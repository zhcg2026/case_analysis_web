# 服务器部署脚本
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   代码上传到服务器部署流程" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "✅ 代码已提交到本地 Git!" -ForegroundColor Green
Write-Host ""
Write-Host "请按以下步骤操作：" -ForegroundColor Yellow
Write-Host ""
Write-Host "步骤 1: 推送到远程 Git 仓库" -ForegroundColor Cyan
Write-Host "  git push origin main" -ForegroundColor White
Write-Host ""
Write-Host "步骤 2: SSH 连接到服务器" -ForegroundColor Cyan
Write-Host "  ssh root@81.70.163.116" -ForegroundColor White
Write-Host ""
Write-Host "步骤 3: 在服务器上执行" -ForegroundColor Cyan
Write-Host "  cd /root/case_analysis_web" -ForegroundColor White
Write-Host "  git pull origin main" -ForegroundColor White
Write-Host "  ./quick_deploy.sh" -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "详细说明请查看 LOCAL_TO_SERVER_DEPLOY.md" -ForegroundColor Gray
Write-Host "========================================" -ForegroundColor Cyan
