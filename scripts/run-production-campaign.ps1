param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$StartDate
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$watchdogLog = Join-Path $root 'data\campaign-watchdog.log'

function Write-WatchdogLog([string]$Message) {
    $line = '{0:o} {1}' -f (Get-Date), $Message
    Add-Content -LiteralPath $watchdogLog -Value $line -Encoding UTF8
}

try {
    $wslRoot = (& wsl.exe -e wslpath -a $root).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $wslRoot) { throw 'Could not resolve project path inside WSL.' }
    if ($wslRoot.Contains("'")) { throw 'Project path containing an apostrophe is unsupported.' }

    $script = "cd '$wslRoot' && exec env PYTHONPATH=src python3 -m cexlatency.cli campaign --config config/haifa-7day.yaml --start-date $StartDate --daemon --max-windows 42 --poll-seconds 30 >> data/campaign-daemon.log 2>&1"
    $psi = [System.Diagnostics.ProcessStartInfo]::new()
    $psi.FileName = 'wsl.exe'
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    @('-e', 'bash', '-lc', $script) | ForEach-Object { [void]$psi.ArgumentList.Add($_) }
    $process = [System.Diagnostics.Process]::Start($psi)
    $process.WaitForExit()
    Write-WatchdogLog "runner exit=$($process.ExitCode)"
    exit $process.ExitCode
} catch {
    Write-WatchdogLog "runner failed: $($_.Exception.Message)"
    exit 1
}
