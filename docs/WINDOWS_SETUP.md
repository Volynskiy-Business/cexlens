# Windows 11 setup

Open PowerShell 7 in the repository root:

```powershell
py -3.12 -m venv .venv
Set-ExecutionPolicy -Scope Process Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
cexlatency validate
```

Run a smoke campaign with `cexlatency benchmark --config config/smoke.yaml --group priority`. Ctrl+C ends orchestration safely; no private or trading operation exists. `scripts\cexlatency.ps1` is the one-command launcher when the package entry point is unavailable.

For periodic runs, create a Windows Task Scheduler action targeting `.venv\Scripts\cexlatency.exe` with arguments `campaign --config config/haifa-7day.yaml` and set the working directory to the repository root. Create six daily triggers corresponding to the YAML windows. Each invocation atomically claims at most one due window and resumes interrupted state. Alternatively, run `cexlatency campaign --config config/haifa-7day.yaml --daemon --max-windows 42` in a supervised terminal.

The production config allows a 30-minute claim grace period. If the computer is asleep beyond it, the window becomes `MISSED` instead of contaminating the intended time-of-day sample. Use a new campaign name to restart with a changed definition.

To schedule a clean future start, pass the local calendar date explicitly, for example `cexlatency campaign --config config/haifa-7day.yaml --start-date 2026-08-07 --daemon --max-windows 42`.

For restart resilience, run `scripts\install-campaign-watchdog.ps1 -StartDate 2026-08-07`. The watchdog checks every 30 minutes, uses Task Scheduler's `IgnoreNew` policy, requests wake-to-run, remains eligible on battery power, and the application-level lock exits duplicate daemon launchers safely.

After completed windows, generate the aggregate dashboard with `cexlatency report --config config/haifa-7day.yaml --campaign haifa-home-baseline`.

Inspect progress at any time with `cexlatency status --config config/haifa-7day.yaml --campaign haifa-home-baseline`.

`tracert <hostname>` may be captured manually for route diagnosis. It is never treated as matching-engine latency. Docker is optional and not required.
