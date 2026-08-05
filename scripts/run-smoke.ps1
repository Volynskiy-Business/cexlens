$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & python -m cexlatency.cli --config config/smoke.yaml validate
    & python -m cexlatency.cli --config config/smoke.yaml benchmark --group priority
} finally {
    Pop-Location
}

