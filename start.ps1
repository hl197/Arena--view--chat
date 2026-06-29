# ──────────────────────────────────────────────────────────
#  ArenaView 一键启动脚本 (PowerShell)
#  启动后端 (FastAPI :8000) + 前端 (Vite :5173)
#  用法: .\start.ps1
# ──────────────────────────────────────────────────────────
$ErrorActionPreference = "Stop"

$ROOT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND_DIR = "$ROOT_DIR\backend"
$FRONTEND_DIR = "$ROOT_DIR\frontend"

# ── 横幅 ─────────────────────────────────────────────
Write-Host ""
Write-Host "   ╔══════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "   ║        ArenaView  多视角决策       ║" -ForegroundColor Cyan
Write-Host "   ╚══════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# ── 清理函数 ─────────────────────────────────────────
$BACKEND_PID = $null
$FRONTEND_PID = $null

function Cleanup {
    Write-Host "`n🛑 正在关闭服务..." -ForegroundColor Yellow

    if ($BACKEND_PID) {
        try { Stop-Process -Id $BACKEND_PID -Force -ErrorAction SilentlyContinue } catch {}
        Write-Host "   ✓ 后端已关闭" -ForegroundColor Green
    }
    if ($FRONTEND_PID) {
        try { Stop-Process -Id $FRONTEND_PID -Force -ErrorAction SilentlyContinue } catch {}
        Write-Host "   ✓ 前端已关闭" -ForegroundColor Green
    }

    Write-Host "👋 ArenaView 已停止" -ForegroundColor Green
}

# 注册 Ctrl+C 处理
try {
    [Console]::TreatControlCAsInput = $false
} catch {}
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Cleanup }

# ── 环境检查 ─────────────────────────────────────────
Write-Host "📋 检查环境..." -ForegroundColor Cyan

# Python
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) { $python = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $python) {
    Write-Host "❌ 未找到 Python" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Python: $(python --version)" -ForegroundColor Green

# Node
$node = Get-Command node -ErrorAction SilentlyContinue
if (-not $node) {
    Write-Host "❌ 未找到 Node.js" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Node:   $(node --version)" -ForegroundColor Green
Write-Host "✓ npm:    $(npm --version)" -ForegroundColor Green

# ── 环境变量 ─────────────────────────────────────────
if (Test-Path "$ROOT_DIR\.env") {
    Get-Content "$ROOT_DIR\.env" | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith("#") -and $line.Contains("=")) {
            $parts = $line.Split("=", 2)
            $key = $parts[0].Trim()
            $value = $parts[1].Trim()
            [Environment]::SetEnvironmentVariable($key, $value, "Process")
        }
    }
    Write-Host "✓ 已加载 .env" -ForegroundColor Green
} else {
    Write-Host "⚠ 未找到 .env 文件" -ForegroundColor Yellow
}

# ── 依赖检查 ─────────────────────────────────────────
Write-Host "📦 检查依赖..." -ForegroundColor Yellow

# 前端 npm
if (-not (Test-Path "$FRONTEND_DIR\node_modules")) {
    Write-Host "   安装前端依赖..." -ForegroundColor Yellow
    Push-Location $FRONTEND_DIR
    npm install
    Pop-Location
    Write-Host "   ✓ 前端依赖已安装" -ForegroundColor Green
} else {
    Write-Host "   ✓ 前端依赖已就绪" -ForegroundColor Green
}

# ── 启动后端 ─────────────────────────────────────────
Write-Host "🔧 启动后端 (FastAPI :8000)..." -ForegroundColor Cyan

$backendProc = Start-Process -FilePath "python" `
    -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload" `
    -WorkingDirectory $ROOT_DIR `
    -PassThru `
    -NoNewWindow

$BACKEND_PID = $backendProc.Id

# 等待后端就绪
Write-Host -NoNewline "   等待后端就绪"
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:8000/health" -UseBasicParsing -TimeoutSec 1
        $ready = $true
        break
    } catch {}
    Write-Host -NoNewline "."
    Start-Sleep -Milliseconds 500
}
if ($ready) {
    Write-Host "`n   ✓ 后端就绪 (http://localhost:8000)" -ForegroundColor Green
} else {
    Write-Host "`n   ⚠ 后端可能未完全启动" -ForegroundColor Yellow
}

# ── 启动前端 ─────────────────────────────────────────
Write-Host "🎨 启动前端 (Vite :5173)..." -ForegroundColor Cyan

$frontendProc = Start-Process -FilePath "npm" `
    -ArgumentList "run", "dev" `
    -WorkingDirectory $FRONTEND_DIR `
    -PassThru `
    -NoNewWindow

$FRONTEND_PID = $frontendProc.Id

# 等待前端就绪
Write-Host -NoNewline "   等待前端就绪"
$ready = $false
for ($i = 0; $i -lt 20; $i++) {
    try {
        $null = Invoke-WebRequest -Uri "http://localhost:5173" -UseBasicParsing -TimeoutSec 1
        $ready = $true
        break
    } catch {}
    Write-Host -NoNewline "."
    Start-Sleep -Seconds 1
}
if ($ready) {
    Write-Host "`n   ✓ 前端就绪 (http://localhost:5173)" -ForegroundColor Green
} else {
    Write-Host "`n   ⚠ 前端可能未完全启动" -ForegroundColor Yellow
}

# ── 完成 ─────────────────────────────────────────────
Write-Host ""
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host "  ArenaView 运行中！" -ForegroundColor Green
Write-Host ""
Write-Host "  🌐 前端:  http://localhost:5173" -ForegroundColor Cyan
Write-Host "  🔧 后端:  http://localhost:8000" -ForegroundColor Cyan
Write-Host "  📚 API:   http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""
Write-Host "  按 Ctrl+C 停止所有服务" -ForegroundColor Yellow
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Green
Write-Host ""

# 阻塞等待
try {
    while ($true) {
        Start-Sleep -Seconds 2
        if ($backendProc.HasExited -and $frontendProc.HasExited) {
            break
        }
    }
} finally {
    Cleanup
}
