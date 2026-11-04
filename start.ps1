# Check the local Ollama models, then start the workbench.
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not $env:OLLAMA_URL) { $env:OLLAMA_URL = 'http://127.0.0.1:11434' }
if (-not $env:MEMORY_MODEL) { $env:MEMORY_MODEL = 'qwen3.8:27b-q4_K_M' }
try {
    $models = (Invoke-RestMethod -Uri ($env:OLLAMA_URL.TrimEnd('/') + '/api/tags') -TimeoutSec 5).models.name
} catch {
    Write-Warning "无法连接 Ollama（$env:OLLAMA_URL）。浏览页面可用，问答需要先启动 Ollama。"
    $models = @()
}
if ($models -and -not ($models -match '^bge-m3(:|$)')) { Write-Warning '未发现 bge-m3，请运行 ollama pull bge-m3。' }
if ($models -and ($models -notcontains $env:MEMORY_MODEL)) { Write-Warning "未发现回答模型 $env:MEMORY_MODEL。" }
python server.py
