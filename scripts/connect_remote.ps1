# Conecta o repositório local a um repo já criado no GitHub e faz push.
# Uso: .\scripts\connect_remote.ps1 -RepoUrl "https://github.com/SEU_USUARIO/obitos-scraper.git"

param(
    [Parameter(Mandatory = $true)]
    [string]$RepoUrl
)

$ErrorActionPreference = "Stop"

$git = "C:\Program Files\Git\bin\git.exe"
$gh = "C:\Program Files\GitHub CLI\gh.exe"
$projectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Set-Location $projectRoot

if (-not (Test-Path ".git")) {
    & $git init
    & $git branch -M main
}

# Identidade git local (tenta obter do gh; senão usa placeholder)
if (Test-Path $gh) {
    $authOk = & $gh auth status 2>$null
    if ($LASTEXITCODE -eq 0) {
        $ghUser = & $gh api user -q .login
        & $git config user.name $ghUser
        & $git config user.email "$ghUser@users.noreply.github.com"
    }
}

$existing = & $git remote get-url origin 2>$null
if ($existing) {
    if ($existing -eq $RepoUrl) {
        Write-Host "Remote origin já configurado: $RepoUrl" -ForegroundColor Green
    } else {
        Write-Host "Atualizando origin: $existing -> $RepoUrl" -ForegroundColor Yellow
        & $git remote set-url origin $RepoUrl
    }
} else {
    & $git remote add origin $RepoUrl
    Write-Host "Remote origin adicionado: $RepoUrl" -ForegroundColor Green
}

Write-Host "Enviando branch main..." -ForegroundColor Cyan
& $git push -u origin main

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Pronto! Código publicado em:" -ForegroundColor Green
    Write-Host $RepoUrl -ForegroundColor White
} else {
    Write-Host ""
    Write-Host "Push falhou. Autentique-se e tente novamente:" -ForegroundColor Yellow
    Write-Host "  gh auth login" -ForegroundColor White
    Write-Host "  .\scripts\connect_remote.ps1 -RepoUrl `"$RepoUrl`"" -ForegroundColor White
    exit 1
}
