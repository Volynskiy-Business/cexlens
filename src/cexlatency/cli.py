from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from datetime import date,datetime,timedelta,timezone
from pathlib import Path

from .adapters import REGISTRY
from .config import load_config
from .reporting import generate_reports
from .runner import benchmark
from .campaign import build_schedule, run_campaign
from .scoring import rank
from .storage import Storage
from .validation import audit_campaign_acceptance


def parse_duration(value: str) -> int:
    units={"s":1,"m":60,"h":3600}
    if len(value)<2 or value[-1].lower() not in units:
        raise argparse.ArgumentTypeError("duration must use s, m, or h suffix (for example 30s, 10m, 2h)")
    try: amount=float(value[:-1])
    except ValueError as exc: raise argparse.ArgumentTypeError("duration must be numeric") from exc
    seconds=int(amount*units[value[-1].lower()])
    if seconds<1 or seconds>7*24*3600: raise argparse.ArgumentTypeError("duration must be between 1 second and 7 days")
    return seconds


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog="cexlatency",description="Public-endpoint CEX latency intelligence; never places orders")
    p.add_argument("--config",default="config/haifa-7day.yaml"); p.add_argument("--json",action="store_true",dest="json_output")
    sub=p.add_subparsers(dest="command",required=True)
    def command(name: str) -> argparse.ArgumentParser:
        result=sub.add_parser(name)
        result.add_argument("--config",default=argparse.SUPPRESS)
        result.add_argument("--json",action="store_true",dest="json_output",default=argparse.SUPPRESS)
        return result
    command("discover")
    b=command("benchmark"); b.add_argument("--exchange",action="append"); b.add_argument("--group",default="priority"); b.add_argument("--iterations",type=int); b.add_argument("--duration",type=parse_duration); b.add_argument("--ws-duration",type=int); b.add_argument("--dry-run",action="store_true")
    c=command("campaign"); c.add_argument("--dry-run",action="store_true"); c.add_argument("--iterations",type=int); c.add_argument("--ws-duration",type=int); c.add_argument("--group",default="priority"); c.add_argument("--max-windows",type=int,default=1); c.add_argument("--daemon",action="store_true"); c.add_argument("--poll-seconds",type=int,default=30); c.add_argument("--start-date",type=date.fromisoformat)
    r=command("report"); r.add_argument("--run-id"); r.add_argument("--campaign")
    s=command("status"); s.add_argument("--campaign")
    a=command("acceptance"); a.add_argument("--campaign")
    cleanup=command("retention"); cleanup.add_argument("--apply",action="store_true")
    command("validate")
    x=command("compare"); x.add_argument("--run-id",action="append",required=True)
    return p


async def _async_main(args: argparse.Namespace) -> int:
    config=load_config(args.config)
    if args.command=="discover":
        rows=[]
        for adapter in REGISTRY.values(): rows.append({"exchange_id":adapter.exchange_id,"display_name":adapter.display_name,"endpoints":[e.url for e in await adapter.discover_public_endpoints()],"websocket_supported":adapter.websocket_supported,"notes":adapter.notes})
        print(json.dumps(rows,indent=2) if args.json_output else "\n".join(f"{r['exchange_id']:10} REST=yes WS={'yes' if r['websocket_supported'] else 'partial'}" for r in rows)); return 0
    if args.command=="benchmark":
        exchanges=getattr(args,"exchange",None) or config.selected_exchanges(getattr(args,"group","priority"))
        effective_iterations=args.iterations or (1 if args.duration else config.probes.iterations)
        effective_ws=args.ws_duration if args.ws_duration is not None else (min(args.duration,config.probes.websocket_observation_seconds) if args.duration else config.probes.websocket_observation_seconds)
        if getattr(args,"dry_run",False): print(json.dumps({"exchanges":exchanges,"iterations_minimum":effective_iterations,"duration_seconds":args.duration,"websocket_seconds":effective_ws},indent=2)); return 0
        run_id,paths,rankings=await benchmark(config,exchanges,effective_iterations,effective_ws,lambda s: None if args.json_output else print(s,flush=True),args.duration)
        result={"run_id":run_id,"reports":paths,"rankings":rankings}; print(json.dumps(result,indent=2) if args.json_output else f"Run {run_id} complete\n"+"\n".join(f"{i}. {r['exchange_id']} {r['overall_score']:.1f} ({r['confidence']})" for i,r in enumerate(rankings,1))); return 0
    if args.command=="campaign":
        exchanges=config.selected_exchanges(args.group)
        if args.dry_run:
            print(json.dumps({"campaign":config.campaign.model_dump(),"schedule":[{"utc":u,"local":l} for u,l in build_schedule(config,args.start_date)],"exchanges":exchanges},indent=2,default=str)); return 0
        result=await run_campaign(config,exchanges,args.iterations,args.ws_duration,args.max_windows,args.daemon,args.poll_seconds,lambda s: None if args.json_output else print(s,flush=True),args.start_date)
        print(json.dumps(result,indent=2)); return 0
    if args.command=="status":
        name=args.campaign or config.campaign.name
        with Storage(config.storage_path) as store:
            windows=store.campaign_windows(name); definition=store.campaign_definition(name)
            result={"campaign":name,"definition":definition,"summary":store.campaign_summary(name),"next_window_utc":store.next_campaign_window(name),"completed_run_ids":store.campaign_run_ids(name),"windows":windows}
        if args.json_output: print(json.dumps(result,indent=2))
        else:
            print(f"Campaign {name}: "+", ".join(f"{k}={v}" for k,v in result["summary"].items()))
            print(f"Next window UTC: {result['next_window_utc'] or 'none'}")
            for row in windows: print(f"{row['local_label']}  {row['status']:9}  attempts={row['attempts']}  run={row['run_id'] or '-'}")
        return 0
    if args.command=="retention":
        days=config.retention.benchmark_days
        if days is None:
            result={"enabled":False,"message":"retention.benchmark_days is null; no data changed"}
        else:
            cutoff=(datetime.now(timezone.utc)-timedelta(days=days)).isoformat()
            with Storage(config.storage_path) as store:
                candidates=store.retention_candidates(cutoff)
                removed=store.prune_runs_before(cutoff) if args.apply else []
            result={"enabled":True,"cutoff_utc":cutoff,"candidate_run_ids":candidates,"applied":bool(args.apply),"removed_run_ids":removed,"preserved_campaign_runs":True,"report_files_preserved":True}
        print(json.dumps(result,indent=2) if args.json_output else json.dumps(result,indent=2)); return 0
    if args.command=="acceptance":
        name=args.campaign or config.campaign.name
        with Storage(config.storage_path) as store: result=audit_campaign_acceptance(store,config,name)
        if args.json_output: print(json.dumps(result,indent=2))
        else:
            print(result["gate"])
            for check,passed in result["checks"].items(): print(f"{'PASS' if passed else 'FAIL'}  {check}")
        return 0 if result["ready"] else 1
    if args.command=="report":
        with Storage(config.storage_path) as store:
            if args.campaign:
                run_ids=store.campaign_run_ids(args.campaign)
                if not run_ids: raise ValueError(f"campaign has no completed windows: {args.campaign}")
                report_id="campaign-"+"".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in args.campaign)
                samples=store.samples_for_runs(run_ids); ws=store.websockets_for_runs(run_ids); markets=store.orderbooks_for_runs(run_ids); routes=store.routes_for_runs(run_ids); window_count=len(run_ids)
            else:
                report_id=args.run_id or store.latest_run_id()
                if not report_id: raise ValueError("no benchmark run found")
                samples=store.samples(report_id); ws=store.websockets(report_id); markets=store.orderbooks(report_id); routes=store.routes(report_id); window_count=1
            rankings=rank(samples,ws,sorted({s['exchange_id'] for s in samples}),config.scoring.weights,markets,window_count,len(config.benchmark_symbols())); paths=generate_reports(report_id,rankings,samples,config.report_directory,ws,markets,routes,config.campaign.timezone)
            for kind,path in paths.items(): store.add_report(report_id,kind,path)
        print(json.dumps(paths,indent=2)); return 0
    if args.command=="compare":
        if len(args.run_id)!=2: raise ValueError("compare requires exactly two --run-id values")
        with sqlite3.connect(config.storage_path) as conn:
            for rid in args.run_id:
                rows=conn.execute("SELECT exchange_id,overall_score,confidence FROM score_snapshots WHERE run_id=? ORDER BY overall_score DESC",(rid,)).fetchall(); print(rid,json.dumps(rows))
        return 0
    if args.command=="validate":
        missing=[e for group in config.exchanges.values() for e in group if e not in REGISTRY]
        status={"config":"valid","registered_exchanges":len(REGISTRY),"missing":missing,"safety":{"live_orders":False,"api_keys":False},"storage_parent":str(Path(config.storage_path).parent)}
        print(json.dumps(status,indent=2)); return 1 if missing else 0
    return 2


def main() -> None:
    args=parser().parse_args()
    try: raise SystemExit(asyncio.run(_async_main(args)))
    except KeyboardInterrupt: print("Interrupted safely; no orders were ever enabled.",file=sys.stderr); raise SystemExit(130)
    except Exception as exc: print(f"ERROR: {type(exc).__name__}: {exc}",file=sys.stderr); raise SystemExit(1)


if __name__=="__main__": main()
