from __future__ import annotations

import asyncio
import json
import platform
import re
import shutil
import socket
import hashlib
from urllib.parse import urlparse

import httpx

from .models import ClockStatus, utc_now


async def _command(*args: str, timeout: float = 15) -> tuple[int, str]:
    process = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout)
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return 124, "diagnostic command timed out"
    return process.returncode or 0, output.decode(errors="replace")


async def detect_clock_status() -> ClockStatus:
    system = platform.system()
    if system == "Windows" and shutil.which("w32tm"):
        code, status = await _command("w32tm", "/query", "/status", "/verbose", timeout=10)
        _, strip = await _command("w32tm", "/stripchart", "/computer:time.windows.com", "/dataonly", "/samples:1", timeout=10) if code == 0 else (code,"")
        return _windows_clock_status(code,status,strip,"w32tm")
    if system != "Windows" and shutil.which("powershell.exe"):
        code,status=await _command("powershell.exe","-NoProfile","-Command","w32tm /query /status /verbose",timeout=10)
        _,strip=await _command("powershell.exe","-NoProfile","-Command","w32tm /stripchart /computer:time.windows.com /dataonly /samples:1",timeout=10) if code == 0 else (code,"")
        if code == 0: return _windows_clock_status(code,status,strip,"Windows host w32tm via WSL")
    if shutil.which("timedatectl"):
        code, output = await _command("timedatectl", "show", "--property=NTPSynchronized", "--property=NTP", "--value", timeout=8)
        values = [line.strip().lower() for line in output.splitlines() if line.strip()]
        synchronized = code == 0 and "yes" in values
        quality="SYNCHRONIZED_OFFSET_UNKNOWN" if synchronized else "UNVERIFIED"
        return ClockStatus(synchronized, quality, "systemd-timesyncd" if synchronized else None, None, utc_now(), output[-2000:])
    return ClockStatus(None, "UNKNOWN", None, None, utc_now(), f"No supported clock diagnostic on {system}")


def _windows_clock_status(code: int, status: str, strip: str, diagnostic_source: str) -> ClockStatus:
    source_match=re.search(r"^(?:Source|Источник):\s*(.+)$",status,re.MULTILINE|re.IGNORECASE)
    lowered=status.lower()
    unsynchronized=any(marker in lowered for marker in ("free-running system clock","local cmos clock","локальные часы cmos","свободно работающие системные часы"))
    synchronized=code==0 and not unsynchronized
    offset_match=re.search(r"([+-]\d+(?:\.\d+)?)s",strip)
    offset=float(offset_match.group(1))*1000 if offset_match else None
    if synchronized and offset is not None and abs(offset)<=100: quality="VERIFIED"
    elif synchronized and offset is not None: quality="MEASURED_OFFSET_OUT_OF_BOUNDS"
    else: quality="UNVERIFIED"
    source=source_match.group(1).strip() if source_match else diagnostic_source
    return ClockStatus(synchronized,quality,source,offset,utc_now(),(status+"\n"+strip)[-3000:])


async def trace_route(url: str, max_hops: int = 20, timeout: float = 45) -> str:
    host = urlparse(url).hostname or url
    if platform.system() == "Windows" and shutil.which("tracert"):
        code, output = await _command("tracert", "-d", "-h", str(max_hops), "-w", "1000", host, timeout=timeout)
    elif shutil.which("traceroute"):
        code, output = await _command("traceroute", "-n", "-m", str(max_hops), "-w", "1", host, timeout=timeout)
    elif shutil.which("tracepath"):
        code, output = await _command("tracepath", "-n", "-m", str(max_hops), host, timeout=timeout)
    else:
        return "UNAVAILABLE: no tracert, traceroute, or tracepath executable found"
    return f"exit_code={code}\n{output}"


def summarize_route(output: str) -> dict[str,int | float | str | None]:
    """Extract portable diagnostic features without inferring matching-engine location."""
    hops=[]; identities=[]
    for line in output.splitlines():
        hop_match=re.match(r"^\s*(\d+)\s+",line)
        if not hop_match: continue
        hop=int(hop_match.group(1))
        latencies=[float(value) for value in re.findall(r"<?\s*(\d+(?:\.\d+)?)\s*ms",line,re.IGNORECASE)]
        ip_match=re.search(r"(?:\d{1,3}\.){3}\d{1,3}|[0-9a-fA-F]{2,}(?::[0-9a-fA-F:]+)+",line)
        identity=ip_match.group(0) if ip_match else "*"
        hops.append({"hop":hop,"latency_ms":sum(latencies)/len(latencies) if latencies else None,"identity":identity})
        identities.append(identity)
    responding=[row for row in hops if row["latency_ms"] is not None]
    increases=[]
    for previous,current in zip(responding,responding[1:]):
        increase=float(current["latency_ms"])-float(previous["latency_ms"])
        increases.append((increase,int(current["hop"])))
    largest=max(increases,default=(0.0,None))
    fingerprint=hashlib.sha256("|".join(identities).encode()).hexdigest()[:16] if identities else None
    return {
        "hop_count":max((int(row["hop"]) for row in hops),default=0),
        "responding_hops":len(responding),
        "max_hop_latency_ms":max((float(row["latency_ms"]) for row in responding),default=None),
        "largest_hop_increase_ms":max(0.0,largest[0]),
        "suspected_bottleneck_hop":largest[1] if largest[0]>=20 else None,
        "route_fingerprint":fingerprint,
        "inference_warning":"Visible hops are diagnostic only and do not identify a matching engine.",
    }


def _parse_windows_adapters(output: str) -> list[str]:
    try:
        payload=json.loads(output.lstrip("\ufeff").strip())
    except (json.JSONDecodeError,TypeError):
        return []
    rows=payload if isinstance(payload,list) else [payload]
    return sorted(
        f"{row.get('Name')} [{row.get('InterfaceDescription')}]"
        for row in rows
        if isinstance(row,dict) and row.get("Name") and row.get("HardwareInterface") is True and row.get("Virtual") is not True
    )


async def detect_network_identity(host_id: str, timeout: float = 8) -> dict[str, str | None]:
    interfaces=sorted({name for _,name in socket.if_nameindex() if name and name.lower() not in {"lo","loopback"} and "loopback" not in name.lower()})
    physical_interfaces=[]
    if platform.system() != "Windows" and shutil.which("powershell.exe"):
        code,output=await _command("powershell.exe","-NoProfile","-Command","Get-NetAdapter | Where-Object Status -eq 'Up' | Select-Object Name,InterfaceDescription,HardwareInterface,Virtual | ConvertTo-Json -Compress",timeout=timeout)
        if code == 0: physical_interfaces=_parse_windows_adapters(output)
    public_ip_hash=None; isp_name=None
    try:
        async with httpx.AsyncClient(timeout=timeout,follow_redirects=True,headers={"User-Agent":"cexlatency/0.1 metadata"}) as client:
            response=await client.get("https://ipinfo.io/json")
            response.raise_for_status()
            data=response.json(); raw_ip=data.get("ip")
            if raw_ip: public_ip_hash=hashlib.sha256(f"{host_id}:{raw_ip}".encode()).hexdigest()
            isp_name=data.get("org")
    except Exception:
        pass
    runtime=", ".join(interfaces)
    interface_evidence=("Windows physical: "+", ".join(physical_interfaces)+("; runtime: "+runtime if runtime else "")) if physical_interfaces else runtime
    return {"network_interface":interface_evidence or None,"public_ip_hash":public_ip_hash,"isp_name":isp_name}
