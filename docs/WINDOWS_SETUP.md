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

After completed windows, generate the aggregate dashboard with `cexlatency report --config config/haifa-7day.yaml --campaign haifa-home-baseline`.

`tracert <hostname>` may be captured manually for route diagnosis. It is never treated as matching-engine latency. Docker is optional and not required.
