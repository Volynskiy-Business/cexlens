# Data quality

Every failed probe is stored with a classification rather than discarded. Rankings distinguish measured facts (samples), derived metrics (percentiles and jitter), inferred conclusions (relative score), and unknowns (clock quality and private order paths).

The host record contains only an anonymized host ID, a host-salted SHA-256 public-IP hash, interfaces, ISP label, OS/Python/timezone, and clock diagnostic. Raw public IP is not persisted. Every run snapshots configuration, Git SHA, adapter capabilities, endpoints, and symbol mappings.

`HIGH` confidence requires broad sampling, very high success, multiple daily windows, and, where timestamp lag is used, verified clock quality. A single smoke run will normally remain `LOW` or `INSUFFICIENT`.

Campaign windows have an explicit grace period. A pending window older than that period becomes `MISSED` and is never relabeled with late measurements. The complete campaign definition is SHA-256 fingerprinted and immutable under its name.

Every claimed window has a unique worker token and a bounded lease. Concurrent launchers cannot reclaim an active window; an interrupted window is recoverable only after its lease expires and remains subject to the original grace rule.

Database retention is disabled by default (`retention.benchmark_days: null`). `cexlatency retention` is a non-destructive preview; deletion occurs only with `--apply`, never removes campaign-referenced runs, and preserves generated report files. Retention is deliberately excluded from the immutable measurement definition because it does not alter how evidence is collected.

Endpoint reachability, HTTP status, sample size, tail behavior, and evidence coverage should be inspected before acting on a ranking. Recent-trade frequency is derived from the timestamp span of a bounded latest-trades response and can vary sharply with sampling time. Exchange-provided trades, volume, or timestamps are not independently audited.
