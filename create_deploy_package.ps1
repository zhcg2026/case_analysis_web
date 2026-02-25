# 创建部署包脚本
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   创建部署包" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查必要文件
$requiredFiles = @(
    "backend\app.py",
    "frontend\dist",
    "requirements.txt",
    "Dockerfile",
    "docker-compose.yml",
    "quick_deploy.sh"
)

Write-Host "检查必要文件..." -ForegroundColor Yellow
foreach ($file in $requiredFiles) {
    if (Test-Path $file) {
        Write-Host "  ✓ $file" -ForegroundColor Green
    } else {
        Write-Host "  ✗ $file" -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "创建部署包..." -ForegroundColor Yellow

# 复制文件到临时目录
$tempDir = "deploy_temp"
if (Test-Path $tempDir) {
    Remove-Item -Recurse -Force $tempDir
}
New-Item -ItemType Directory -Path $tempDir | Out-Null

# 复制文件
Copy-Item -Path "backend" -Destination "$tempDir\" -Recurse
Copy-Item -Path "frontend\dist" -Destination "$tempDir\frontend\" -Recurse
Copy-Item -Path "requirements.txt" -Destination "$tempDir\"
Copy-Item -Path "Dockerfile" -Destination "$tempDir\"
Copy-Item -Path "docker-compose.yml" -Destination "$tempDir\"
Copy-Item -Path "quick_deploy.sh" -Destination "$tempDir\"

# 创建压缩包
$packageName = "deploy_package_$(Get-Date -Format 'yyyyMMdd_HHmmss').zip"
Compress-Archive -Path "$tempDir\*" -DestinationPath $packageName -Force

# 清理临时目录
Remove-Item -Recurse -Force $tempDir

Write-Host ""
Write-Host "✅ 部署包创建成功!" -ForegroundColor Green
Write-Host "   文件: $packageName" -ForegroundColor White
Write-Host ""
Write-Host "下一步:" -ForegroundColor Yellow
Write-Host "  1. 使用 SCP 或 SFTP 上传 $packageName 到服务器" -ForegroundColor White
Write-Host "  2. 在服务器上执行:" -ForegroundColor White
Write-Host "     cd /root/case_analysis_web" -ForegroundColor Gray
Write-Host "     unzip $packageName" -ForegroundColor Gray
Write-Host "     ./quick_deploy.sh" -ForegroundColor Gray
Write-Host ""
