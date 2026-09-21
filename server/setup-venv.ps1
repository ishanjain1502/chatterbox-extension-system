$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Venv = Join-Path $Root ".venv"

$Python = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    $Python = @("py", "-3.11")
} elseif (Get-Command python3.11 -ErrorAction SilentlyContinue) {
    $Python = @("python3.11")
} else {
    Write-Error @"
CPython 3.11 is required. Install it with:
  winget install Python.Python.3.11
Then re-run: .\setup-venv.ps1
"@
}

& $Python[0] $Python[1..($Python.Length - 1)] -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Selected interpreter is not CPython 3.11. Use the Windows py launcher or python.org 3.11."
}

& $Python[0] $Python[1..($Python.Length - 1)] -m venv $Venv
& (Join-Path $Venv "Scripts\python.exe") -m pip install --upgrade pip
& (Join-Path $Venv "Scripts\python.exe") -m pip install -r (Join-Path $Root "requirements.txt")

Write-Host "Virtual environment ready at $Venv"
Write-Host "Activate with: $($Venv)\Scripts\Activate.ps1"
