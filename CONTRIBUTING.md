# Contributing

Contributions should preserve CEXLENS's evidence-first and safety-first design.

1. Create a focused branch from `main`.
2. Add sanitized fixtures for every adapter parsing change.
3. Run `pytest` and `cexlatency --config config/smoke.yaml validate`.
4. State whether live endpoints were exercised, from which broad region, and at what request rate.
5. Never add secrets, private-account requirements, live-order methods, certificate bypasses, or aggressive probe rates.

Endpoint support claims require captured evidence. Geo-blocked or partial support should be documented rather than hidden.

