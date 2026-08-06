from __future__ import annotations

import asyncio
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
        source_match = re.search(r"^Source:\s*(.+)$", status, re.MULTILINE | re.IGNORECASE)
        synchronized = code == 0 and "free-running system clock" not in status.lower() and "local cmos clock" not in status.lower()
        offset = None
        if synchronized:
            _, strip = await _command("w32tm", "/stripchart", "/computer:time.windows.com", "/dataonly", "/samples:1", timeout=10)
            match = re.search(r"([+-]\d+(?:\.\d+)?)s", strip)
            if match: offset = float(match.group(1)) * 1000
        verified = synchronized and offset is not None and abs(offset) <= 100
        return ClockStatus(synchronized, "VERIFIED" if verified else "UNVERIFIED", source_match.group(1).strip() if source_match else None, offset, utc_now(), status[-2000:])
    if shutil.which("timedatectl"):
        code, output = await _command("timedatectl", "show", "--property=NTPSynchronized", "--property=NTP", "--value", timeout=8)
        values = [line.strip().lower() for line in output.splitlines() if line.strip()]
        synchronized = code == 0 and "yes" in values
        return ClockStatus(synchronized, "VERIFIED" if synchronized else "UNVERIFIED", "systemd-timesyncd" if synchronized else None, None, utc_now(), output[-2000:])
    return ClockStatus(None, "UNKNOWN", None, None, utc_now(), f"No supported clock diagnostic on {system}")


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


async def detect_network_identity(host_id: str, timeout: float = 8) -> dict[str, str | None]:
    interfaces=sorted({name for _,name in socket.if_nameindex() if name and name.lower() not in {"lo","loopback"} and "loopback" not in name.lower()})
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
    return {"network_interface":", ".join(interfaces) or None,"public_ip_hash":public_ip_hash,"isp_name":isp_name}
