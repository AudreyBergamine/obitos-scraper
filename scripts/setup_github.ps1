# Conecta o repositório local ao GitHub e envia o código.
# Pré-requisito: gh auth login (executar uma vez antes deste script)

$ErrorActionPreference = "Stop"

$git = "C:\Program Files\Git\bin\git.exe"
$gh = "C:\Program Files\GitHub CLI\gh.exe"
$repoName = "obitos-scraper"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Set-Location $projectRoot

Write-Host "Verificando autenticação GitHub..." -ForegroundColor Cyan
& $gh auth status
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Execute primeiro: gh auth login" -ForegroundColor Yellow
    Write-Host "Depois rode este script novamente." -ForegroundColor Yellow
    exit 1
}

if (-not (Test-Path ".git")) {
    Write-Host "Inicializando repositório git..." -ForegroundColor Cyan
    & $git init
    & $git branch -M main
}

$remoteUrl = & $gh repo view $repoName --json url -q .url 2>$null
if (-not $remoteUrl) {
    Write-Host "Criando repositório no GitHub: $repoName" -ForegroundColor Cyan
    & $gh repo create $repoName `
        --private `
        --source . `
        --remote origin `
        --description "Pipeline de coleta e estruturação de obituários públicos brasileiros" `
        --push
} else {
    Write-Host "Repositório já existe: $remoteUrl" -ForegroundColor Green
    $existing = & $git remote get-url origin 2>$null
    if (-not $existing) {
        & $git remote add origin "https://github.com/$( & $gh api user -q .login)/$repoName.git"
    }
    & $git push -u origin main
}

Write-Host ""
Write-Host "Concluído! Repositório:" -ForegroundColor Green
& $gh repo view $repoName --web 2>$null | Out-Null
& $gh repo view $repoName --json url -q .url
