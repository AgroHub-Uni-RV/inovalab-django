param(
    [string]$BaseUrl = 'http://127.0.0.1:8000',
    [string]$Session = 'padroes-visuais',
    [int[]]$Widths = @(1920, 1440, 1366, 1201, 820, 768, 360),
    [string[]]$Paths = @('/index/', '/usuarios/', '/tarefas/', '/tarefas/nova/', '/agenda/', '/agenda/novo/', '/materiais/', '/materiais/novo/', '/banners/', '/banners/novo/', '/catalogo/servicos/', '/catalogo/equipamentos/', '/integracoes/', '/perfil/', '/publico/'),
    [string]$OutputPath = ''
)

# Use uma sessão já autenticada; o script apenas consulta as páginas.
$ErrorActionPreference = 'Stop'
$rows = [System.Collections.Generic.List[object]]::new()
foreach ($width in $Widths) {
    & npx.cmd --no-install agent-browser --session $Session set viewport $width 1080 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Não foi possível configurar o navegador.' }
    foreach ($path in $Paths) {
        & npx.cmd --no-install agent-browser --session $Session open ($BaseUrl.TrimEnd('/') + $path) | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Falha ao abrir $path" }
        $result = Get-Content -Raw -Encoding UTF8 -LiteralPath (Join-Path $PSScriptRoot 'medir-padroes-visuais.js') |
            & npx.cmd --no-install agent-browser --session $Session eval --stdin
        if ($LASTEXITCODE -ne 0) { throw "Falha ao medir $path" }
        foreach ($row in ($result | ConvertFrom-Json)) {
            if ($row.path -ne $path) { throw "Acesso a $path redirecionou para $($row.path); confira a autenticação/permissão." }
            $rows.Add($row)
        }
    }
}

$failures = [System.Collections.Generic.List[string]]::new()
foreach ($row in $rows) {
    $context = "$($row.path) $($row.width)px $($row.mode)"
    if ($row.status -ne 200) { $failures.Add("${context}: resposta HTTP $($row.status)") }
    if ($row.overflow -gt 1) { $failures.Add("${context}: transbordamento externo") }
    if ($row.brokenImages) { $failures.Add("${context}: imagem quebrada") }
    if ($row.clippedDashboardControls.Count) { $failures.Add("${context}: controles do Dashboard ultrapassam seu espaço: $($row.clippedDashboardControls -join ', ')") }
    if ($row.clippedActiveTabs.Count) { $failures.Add("${context}: indicador da aba ativa oculto: $($row.clippedActiveTabs -join ', ')") }
    if ($row.clippedStatLabels.Count) { $failures.Add("${context}: rótulos maiores que o espaço do contador: $($row.clippedStatLabels -join ', ')") }
    if ($row.taskNumberGaps | Where-Object { $_.actual + 1 -lt $_.expected }) { $failures.Add("${context}: ID ocupa o espaço do título da tarefa") }
    if (-not $row.fontLoaded -or $row.body.font -notmatch 'Montserrat') { $failures.Add("${context}: Montserrat não carregada") }
    if ($row.header -and $row.width -gt 760) {
        if ([Math]::Abs($row.container.left - $row.header.left) -gt 1 -or [Math]::Abs($row.container.width - $row.header.width) -gt 1) {
            $failures.Add("${context}: conteúdo desalinhado do cabeçalho")
        }
    }
    if ($row.container -and $row.footer -and ([Math]::Abs($row.container.left - $row.footer.left) -gt 1 -or [Math]::Abs($row.container.width - $row.footer.width) -gt 1)) {
        $failures.Add("${context}: conteúdo desalinhado do rodapé")
    }
    if ($row.filter -and ($row.filter.padding | Where-Object { $_ -ne '0px' })) {
        $failures.Add("${context}: filtros com margem interna exclusiva")
    }
}

# Componentes equivalentes devem conservar suas medidas em todos os módulos.
foreach ($group in ($rows | Where-Object { $_.card } | Group-Object width, mode)) {
    foreach ($component in @('statistics', 'card', 'statTitle', 'statNumber', 'statIcon')) {
        $baseline = $group.Group[0].$component
        foreach ($row in $group.Group) {
            $actual = $row.$component
            foreach ($property in @('radius', 'gap', 'size', 'weight')) {
                if ($actual.$property -ne $baseline.$property) {
                    $failures.Add("$($row.path) $($group.Name): $component.$property diferente dos outros módulos")
                }
            }
            if (($actual.padding -join ',') -ne ($baseline.padding -join ',')) {
                $failures.Add("$($row.path) $($group.Name): padding de $component diferente dos outros módulos")
            }
        }
    }
}
foreach ($group in ($rows | Group-Object width, mode)) {
    foreach ($component in @('heading', 'field', 'button')) {
        $withComponent = @($group.Group | Where-Object { $_.$component })
        if ($withComponent.Count -lt 2) { continue }
        $baseline = $withComponent[0].$component
        foreach ($row in $withComponent) {
            foreach ($property in @('font', 'size', 'radius')) {
                if ($row.$component.$property -ne $baseline.$property) {
                    $failures.Add("$($row.path) $($group.Name): $component.$property diferente dos outros módulos")
                }
            }
        }
    }
}
if ($OutputPath) { $rows | ConvertTo-Json -Depth 6 | Set-Content -Encoding UTF8 -LiteralPath $OutputPath }
@{ checked = $rows.Count; failures = @($failures) } | ConvertTo-Json -Depth 4
if ($failures.Count) { exit 1 }
