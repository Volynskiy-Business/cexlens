from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
from pathlib import Path

from .adapters import REGISTRY
from .config import load_config
from .reporting import generate_reports
from .runner import benchmark
from .scoring import rank
from .storage import Storage


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog="cexlatency",description="Public-endpoint CEX latency intelligence; never places orders")
    p.add_argument("--config",default="config/haifa-7day.yaml"); p.add_argument("--json",action="store_true",dest="json_output")
    sub=p.add_subparsers(dest="command",required=True)
    sub.add_parser("discover")
    b=sub.add_parser("benchmark"); b.add_argument("--exchange",action="append"); b.add_argument("--group",default="priority"); b.add_argument("--iterations",type=int); b.add_argument("--ws-duration",type=int); b.add_argument("--dry-run",action="store_true")
    c=sub.add_parser("campaign"); c.add_argument("--dry-run",action="store_true"); c.add_argument("--iterations",type=int)
    r=sub.add_parser("report"); r.add_argument("--run-id")
    v=sub.add_parser("validate")
    x=sub.add_parser("compare"); x.add_argument("--run-id",action="append",required=True)
    return p


async def _async_main(args: argparse.Namespace) -> int:
    config=load_config(args.config)
    if args.command=="discover":
        rows=[]
        for adapter in REGISTRY.values(): rows.append({"exchange_id":adapter.exchange_id,"display_name":adapter.display_name,"endpoints":[e.url for e in await adapter.discover_public_endpoints()],"websocket_supported":bool(adapter.ws_url),"notes":adapter.notes})
        print(json.dumps(rows,indent=2) if args.json_output else "\n".join(f"{r['exchange_id']:10} REST=yes WS={'yes' if r['websocket_supported'] else 'partial'}" for r in rows)); return 0
    if args.command in ("benchmark","campaign"):
        exchanges=getattr(args,"exchange",None) or config.selected_exchanges(getattr(args,"group","priority"))
        if getattr(args,"dry_run",False): print(json.dumps({"exchanges":exchanges,"iterations":args.iterations or config.probes.iterations,"websocket_seconds":config.probes.websocket_observation_seconds},indent=2)); return 0
        run_id,paths,rankings=await benchmark(config,exchanges,args.iterations,getattr(args,"ws_duration",None),lambda s: None if args.json_output else print(s))
        result={"run_id":run_id,"reports":paths,"rankings":rankings}; print(json.dumps(result,indent=2) if args.json_output else f"Run {run_id} complete\n"+"\n".join(f"{i}. {r['exchange_id']} {r['overall_score']:.1f} ({r['confidence']})" for i,r in enumerate(rankings,1))); return 0
    if args.command=="report":
        with Storage(config.storage_path) as store:
            run_id=args.run_id or store.latest_run_id()
            if not run_id: raise ValueError("no benchmark run found")
            samples=store.samples(run_id); ws=store.websockets(run_id); rankings=rank(samples,ws,sorted({s['exchange_id'] for s in samples}),config.scoring.weights); paths=generate_reports(run_id,rankings,samples,config.report_directory)
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

