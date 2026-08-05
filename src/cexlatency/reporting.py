from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
from plotly.subplots import make_subplots


def generate_reports(run_id: str, rankings: list[dict[str, Any]], samples: list[dict[str, Any]], output_dir: str | Path) -> dict[str,str]:
    root=Path(output_dir)/run_id; root.mkdir(parents=True,exist_ok=True)
    summary={"run_id":run_id,"recommendation":rankings[0]["exchange_id"] if rankings and rankings[0]["confidence"]!="INSUFFICIENT" else None,"rankings":rankings,"methodology":{"latency":"REST p95 and tails are ranked separately; WebSocket timestamp lag is labeled observed lag.","safety":"Public endpoints only; no API keys and no orders.","clock_quality":"UNKNOWN unless independently verified."}}
    json_path=root/"summary.json"; json_path.write_text(json.dumps(summary,indent=2),encoding="utf-8")
    csv_path=root/"rankings.csv"
    with csv_path.open("w",newline="",encoding="utf-8") as f:
        writer=csv.DictWriter(f,fieldnames=["rank","exchange_id","overall_score","confidence","evidence_coverage"]); writer.writeheader()
        for i,row in enumerate(rankings,1): writer.writerow({k:v for k,v in {"rank":i,**row}.items() if k in writer.fieldnames})
    evidence_path=root/"probe_samples.csv"
    if samples:
        with evidence_path.open("w",newline="",encoding="utf-8") as f:
            fields=[k for k in samples[0] if k!="metadata_json"]; writer=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore"); writer.writeheader(); writer.writerows(samples)
    else: evidence_path.write_text("",encoding="utf-8")
    md=[f"# CEX Latency Intelligence Report\n\nRun ID: `{run_id}`\n","> Observed from this host and connection. Results are not universal and do not represent order execution latency.\n","## Executive recommendation\n"]
    if summary["recommendation"]: md.append(f"Best measured technical compromise in this run: **{summary['recommendation']}**. This is a benchmark result, not financial advice.\n")
    else: md.append("No winner is declared because evidence quality is insufficient.\n")
    md.append("\n## Transparent ranking\n\n| Rank | Exchange | Score | Confidence | Coverage |\n|---:|---|---:|---|---:|\n")
    for i,r in enumerate(rankings,1): md.append(f"| {i} | {r['exchange_id']} | {r['overall_score']:.1f} | {r['confidence']} | {r['evidence_coverage']:.0%} |\n")
    md.append("\n## Limitations\n\n- Public market-data paths may differ from private order paths.\n- Observed timestamp lag is not true one-way latency while local clock quality is unknown.\n- Market quality and breadth are neutral placeholders unless sufficient public depth telemetry is collected.\n- A short run cannot represent seven-day time-of-day behavior.\n")
    md_path=root/"executive-report.md"; md_path.write_text("".join(md),encoding="utf-8")
    names=[r["exchange_id"] for r in rankings]; fig=make_subplots(rows=2,cols=1,subplot_titles=("Overall score","REST median / p95 / p99 (ms)"))
    fig.add_trace(go.Bar(x=names,y=[r["overall_score"] for r in rankings],name="Overall score",text=[r["confidence"] for r in rankings]),row=1,col=1)
    for metric,label in (("rest_median","Median"),("rest_p95","p95"),("rest_p99","p99")): fig.add_trace(go.Bar(x=names,y=[r["raw_metrics"].get(metric) for r in rankings],name=label),row=2,col=1)
    fig.update_layout(title=f"CEX Latency Intelligence — {run_id}",height=850,barmode="group",template="plotly_white",annotations=list(fig.layout.annotations)+[dict(text="Evidence over assumptions · public endpoints only · no order placement",xref="paper",yref="paper",x=.5,y=-.12,showarrow=False)])
    html_path=root/"dashboard.html"; fig.write_html(html_path,include_plotlyjs=True,full_html=True)
    return {"html":str(html_path),"markdown":str(md_path),"json":str(json_path),"rankings_csv":str(csv_path),"samples_csv":str(evidence_path)}

