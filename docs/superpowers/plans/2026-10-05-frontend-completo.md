# Plano simples — frontend completo

> Atualização de 07/10/2026: o módulo de integradores, sua API e seus recibos foram retirados. As referências a esse módulo nesta entrega registram decisões anteriores e não descrevem funções disponíveis. As conexões de Accounts, eventos e contato permanecem.

> Executar com `executing-plans`, diretamente conforme fluxo de plano simples autorizado. Uma única revisão independente ao final.

**Objetivo:** todas as telas dos módulos com a linguagem visual das referências, login em `/`, index e tela Usuários protegida.
**Spec:** [desenho](../specs/2026-10-05-frontend-completo-design.md).
**Arquitetura:** Django/templates/CSS/SVG/JS existentes; sem dependências novas/modelos/API; base53fd580, branch feat/frontend-completo.

## Restrições

Dados/políticas reais; logs e imagens das referências não entram no produto. Logos vazias. Login preservado visualmente, identidade movida para perfil. Montserrat local/OFL provisória. Logout POST/CSRF e `next` seguro. Conta técnica não ganha privilégios por alteração visual. Conservar as regras/versão de escrita dos módulos.

## 1. Rotas, navegação e base

- [x] RED: login raiz200, index privado, entrada padrão/index/alias e `next` seguro, perfil, menus compartilhados, público sem dados privados.
- [x] `accounts/urls.py`, settings/core urls, `core/navigation.py` context processor; menu extraído do Dashboard, `core/base` com blocks de layout/extra_head/mensagens, catalogo/base interno e core/public-base; CSS compartilhado em módulos.css; atualizar testes antigos de rotas.
- [x] GREEN suite/check/drift; commit português.

## 2. Usuários

- [x] RED autorização vigente (super ativo), staff/perms comuns negados, contagens/filtros/paginação/escape, Administrar contas/menu apontam `/usuarios/`.
- [x] `accounts/user_views.py`, templates de usuários com cartões/contadores/abas/busca15 por página; configurações técnicas somente via acesso autorizado existente. Pergunta opcional sem resposta: preservar a autoridade técnica vigente.
- [x] GREEN suite/check; commit português.

## 3. Tarefas e agenda

- [x] RED filtros/contagens sem tarefas alheias, querystring preservado; calendário domingo primeiro, busca/categoria, reserva na virada/meia-noite/cancelados/paginação.
- [x] Views/seletores aplicam filtros reais; contadores e tabs. Templates Kanban/calendário, formulário/detalhe com barra e histórico, erros e confirmações na base; preservar transições/versão/CSRF.
- [x] GREEN suite e Chrome básico; commit português.

## 4. Materiais, banners e demais páginas

- [x] RED status/categoria/busca/tab/counts/escape/paginação/proteção de banners; smoke render das telas restantes.
- [x] Tabelas/contadores/thumbnails/abas com dados atuais. Catálogo/integrações/perfil/público/formulários/confirmações/históricos e 403/404/500 coerentes, sem controles cenográficos.
- [x] GREEN suite/check/drift/pip; Chrome completo, capturas e comparação; commit português.

## 5. Revisão e entrega

- [x] Uma revisão independente read-only. Regraduar; Important/Critical em uma passada RED/GREEN; menores registrados.
- [x] Guia com cenários/testes/limitações, README/AGENTS/spec/plan e decisões atualizados; commits. Encerrar navegador/servidor; remover somente temporários desta tarefa se a ferramenta permitir, sem contornar rejeições.
- [x] Status final limpo; entrega local, aguardar depuração.

## Resultado da execução

309 testes passaram; 45 rotas no Chrome e 155 cenários de layout/papel/menu. Uma revisão independente: retorno circular no login e horário de continuação da reserva corrigidos RED→GREEN, suíte309/309 e confirmação no navegador. Menor adiado: quebra de rótulos longos em contadores. Decisões e custos preservados no [guia da entrega](../../frontend/02-paginas-e-usuarios.md#decisões-da-execução). Figma recusou acesso; PNGs autorizados, Group17 não verificável. Commits locais; aguardar depuração. Nenhuma segunda revisão.

## Foco da revisão

Encerramento: navegador e servidor temporário fechados. A aprovação automática rejeitou a remoção de `.superpowers/sdd/2026-10-05-frontend-completo/` com `blocked by policy`; os temporários permanecem ignorados pelo Git. A rejeição foi respeitada e registrada no guia.

1. Login raiz, aliases, `next` e conta desativada não causam loop, retorno externo ou acesso indevido.
2. Usuários e contagens/filtros de módulos nunca ampliam permissões, inclusive staff ou admin de negócio sem autoridade técnica.
3. Reservas de múltiplos dias/meia-noite e paginação preservam calendário correto sem expor cancelados.
4. Sidebar expandida e dados longos em768/820/360 não escondem controles, foco, mensagens ou dias.
5. Forms/confirmations/actions preservam CSRF, versão e validação; assets/avatars/empty states funcionam sem Referencias ou CDN e sem dados fictícios.
