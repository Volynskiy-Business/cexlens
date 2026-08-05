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

Run a smoke campaign with `cexlatency --config config/smoke.yaml benchmark --group priority`. Ctrl+C ends orchestration safely; no private or trading operation exists.

For periodic runs, create a Windows Task Scheduler action targeting `.venv\Scripts\cexlatency.exe` with arguments `--config config/haifa-7day.yaml campaign` and set the working directory to the repository root. Create six daily triggers corresponding to the YAML windows. Ensure the computer is awake and uses the same intended network path.

`tracert <hostname>` may be captured manually for route diagnosis. It is never treated as matching-engine latency. Docker is optional and not required.

