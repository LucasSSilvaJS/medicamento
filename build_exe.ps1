# Gera dist\MedicamentoLembretes.exe (arquivo único, sem console).
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install -r requirements.txt -r requirements-build.txt
python -m PyInstaller --clean --noconfirm medicamento_tray.spec

Write-Host ""
Write-Host "Pronto: dist\MedicamentoLembretes.exe"
Write-Host "Copie o .exe para onde quiser e mantenha config.json na mesma pasta (ou deixe o app criar um na primeira execução)."
