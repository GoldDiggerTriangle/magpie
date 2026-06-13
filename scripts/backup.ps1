param(
    [string]$BackendDir = "",
    [string]$PythonExe = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")

if ([string]::IsNullOrWhiteSpace($BackendDir)) {
    $BackendDir = Join-Path $RepoRoot "backend"
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $CandidateVenvs = @(
        (Join-Path $RepoRoot ".venv"),
        (Join-Path $BackendDir ".venv")
    )
    $PythonExe = "python"
    foreach ($VenvRoot in $CandidateVenvs) {
        $ActivateScript = Join-Path $VenvRoot "Scripts\Activate.ps1"
        $VenvPython = Join-Path $VenvRoot "Scripts\python.exe"
        if ((Test-Path -LiteralPath $ActivateScript) -and (Test-Path -LiteralPath $VenvPython)) {
            . $ActivateScript
            $PythonExe = $VenvPython
            break
        }
    }
}

Push-Location -LiteralPath $BackendDir
try {
    & $PythonExe "manage.py" "backup" "--upload" "--keep-daily" "7" "--keep-weekly" "4"
    if ($LASTEXITCODE -ne 0) {
        throw "Magpie backup failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
