$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:DNS_SWITCHER_DEV = '1'
$env:DNS_SWITCHER_SESSION_TOKEN = 'development-only-token'
Write-Host 'Avvio backend su http://127.0.0.1:8765 ...'
Start-Process -FilePath 'py' -ArgumentList '-3.12','-m','backend.run_server','--port','8765','--token','development-only-token' -WorkingDirectory $root
Write-Host 'Avvio Vite su http://127.0.0.1:5173/?token=development-only-token ...'
Push-Location (Join-Path $root 'frontend')
npm run dev
Pop-Location
