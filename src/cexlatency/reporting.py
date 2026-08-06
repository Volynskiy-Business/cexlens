from __future__ import annotations

import csv
import html
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import plotly.io as pio


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = sorted({key for row in rows for key in row if not key.endswith("_json") and key != "metadata"})
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _figure_html(figure: go.Figure, include_js: bool = False) -> str:
    figure.update_layout(template="plotly_white", margin=dict(l=55,r=30,t=55,b=55), height=430, legend=dict(orientation="h",y=-.18))
    return pio.to_html(figure, full_html=False, include_plotlyjs=True if include_js else False, config={"displaylogo":False,"responsive":True})


def _recommendations(rankings: list[dict[str, Any]]) -> dict[str, Any]:
    eligible=[r for r in rankings if r["confidence"] != "INSUFFICIENT"]
    by_metric=lambda key,reverse=False: sorted((r for r in rankings if r["raw_metrics"].get(key) is not None),key=lambda r:r["raw_metrics"][key],reverse=reverse)
    return {
        "best_overall": eligible[0]["exchange_id"] if eligible else None,
        "best_low_latency": (by_metric("rest_p95") or [{}])[0].get("exchange_id"),
        "best_stable": (by_metric("rest_p99") or [{}])[0].get("exchange_id"),
        "best_altcoin_breadth": (by_metric("market_count",True) or [{}])[0].get("exchange_id"),
        "unsuitable_or_unproven": [r["exchange_id"] for r in rankings if r["confidence"]=="INSUFFICIENT" or r["raw_metrics"].get("success_rate",0)<.9],
    }


def _dimension_rankings(rankings: list[dict[str, Any]]) -> dict[str, list[str]]:
    def ordered(metric: str, reverse: bool = False) -> list[str]:
        rows=[r for r in rankings if r["raw_metrics"].get(metric) is not None]
        return [r["exchange_id"] for r in sorted(rows,key=lambda r:r["raw_metrics"][metric],reverse=reverse)]
    def component(name: str) -> list[str]:
        return [r["exchange_id"] for r in sorted(rankings,key=lambda r:r["components"].get(name,0),reverse=True)]
    return {
        "lowest_network_latency": ordered("tcp_median"),
        "best_websocket_stability": component("websocket"),
        "best_market_data_freshness": component("freshness"),
        "best_order_book_quality": component("market_quality"),
        "best_futures_market_coverage": ordered("market_count",True),
        "best_overall_manual_scalping": [r["exchange_id"] for r in rankings if r["confidence"]!="INSUFFICIENT"],
        "best_major_pairs": component("market_quality"),
        "best_altcoin_small_cap_futures_proxy": ordered("market_count",True),
        "best_technical_compromise_from_haifa": [r["exchange_id"] for r in rankings if r["confidence"]!="INSUFFICIENT"],
    }


def generate_reports(run_id: str, rankings: list[dict[str, Any]], samples: list[dict[str, Any]], output_dir: str | Path, websocket_rows: list[dict[str, Any]] | None = None, market_rows: list[dict[str, Any]] | None = None, routes: list[dict[str, Any]] | None = None) -> dict[str,str]:
    websocket_rows=websocket_rows or []; market_rows=market_rows or []; routes=routes or []
    root=Path(output_dir)/run_id; root.mkdir(parents=True,exist_ok=True)
    recommendations=_recommendations(rankings)
    summary={"run_id":run_id,"recommendation":recommendations["best_overall"],"recommendations":recommendations,"rankings_by_dimension":_dimension_rankings(rankings),"rankings":rankings,"websocket_sessions":websocket_rows,"market_quality":market_rows,"route_diagnostics_count":len(routes),"methodology":{"latency":"REST p95 and tails are ranked separately; WebSocket timestamp lag is labeled observed lag.","safety":"Public endpoints only; no API keys and no orders.","clock_quality":"Captured per host; observed lag is not exact one-way latency unless VERIFIED.","market_values":"Exchange-provided and not independently audited."}}
    json_path=root/"summary.json"; json_path.write_text(json.dumps(summary,indent=2),encoding="utf-8")
    ranking_rows=[{"rank":i,"exchange_id":r["exchange_id"],"overall_score":r["overall_score"],"confidence":r["confidence"],"evidence_coverage":r["evidence_coverage"]} for i,r in enumerate(rankings,1)]
    csv_path=root/"rankings.csv"; _write_csv(csv_path,ranking_rows)
    evidence_path=root/"probe_samples.csv"; _write_csv(evidence_path,samples)
    ws_path=root/"websocket_sessions.csv"; _write_csv(ws_path,websocket_rows)
    market_path=root/"market_quality.csv"; _write_csv(market_path,market_rows)

    md=[f"# CEX Latency Intelligence Report\n\nRun ID: `{run_id}`\n","> Observed from this host and connection. Results are not universal and do not represent order execution latency.\n","## Executive recommendation\n"]
    if recommendations["best_overall"]: md.append(f"Best measured technical compromise: **{recommendations['best_overall']}**. Best REST p95: **{recommendations['best_low_latency']}**; best tail stability: **{recommendations['best_stable']}**; broadest reported futures universe: **{recommendations['best_altcoin_breadth']}**. This is benchmark evidence, not financial advice.\n")
    else: md.append(f"No overall winner is declared because evidence quality is insufficient. Provisional REST p95 leader: **{recommendations['best_low_latency']}**; provisional broadest futures universe: **{recommendations['best_altcoin_breadth']}**.\n")
    md.append("\n## Transparent ranking\n\n| Rank | Exchange | Score | Confidence | Coverage | REST p95 | Spread bps | Markets |\n|---:|---|---:|---|---:|---:|---:|---:|\n")
    for i,r in enumerate(rankings,1):
        raw=r["raw_metrics"]; fmt=lambda v:"—" if v is None else f"{v:.2f}"
        md.append(f"| {i} | {r['exchange_id']} | {r['overall_score']:.1f} | {r['confidence']} | {r['evidence_coverage']:.0%} | {fmt(raw.get('rest_p95'))} | {fmt(raw.get('spread_bps'))} | {raw.get('market_count') or '—'} |\n")
    md.append("\n## Evidence classification\n\n- **Measured:** individual probe samples, WebSocket sessions, and public order-book snapshots.\n- **Derived:** percentiles, jitter, spread, depth bands, normalized components, and confidence.\n- **Inferred:** relative suitability labels and provisional leaders.\n- **Unknown:** private order path, matching-engine location, and exact one-way latency without verified clock offset.\n")
    md.append("\n## Limitations\n\n- Public market-data paths may differ from private order paths.\n- Observed timestamp lag is not true one-way latency unless clock quality is verified.\n- Exchange volume, open interest, funding, and depth are exchange-provided and not independently audited.\n- A short run cannot represent seven-day time-of-day behavior.\n")
    md_path=root/"executive-report.md"; md_path.write_text("".join(md),encoding="utf-8")

    names=[r["exchange_id"] for r in rankings]
    figures: list[tuple[str,str,go.Figure]]=[]
    overall=go.Figure(go.Bar(x=names,y=[r["overall_score"] for r in rankings],text=[r["confidence"] for r in rankings],marker_color="#315efb")); overall.update_layout(title="Overall score and confidence",yaxis_title="Score")
    figures.append(("overview","Executive Overview",overall))
    components=go.Figure()
    for component in ("websocket","rest_p95","tail_stability","reliability","freshness","market_quality","market_breadth","accessibility"):
        components.add_bar(name=component,x=names,y=[r["components"].get(component) for r in rankings])
    components.update_layout(title="Ranking component breakdown",barmode="group",yaxis_title="Component score")
    figures.append(("ranking","Exchange Ranking",components))
    latency=go.Figure()
    for exchange in names:
        values=[s["duration_ms"] for s in samples if s["exchange_id"]==exchange and s["probe_type"].startswith("rest") and s.get("success") and s.get("duration_ms") is not None]
        latency.add_trace(go.Box(y=values,name=exchange,boxpoints="outliers"))
    latency.update_layout(title="REST latency distribution",yaxis_title="Milliseconds")
    figures.append(("distribution","Latency Distribution",latency))
    tails=go.Figure()
    for key,label in (("rest_median","Median"),("rest_p95","p95"),("rest_p99","p99")): tails.add_bar(name=label,x=names,y=[r["raw_metrics"].get(key) for r in rankings])
    tails.update_layout(title="Median and tail latency",barmode="group",yaxis_title="Milliseconds")
    figures.append(("tails","Tail Latency",tails))
    timeline=go.Figure()
    for exchange in names:
        rows=[s for s in samples if s["exchange_id"]==exchange and s["probe_type"].startswith("rest") and s.get("success")]
        timeline.add_scatter(name=exchange,x=[s["started_at"] for s in rows],y=[s["duration_ms"] for s in rows],mode="lines+markers")
    timeline.update_layout(title="Latency over time",yaxis_title="Milliseconds")
    figures.append(("timeline","Latency Over Time",timeline))
    failures=go.Figure(go.Bar(x=names,y=[100*(1-r["raw_metrics"].get("success_rate",0)) for r in rankings],marker_color="#d64545")); failures.update_layout(title="REST failure rate",yaxis_title="Percent")
    figures.append(("failures","Failure Rate",failures))
    ws=go.Figure()
    ws_map={r["exchange_id"]:r for r in websocket_rows}
    ws.add_bar(name="Handshake",x=names,y=[ws_map.get(e,{}).get("handshake_ms") for e in names]); ws.add_bar(name="First message",x=names,y=[ws_map.get(e,{}).get("first_message_ms") for e in names]); ws.add_bar(name="p95 interval",x=names,y=[ws_map.get(e,{}).get("p95_interval_ms") for e in names]); ws.update_layout(title="WebSocket connection and message stability",barmode="group",yaxis_title="Milliseconds")
    figures.append(("websocket","WebSocket Stability",ws))
    hourly: dict[tuple[str,int],list[float]]=defaultdict(list)
    for s in samples:
        if s.get("success") and s.get("duration_ms") is not None:
            try: hourly[(s["exchange_id"],datetime.fromisoformat(s["started_at"]).hour)].append(s["duration_ms"])
            except (ValueError,TypeError): pass
    hours=sorted({h for _,h in hourly})
    heat=go.Figure(go.Heatmap(x=[f"{h:02}:00 UTC" for h in hours],y=names,z=[[sum(hourly[(e,h)])/len(hourly[(e,h)]) if hourly[(e,h)] else None for h in hours] for e in names],colorscale="Viridis",colorbar_title="ms")); heat.update_layout(title="Time-of-day REST latency")
    figures.append(("heatmap","Time-of-Day Comparison",heat))
    market=go.Figure(); market.add_bar(name="Average spread bps",x=names,y=[r["raw_metrics"].get("spread_bps") for r in rankings]); market.add_bar(name="10 bps depth / 1M",x=names,y=[(r["raw_metrics"].get("depth_10bps") or 0)/1_000_000 for r in rankings]); market.update_layout(title="Order-book quality",barmode="group")
    figures.append(("orderbook","Order-Book Quality",market))
    breadth=go.Figure(go.Bar(x=names,y=[r["raw_metrics"].get("market_count") for r in rankings],marker_color="#10a37f")); breadth.update_layout(title="Exchange-reported futures market coverage",yaxis_title="Instrument count")
    figures.append(("coverage","Futures Coverage",breadth))

    nav="".join(f'<a href="#{anchor}">{html.escape(title)}</a>' for anchor,title,_ in figures)
    sections=[]
    for index,(anchor,title,figure) in enumerate(figures): sections.append(f'<section id="{anchor}"><h2>{html.escape(title)}</h2>{_figure_html(figure,index==0)}</section>')
    route_rows="".join(f"<tr><td>{html.escape(r['exchange_id'])}</td><td>{html.escape(r['endpoint'])}</td><td><pre>{html.escape(r['output'][:4000])}</pre></td></tr>" for r in routes) or '<tr><td colspan="3">Route diagnostics were disabled for this run.</td></tr>'
    raw_rows="".join(f"<tr><td>{html.escape(str(s.get('exchange_id')))}</td><td>{html.escape(str(s.get('probe_type')))}</td><td>{html.escape(str(s.get('duration_ms')))}</td><td>{html.escape(str(bool(s.get('success'))))}</td><td>{html.escape(str(s.get('error_class') or ''))}</td></tr>" for s in samples[:1000])
    dashboard=f'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>CEXLENS {html.escape(run_id)}</title><style>body{{margin:0;font:15px system-ui;color:#17213b;background:#f5f7fb}}nav{{position:sticky;top:0;z-index:3;display:flex;gap:16px;overflow:auto;padding:14px 24px;background:#111a33}}nav a{{color:#dce5ff;text-decoration:none;white-space:nowrap}}main{{max-width:1280px;margin:auto;padding:28px}}section{{background:white;border:1px solid #dfe5f1;border-radius:12px;padding:20px;margin:0 0 24px}}h1{{margin-top:0}}table{{border-collapse:collapse;width:100%}}th,td{{padding:9px;border-bottom:1px solid #e5e9f2;text-align:left}}pre{{white-space:pre-wrap;max-height:220px;overflow:auto}}.notice{{padding:14px;border-left:4px solid #f0ad2c;background:#fff8e6}}</style></head><body><nav>{nav}<a href="#routes">Route Diagnostics</a><a href="#raw">Raw Evidence</a><a href="#methodology">Methodology</a></nav><main><h1>CEXLENS · {html.escape(run_id)}</h1><p class="notice">Public-endpoint evidence only. No orders, no credentials, and no claim of matching-engine latency.</p>{''.join(sections)}<section id="routes"><h2>Route Diagnostics</h2><table><tr><th>Exchange</th><th>Endpoint</th><th>Diagnostic output</th></tr>{route_rows}</table></section><section id="raw"><h2>Raw Evidence</h2><table><tr><th>Exchange</th><th>Probe</th><th>Duration ms</th><th>Success</th><th>Error</th></tr>{raw_rows}</table></section><section id="methodology"><h2>Methodology and Limitations</h2><p>Monotonic clocks measure durations. Exchange timestamps are reported as observed lag, not exact one-way latency unless local clock quality is verified. Market values are exchange-provided and not independently audited.</p></section></main></body></html>'''
    html_path=root/"dashboard.html"; html_path.write_text(dashboard,encoding="utf-8")
    return {"html":str(html_path),"markdown":str(md_path),"json":str(json_path),"rankings_csv":str(csv_path),"samples_csv":str(evidence_path),"websockets_csv":str(ws_path),"market_quality_csv":str(market_path)}
