# Plano simples — base visual e Dashboard

> Executar diretamente com `executing-plans`, conforme fluxo de plano simples autorizado. Entregar somente a primeira parte visual e aguardar depuração.

**Objetivo:** base visual e `/painel/` fiel à geometria do Dashboard/sidebar, com dados e permissões reais.
**Spec:** [desenho](../specs/2026-10-05-frontend-referencias-design.md).
**Arquitetura:** Django/templates/CSS/SVG/JS em core, seletores existentes, sem novos modelos/APIs; branch feat/frontend-painel, base9ac6418.

## Restrições

- Manter login/raiz de identidade; link para Dashboard. Outros módulos conservam conteúdos até sua entrega visual.
- Fonte original não identificada; Montserrat/OFL local como escolha técnica. Responsável decidiu logos em branco e futura inclusão própria; reservar áreas sem marcas inventadas.
- Tarefas restritas por responsável/admin; reservas/calendário nunca expõem agenda ao comum. Logout POST/CSRF; no-store.
- Sem recursos novos das imagens. Menus/abas são rotas/filtros reais; sem dados fictícios ou indicadores de feriados/recessos.

## 1. Consulta e acesso

- [x] RED tests core: anon/inativo, staff/comum/tarefa alheia/excluída, admin real, filtros/status/período/limites, calendário seis meses/domingo/virada de ano/limites exatos, estados vazios, HTML escapado, no-store, menus e CSRF.
- [x] `core/dashboard.py` dashboard_context(actor,now=None,task_tab='pendentes',booking_tab='semana') normaliza filtros e aplica seletores; seis meses/badges/reservas, UIquery em core/views e core/urls. GET/HEAD somente.
- [x] GREEN módulo/suíte/check/drift; commit `feat (core): adiciona dashboard com consultas autorizadas.`.

## 2. Base visual

- [x] Templates core/base/dashboard/sidebar/icon, core/static/core/{painel.css,painel.js,assets}; SVG próprios, Montserrat/OFL local e espaços vazios para logos; link Dashboard identidade.
- [x] Geometria1920/sidebar79/header74/content1436/panels630, expansão283, tabs/card/footer; responsive1366/360, scroll interno e textos longos.
- [x] Chrome com fixtures próprias: estado real, links/filtros, sidebar/escape/teclado, perfil/logout, 1920/1366/360, comum/admin, fontes/imagens/erros. Capturar e inspecionar screenshots; apagar só fixtures próprias; fechar servidor/navegador.
- [x] GREEN suíte/check/drift/pip/diff; commit `feat (frontend): reproduz base visual e dashboard das referências.`.

## 3. Revisão e entrega

- [x] Uma revisão read-only independente; Important/Critical em uma passada RED/GREEN; menores registrados.
- [x] Guia docs/frontend/01-base-e-dashboard.md, README e orientação visual atualizados; registrar diferenças/scope/roteiro e decisões do ledger.
- [x] Checks finais, commit português; branch local, aguardar depuração.
- [ ] Limpar scratch próprio: aprovação automática rejeitou a exclusão, mesmo por caminhos explícitos (`blocked by policy`). Pasta ignorada mantida para remoção manual; servidor e navegador encerrados.

## Foco da revisão

1. Usuário comum/staff não vê reservas, contadores/dias ocupados ou tarefas alheias por abas/querystring/menu.
2. Virada de mês/ano, fim à meia-noite, início/fim semana e cancelados não contam incorretamente.
3. Expansão/mobile/perfil não tornam logout inseguro, escondem foco ou deixam controles sem nome/acesso por teclado.
4. Texto longo/nomes e listas vazias preservam responsividade, sem HTML injetado ou dados fictícios.
5. Assets locais continuam acessíveis em clone sem Referencias; fonte/licença/carregamento/marcas não dependem de recursos externos no navegador.

## Resultado e decisões registradas

Entrega local na branch `feat/frontend-painel`: base e Dashboard, 12 testes novos e suíte completa 282/282, checks/migrações/dependências sem pendências. Chrome 1920/1366/360 e, após correção da revisão, 768/820 com ambos os papéis e menu expandido/recolhido. [Guia e capturas](../../frontend/01-base-e-dashboard.md).

Decisões do ledger, em ordem:

1. Plano direto e primeira entrega somente base/Dashboard, com funcionalidades atuais. **Custo:** as outras telas dependem de entregas posteriores autorizadas.
2. Dashboard em `/painel/`, preservando identidade/login e migrando os outros layouts depois. **Custo:** aparência temporariamente diferente entre telas.
3. Fonte não identificada: Montserrat local/OFL provisória. A proposta inicial de recortar marcas dos PNGs foi **substituída pela resposta do responsável**, que pediu áreas vazias e inserirá as logos futuramente. **Custo:** fonte/ícones podem exigir refinamento quando houver assets originais; marcas ficam pendentes.
4. Branch no checkout da IDE e ledger em PowerShell, sem novo worktree/framework/domínio; manter a branch local para depuração conforme o fluxo fracionado. **Custo:** registro manual e integração da branch em etapa posterior; verificação restrita aos ambientes exercitados.
5. Template funcional simples no commit intermediário, substituído pelo visual final após validar consultas/permissões. **Custo:** somente a apresentação do commit intermediário, sem efeito na entrega final.

Revisão independente única por `gpt-6-astra/high`, intervalo `9ac6418..2565f51`, sem Critical e sem itens recusados para julgamento. Um Important de transbordamento em tablet com sidebar expandida foi corrigido em uma passada: script de regressão RED em768 → GREEN nas oito combinações de 768/820 × admin/comum × expandido/recolhido; suíte 282/282. Correção commit `47e63ee`. Sem nova rodada de revisão.

Menores adiados:

- Reserva vermelha prevalece sobre a marca azul de hoje; texto acessível conserva ambos. Acrescentar marca visual combinada posteriormente.
- `OFL.txt` original tem espaço final na linha21; comparação da branch inteira sinaliza essa formatação da licença. Sem impacto funcional; formatação preservada.

Não iniciar outra tela antes da depuração/autorização do responsável. Tarefa futura explícita: **responsável inserir logos InovaLab, AgroHub e YpêTec**.
