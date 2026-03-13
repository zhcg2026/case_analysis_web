# 本地开发环境启动脚本
# 使用说明:
# 1. 确保 Docker Desktop 没有运行 MySQL 数据库
# 2. 确保本地有 MySQL 数据库在运行
# 3. 在 PowerShell 中执行: .\start_local.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   城管案件分析系统 - 本地启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查是否有 .env.local 文件
if (-not (Test-Path ".env.local")) {
    Write-Host "错误: .env.local 文件不存在!" -ForegroundColor Red
    exit 1
}

# 加载环境变量
Write-Host "加载本地环境变量..." -ForegroundColor Yellow
Get-Content ".env.local" | ForEach-Object {
    if ($_ -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($matches[1], $matches[2])
        Write-Host "  设置: $($matches[1]) = $($matches[2])" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "准备启动服务..." -ForegroundColor Yellow
Write-Host ""
Write-Host "请分别在两个终端中执行以下命令:" -ForegroundColor Cyan
Write-Host ""
Write-Host "终端1 - 启动后端:" -ForegroundColor Green
Write-Host "  cd backend" -ForegroundColor White
Write-Host "  python app.py" -ForegroundColor White
Write-Host ""
Write-Host "终端2 - 启动前端:" -ForegroundColor Green
Write-Host "  cd frontend" -ForegroundColor White
Write-Host "  npm run dev" -ForegroundColor White
Write-Host ""
Write-Host "访问地址: http://localhost:5173/" -ForegroundColor Cyan
Write-Host ""
