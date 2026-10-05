# Plano simples — base visual e Dashboard

> Executar diretamente com `executing-plans`, conforme fluxo de plano simples autorizado. Entregar somente a primeira parte visual e aguardar depuração.

**Objetivo:** base visual e `/painel/` fiel à geometria do Dashboard/sidebar, com dados e permissões reais.
**Spec:** [desenho](../specs/2026-10-05-frontend-referencias-design.md).
**Arquitetura:** Django/templates/CSS/SVG/JS em core, seletores existentes, sem novos modelos/APIs; branch feat/frontend-painel, base9ac6418.

## Restrições

- Manter login/raiz de identidade; link para Dashboard. Outros módulos conservam conteúdos até sua entrega visual.
- Fonte/logos originais não fornecidos até este registro; Montserrat/OFL local e PNGs originais via recorte CSS, escolhas técnicas com fidelidade a verificar.
- Tarefas restritas por responsável/admin; reservas/calendário nunca expõem agenda ao comum. Logout POST/CSRF; no-store.
- Sem recursos novos das imagens. Menus/abas são rotas/filtros reais; sem dados fictícios ou indicadores de feriados/recessos.

## 1. Consulta e acesso

- [ ] RED tests core: anon/inativo, staff/comum/tarefa alheia/excluída, admin real, filtros/status/período/limites, calendário seis meses/domingo/virada de ano/limites exatos, estados vazios, HTML escapado, no-store, menus e CSRF.
- [ ] `core/dashboard.py` dashboard_context(actor,now=None,task_tab='pendentes',booking_tab='semana') normaliza filtros e aplica seletores; seis meses/badges/reservas, UIquery em core/views e core/urls. GET/HEAD somente.
- [ ] GREEN módulo/suíte/check/drift; commit `feat (core): adiciona dashboard com consultas autorizadas.`.

## 2. Base visual

- [ ] Templates core/base/dashboard/sidebar/icon, core/static/core/{painel.css,painel.js,assets}; SVG próprios, Montserrat/OFL local e PNGs originais para marcas; link Dashboard identidade.
- [ ] Geometria1920/sidebar79/header74/content1436/panels630, expansão283, tabs/card/footer; responsive1366/360, scroll interno e textos longos.
- [ ] Chrome com fixtures próprias: estado real, links/filtros, sidebar/escape/teclado, perfil/logout, 1920/1366/360, comum/admin, fontes/imagens/erros. Capturar e inspecionar screenshots; apagar só fixtures próprias; fechar servidor/navegador.
- [ ] GREEN suíte/check/drift/pip/diff; commit `feat (frontend): reproduz base visual e dashboard das referências.`.

## 3. Revisão e entrega

- [ ] Uma revisão read-only independente; Important/Critical em uma passada RED/GREEN; menores registrados.
- [ ] Guia docs/frontend/01-base-e-dashboard.md, README e orientação visual atualizados; registrar diferenças/scope/roteiro e decisões do ledger.
- [ ] Checks finais, commit português, limpar scratch próprio; branch local, aguardar depuração.

## Foco da revisão

1. Usuário comum/staff não vê reservas, contadores/dias ocupados ou tarefas alheias por abas/querystring/menu.
2. Virada de mês/ano, fim à meia-noite, início/fim semana e cancelados não contam incorretamente.
3. Expansão/mobile/perfil não tornam logout inseguro, escondem foco ou deixam controles sem nome/acesso por teclado.
4. Texto longo/nomes e listas vazias preservam responsividade, sem HTML injetado ou dados fictícios.
5. Assets locais continuam acessíveis em clone sem Referencias; fonte/licença/carregamento/marcas não dependem de recursos externos no navegador.
