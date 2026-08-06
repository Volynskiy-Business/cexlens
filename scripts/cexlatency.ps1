$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$installed = Join-Path $root '.venv\Scripts\cexlatency.exe'
Push-Location $root
try {
    if (Test-Path -LiteralPath $installed -PathType Leaf) {
        & $installed @args
    } else {
        & python -m cexlatency.cli @args
    }
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
