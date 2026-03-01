# 本地构建部署脚本
Write-Host "=== 本地构建部署脚本 ===" -ForegroundColor Green

# 1. 确认前端已构建
if (-not (Test-Path "frontend\dist")) {
    Write-Host "错误：前端未构建！请先运行 npm run build" -ForegroundColor Red
    exit 1
}

Write-Host "✅ 前端构建已确认" -ForegroundColor Green

# 2. 创建部署包目录
$deployDir = "deploy_package"
if (Test-Path $deployDir) {
    Remove-Item -Recurse -Force $deployDir
}
New-Item -ItemType Directory -Path $deployDir | Out-Null
New-Item -ItemType Directory -Path "$deployDir\backend" | Out-Null
New-Item -ItemType Directory -Path "$deployDir\frontend" | Out-Null

Write-Host "✅ 部署包目录已创建" -ForegroundColor Green

# 3. 复制必要文件
Copy-Item "backend\app.py" -Destination "$deployDir\backend\"
Copy-Item "frontend\dist" -Recurse -Destination "$deployDir\frontend\"
Copy-Item "docker-compose.yml" -Destination "$deployDir\"
Copy-Item "Dockerfile" -Destination "$deployDir\"
Copy-Item "requirements.txt" -Destination "$deployDir\"

Write-Host "✅ 文件已复制到部署包" -ForegroundColor Green

# 4. 显示部署包内容
Write-Host "`n📦 部署包内容：" -ForegroundColor Cyan
Get-ChildItem -Recurse $deployDir | Select-Object FullName

Write-Host "`n✅ 部署包创建完成！" -ForegroundColor Green
Write-Host "`n下一步操作：" -ForegroundColor Yellow
Write-Host "1. 将 $deployDir 目录上传到服务器 /root/case_analysis_web/"
Write-Host "2. 在服务器上执行：cd /root/case_analysis_web && docker-compose up -d --build"
