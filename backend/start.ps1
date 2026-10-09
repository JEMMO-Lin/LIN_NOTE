﻿﻿﻿# KnowFlow 一键启动脚本
# 用法：在 backend 目录下执行 .\start.ps1
# 功能：自动创建 venv → 安装依赖 → 生成 .env → 迁移数据库 → 启动 API
# MVP 单机模式：SQLite + 可选 Redis/ChromaDB，无需 Docker

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

# 辅助：以 Continue 策略执行 native 命令，屏蔽 stderr 误报，返回退出码
function Invoke-Native {
    param([scriptblock]$Block)
    try {
        $ErrorActionPreference = "Continue"
        & $Block
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = "Stop"
    }
}

Write-Host "===== KnowFlow 启动 =====" -ForegroundColor Cyan

# 1. 虚拟环境
$venvPath = Join-Path $root ".venv"
$activateScript = Join-Path $venvPath "Scripts\Activate.ps1"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$venvHealthy = $false
if ((Test-Path $activateScript) -and (Test-Path $venvPython)) {
    $rc = Invoke-Native { & $venvPython --version 2>&1 | Out-Null }
    $venvHealthy = $rc -eq 0
}
if (-not $venvHealthy) {
    Write-Host "[1/4] 创建虚拟环境..." -ForegroundColor Yellow
    if (Test-Path $venvPath) { Remove-Item $venvPath -Recurse -Force }
    python -m venv $venvPath
}
& $activateScript

# 2. 依赖
Write-Host "[2/4] 安装依赖..." -ForegroundColor Yellow
$rc = Invoke-Native { pip install -r (Join-Path $root "requirements.txt") --disable-pip-version-check 2>&1 | Out-Null }
if ($rc -ne 0) {
    Write-Host "`n[错误] 依赖安装失败（退出码 $rc），请检查 requirements.txt 或网络后重试" -ForegroundColor Red
    Write-Host "提示：可删除 .venv 目录后重新运行本脚本" -ForegroundColor Yellow
    exit 1
}

# 3. .env
$envFile = Join-Path $root ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "[3/4] 生成 .env..." -ForegroundColor Yellow
    Copy-Item (Join-Path $root ".env.example") $envFile
}

# 4. 数据库迁移 + 启动（SQLite 单文件，无需外部服务）
Write-Host "[4/4] 数据库迁移（SQLite）..." -ForegroundColor Yellow
$alembic = Join-Path $venvPath "Scripts\alembic.exe"
$alembicIni = Join-Path $root "alembic.ini"
$versionsDir = Join-Path $root "alembic\versions"
$versions = Get-ChildItem $versionsDir -Filter "*.py" -ErrorAction SilentlyContinue
if (-not $versions) {
    Write-Host "  生成初始迁移..." -ForegroundColor Gray
    $rc = Invoke-Native { & $alembic -c $alembicIni revision --autogenerate -m "init" 2>&1 | Out-Null }
    if ($rc -ne 0) {
        Write-Host "`n[错误] 生成迁移失败，请检查模型定义" -ForegroundColor Red
        exit 1
    }
}
$rc = Invoke-Native { & $alembic -c $alembicIni upgrade head 2>&1 | Out-Null }
if ($rc -ne 0) {
    Write-Host "`n[错误] 数据库迁移失败（退出码 $rc）" -ForegroundColor Red
    exit 1
}

Write-Host "`n启动 API 服务..." -ForegroundColor Cyan
Write-Host "API 文档: http://localhost:8000/docs" -ForegroundColor Green
Write-Host "数据库: SQLite (knowflow.db)`n" -ForegroundColor Gray
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
