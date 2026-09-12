# Builds "PII Scrub.exe" into dist\. Run on Windows only - PyInstaller
# cannot cross-compile, so this cannot be produced on another platform.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path .\.venv)) { python -m venv .venv }
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m spacy download en_core_web_lg
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean piiscrub.spec

Write-Host "Built: $PSScriptRoot\dist\PII Scrub\PII Scrub.exe"
