param(
    [string]$BaseUrl = 'http://127.0.0.1:8000',
    [string]$Session = 'ajustes-layout'
)

$ErrorActionPreference = 'Stop'
$failures = [System.Collections.Generic.List[string]]::new()
$checks = 0
$probe = Join-Path $PSScriptRoot 'medir-sidebar-calendario.js'

function Invoke-Browser {
    param([string[]]$BrowserArgs)
    $output = & npx.cmd --no-install agent-browser --session $Session @BrowserArgs
    if ($LASTEXITCODE -ne 0) { throw "Falha no navegador: $($BrowserArgs -join ' ')" }
    return $output
}

function Read-Layout {
    $output = Get-Content -Raw -Encoding UTF8 $probe | & npx.cmd --no-install agent-browser --session $Session eval --stdin
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao medir a página.' }
    return ($output -join "`n" | ConvertFrom-Json)
}

function Assert-Layout {
    param([bool]$Condition, [string]$Message)
    $script:checks++
    if (!$Condition) { $script:failures.Add($Message) }
}

# Requer sessão autenticada. Usa apenas navegação e preferência local; não grava dados de negócio.
Invoke-Browser -BrowserArgs @('set', 'viewport', '1366', '900') | Out-Null
Invoke-Browser -BrowserArgs @('open', "$BaseUrl/index/") | Out-Null
"localStorage.removeItem('inovalab.sidebar.expanded')" | & npx.cmd --no-install agent-browser --session $Session eval --stdin | Out-Null
Invoke-Browser -BrowserArgs @('open', "$BaseUrl/index/") | Out-Null
$layout = Read-Layout
if ($layout.path -ne '/index/') { throw 'Entre no sistema nesta sessão antes de executar.' }
Assert-Layout (!$layout.expanded) 'Primeiro acesso deve iniciar recolhido.'
Assert-Layout ($layout.status -eq 200) 'Dashboard deve responder HTTP 200.'
Assert-Layout (@($layout.centers | Where-Object { [Math]::Abs($_) -gt 0.5 }).Count -eq 0) 'Ícones recolhidos devem estar centralizados.'
Assert-Layout (($layout.legend.label -join ',') -eq 'Recesso,Feriado,Evento') 'Legenda deve exibir Recesso, Feriado e Evento.'
Assert-Layout (($layout.legend.color -join ',') -eq 'rgb(118, 184, 42),rgb(0, 163, 216),rgb(235, 27, 35)') 'Legenda deve usar verde, azul e vermelho nesta ordem.'
Assert-Layout (@($layout.logos | Where-Object loaded).Count -gt 0) 'Logo deve carregar na sidebar.'

Invoke-Browser -BrowserArgs @('click', '.sidebar-toggle') | Out-Null
Invoke-Browser -BrowserArgs @('open', "$BaseUrl/banners/") | Out-Null
$layout = Read-Layout
Assert-Layout ($layout.expanded -and $layout.cached -eq 'true') 'Menu aberto deve persistir ao navegar.'
Invoke-Browser -BrowserArgs @('open', "$BaseUrl/banners/") | Out-Null
Assert-Layout ((Read-Layout).expanded) 'Menu aberto deve persistir ao atualizar.'
if ((Read-Layout).expanded) { Invoke-Browser -BrowserArgs @('click', '.sidebar-toggle') | Out-Null }
Invoke-Browser -BrowserArgs @('open', "$BaseUrl/publico/") | Out-Null
$layout = Read-Layout
Assert-Layout ($layout.sidebar -and $layout.header -and $layout.footer) 'Páginas deve manter sidebar, cabeçalho e rodapé.'
Assert-Layout ($layout.status -eq 200) 'Páginas deve responder HTTP 200.'
Assert-Layout (!$layout.expanded -and $layout.cached -eq 'false') 'Menu fechado deve persistir ao navegar.'
Assert-Layout ($layout.overflow -le 1) 'Páginas não deve transbordar horizontalmente.'
Invoke-Browser -BrowserArgs @('open', "$BaseUrl/publico/sobre/") | Out-Null
$layout = Read-Layout
Assert-Layout ($layout.sidebar -and $layout.header -and $layout.footer) 'Sobre deve manter estrutura interna após login.'
Assert-Layout ($layout.status -eq 200) 'Sobre deve responder HTTP 200.'

Invoke-Browser -BrowserArgs @('set', 'viewport', '360', '800') | Out-Null
Invoke-Browser -BrowserArgs @('open', "$BaseUrl/index/") | Out-Null
Invoke-Browser -BrowserArgs @('click', '.mobile-menu') | Out-Null
Invoke-Browser -BrowserArgs @('open', "$BaseUrl/publico/") | Out-Null
$layout = Read-Layout
Assert-Layout ($layout.expanded) 'Menu aberto deve persistir no celular.'
Invoke-Browser -BrowserArgs @('press', 'Escape') | Out-Null
Invoke-Browser -BrowserArgs @('open', "$BaseUrl/index/") | Out-Null
$layout = Read-Layout
Assert-Layout (!$layout.expanded -and $layout.cached -eq 'false') 'Fechar com Escape deve persistir no celular.'
Assert-Layout ($layout.overflow -le 1) 'Dashboard móvel não deve transbordar horizontalmente.'

[pscustomobject]@{ checks = $checks; failures = $failures.ToArray() } | ConvertTo-Json -Depth 4
if ($failures.Count) { exit 1 }

