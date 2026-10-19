# Arranca backend (uvicorn en 8000, venv de backend/.venv) y frontend (npm run dev, 5173).
# Si un puerto ya esta ocupado no arranca un duplicado y avisa.
# Uso (desde la raiz): powershell -ExecutionPolicy Bypass -File scripts/dev.ps1
$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $PSScriptRoot
$backendDir = Join-Path $root 'backend'
$frontendDir = Join-Path $root 'frontend'
$python = Join-Path $backendDir '.venv\Scripts\python.exe'
$backendPort = 8000
$frontendPort = 5173

function Test-PortBusy([int]$Port) {
    # Prueba IPv4 y IPv6 (Vite escucha en ::1 cuando resuelve localhost).
    foreach ($ip in @('127.0.0.1', '::1')) {
        if ($ip -eq '::1') {
            $family = [System.Net.Sockets.AddressFamily]::InterNetworkV6
        } else {
            $family = [System.Net.Sockets.AddressFamily]::InterNetwork
        }
        $client = New-Object System.Net.Sockets.TcpClient($family)
        try {
            $client.Connect([System.Net.IPAddress]::Parse($ip), $Port)
            return $true
        } catch {
            # Puerto libre en esta familia; probar la siguiente.
        } finally {
            $client.Close()
        }
    }
    return $false
}

$backendProc = $null
if (Test-PortBusy $backendPort) {
    Write-Warning "El puerto $backendPort ya esta ocupado (probablemente el backend ya esta arrancado). No se inicia otro backend."
} elseif (-not (Test-Path $python)) {
    Write-Warning "No existe $python. Crea el venv: cd backend; python -m venv .venv; .venv\Scripts\pip install -r requirements-dev.txt"
} else {
    Write-Host "Arrancando backend en http://127.0.0.1:$backendPort ..." -ForegroundColor Cyan
    $backendProc = Start-Process -FilePath $python `
        -ArgumentList @('-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', "$backendPort") `
        -WorkingDirectory $backendDir -NoNewWindow -PassThru
}

try {
    if (Test-PortBusy $frontendPort) {
        Write-Warning "El puerto $frontendPort ya esta ocupado (probablemente el frontend ya esta arrancado). No se inicia otro."
    } else {
        Write-Host "Arrancando frontend en http://localhost:$frontendPort ..." -ForegroundColor Cyan
        Push-Location $frontendDir
        try {
            npm run dev
        } finally {
            Pop-Location
        }
    }
} finally {
    if ($backendProc -and -not $backendProc.HasExited) {
        Write-Host "Deteniendo backend (PID $($backendProc.Id))..." -ForegroundColor Cyan
        Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    }
}
