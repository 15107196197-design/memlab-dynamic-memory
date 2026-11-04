$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $env:OLLAMA_URL) { $env:OLLAMA_URL = 'http://127.0.0.1:11434' }
try {
    $models = (Invoke-RestMethod -Uri ($env:OLLAMA_URL.TrimEnd('/') + '/api/tags') -TimeoutSec 5).models.name
} catch {
    Write-Host '无法连接本机 Ollama，请先启动 Ollama。' -ForegroundColor Red
    exit 1
}
if (-not ($models -match '^bge-m3(:|$)')) { Write-Warning '未发现 bge-m3；请运行 ollama pull bge-m3。' }
if (-not $env:MEMORY_MODEL) { $env:MEMORY_MODEL = 'qwen3.8:27b-q4_K_M' }
if ($models -notcontains $env:MEMORY_MODEL) { Write-Warning "未发现回答模型 $env:MEMORY_MODEL；请安装该模型或设置 MEMORY_MODEL。" }
Write-Host '浏览器地址：http://127.0.0.1:8765'
python app.py
