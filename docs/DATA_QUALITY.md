# Data quality

Every failed probe is stored with a classification rather than discarded. Rankings distinguish measured facts (samples), derived metrics (percentiles and jitter), inferred conclusions (relative score), and unknowns (clock quality and private order paths).

`HIGH` confidence requires broad sampling, very high success, multiple daily windows, and, where timestamp lag is used, verified clock quality. A single smoke run will normally remain `LOW` or `INSUFFICIENT`.

Endpoint reachability, HTTP status, sample size, tail behavior, and evidence coverage should be inspected before acting on a ranking. Exchange-provided volume or timestamps are not independently audited.

