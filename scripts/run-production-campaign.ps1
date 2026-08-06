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
    $resolvedRoot = (Resolve-Path -LiteralPath $root).Path
    $pathMatch = [regex]::Match($resolvedRoot, '^([A-Za-z]):\\(.*)$')
    if (-not $pathMatch.Success) { throw 'The project must be stored on a Windows drive visible to WSL.' }
    $drive = $pathMatch.Groups[1].Value.ToLowerInvariant()
    $relativeRoot = $pathMatch.Groups[2].Value.Replace('\', '/')
    $wslRoot = "/mnt/$drive/$relativeRoot"
    if ($wslRoot.Contains("'")) { throw 'Project path containing an apostrophe is unsupported.' }

    $script = "cd '$wslRoot' && exec env PYTHONPATH=src python3 -m cexlatency.cli campaign --config config/haifa-7day.yaml --start-date $StartDate --daemon --max-windows 42 --poll-seconds 30 >> data/campaign-daemon.log 2>&1"
    & wsl.exe -e bash -lc $script
    $runnerExitCode = $LASTEXITCODE
    Write-WatchdogLog "runner exit=$runnerExitCode"
    exit $runnerExitCode
} catch {
    Write-WatchdogLog "runner failed at line $($_.InvocationInfo.ScriptLineNumber): $($_.Exception.Message); stack=$($_.ScriptStackTrace)"
    exit 1
}
