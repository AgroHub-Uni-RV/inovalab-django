# Gerenciamento e execução de agendamentos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Organizar o gerenciamento por aprovação e execução, derivar a execução dos serviços pelas tarefas e permitir que apenas administradores registrem a realização das visitas.

**Architecture:** Uma política compartilhada calcula execução e alertas a partir dos fatos existentes, com agregações de tarefas em lote e um instante por resposta. Somente a realização de visitas ganha campos persistidos; a gravação usa o domínio transacional e a proteção de versão atuais. Templates reutilizáveis apresentam os mesmos rótulos sem modificar aprovação, URLs ou fluxos de tarefas.

**Tech Stack:** Django, Django REST Framework, templates Django, CSS compartilhado, SQLite/PostgreSQL e Playwright já utilizado pelos scripts do projeto; sem novas dependências de produto.

**Spec:** `docs/superpowers/specs/2026-10-08-execucao-agendamentos-design.md`, versão aprovada pelo responsável em 08/10/2026.

Etapa: plano aprovado para execução nativa. O responsável autorizou nova branch, publicação e merge na main ao final da verificação.

## Global Constraints

- Preservar `situacao`, seus valores e contratos atuais: `pendente`, `confirmado`, `rejeitado`, além de `cancelado_em`.
- Serviços e visitas confirmados e não cancelados participam dela; os demais registros têm execução não aplicável.
- Não criar colunas `atrasado` ou um segundo status de execução para sincronizar.
- Para serviços, atraso exige `agora > prazo`; conclusão exatamente no prazo não é tardia.
- Para visitas, o intervalo Em execução é `inicio <= agora < fim`: exatamente no término já pertence a Aguardando encerramento.
- Somente administradores ativos podem registrar sua realização.
- Preservar `/agenda/solicitacoes/`, nomes de rota, acesso exclusivo de administradores e seleção de Agendamentos na sidebar.
- Preservar `sheet-layout`, topbars padronizadas, ações existentes e todos os conteúdos.
- Preservar IDs, vínculos, arquivos, autoria, versões e eventos.
- Não alterar Accounts, papéis atuais, equipamentos históricos ou o repositório do monólito.
- Consultar páginas não grava mudanças de estado, não incrementa versões e não produz eventos.
- Desenvolver somente este módulo de Agenda; não refatorar tarefas, seus modais ou suas transições. Fazer commits em português por entrega importante, sem push automático.
- Testes de migração usam banco de testes; navegador usa banco e sessões descartáveis. Não alterar o SQLite de trabalho nem interromper servidores do responsável para verificar a entrega.

## Review Focus

- Responsável/ator excluído: preservar `realizada_em` e o nome histórico do evento mesmo quando a FK administrativa vira nula; teste na tarefa 2.
- IDs iguais em agendas distintas e registros históricos de equipamento: não colidir cartões nem perder registros ao agrupar; teste na tarefa 4.
- Virada de horário durante uma resposta: etiqueta, filtro e contador usam o mesmo instante, inclusive no fuso do projeto; teste na tarefa 1.
- Retorno malicioso ou página que deixou de existir após uma ação: impedir redirecionamento externo e voltar à paginação válida sem reenviar POST; teste na tarefa 3.
- Agregações sobre múltiplos vínculos: responsáveis/equipamentos não multiplicam tarefas nem causam consulta por cartão; teste na tarefa 1.

## Arquivos e responsabilidades

- Criar `inovalab_app/agenda/execution.py`: tipos, política, adaptador de agregações, preparação de leitura e filtro de execução.
- Alterar `inovalab_app/agenda/models.py` e criar `inovalab_app/migrations/0007_realizacao_visitas.py`: propriedades somente leitura, campos de realização e evento `realizar`.
- Alterar `inovalab_app/agenda/selectors.py`: preparar leituras autorizadas com agregações e instante compartilhado, incluindo seleção administrativa explícita.
- Alterar `inovalab_app/agenda/services.py` e `inovalab_app/agenda/policies.py`: registro administrativo transacional e elegibilidade da ação.
- Criar `inovalab_app/agenda/execution_views.py`; alterar `inovalab_app/agenda/urls.py`, `api.py`, `api_urls.py`, `serializers.py` e `forms.py`: transporte web/API estrito, versionado e com retorno seguro.
- Alterar `inovalab_app/agenda/views.py` e `personal.py`: filtros, contadores, agrupamento e contexto dos detalhes.
- Criar os fragmentos `inovalab_app/templates/inovalab_app/agenda/execution_badges.html` e `management_card.html`; alterar `requests.html`, `list.html`, `filters.html`, `detail.html`, `my_bookings.html`, `my_detail.html`, `error.html` na mesma pasta, `inovalab_app/templates/inovalab_app/tarefas/form.html` apenas nos textos de retorno e `inovalab_app/templates/inovalab_app/shared/dashboard.html`.
- Alterar `inovalab_app/shared/dashboard.py`, `inovalab_app/static/inovalab_app/shared/modulos.css` (componentes) e `ui.css` (integração do gerenciamento): seleção de concluídos real e apresentação responsiva compartilhada.
- Criar testes específicos indicados abaixo; ajustar testes de migração e expectativas antigas somente quando a regra aprovada mudar seu resultado.
- Criar `scripts/verificar-execucao-agendamentos.cjs` e `docs/modules/30-gerenciamento-execucao-agendamentos.md`: verificação isolada no navegador e documentação da entrega.

## Task 1: Política de execução e leituras agregadas

**Arquivos:** criar `agenda/execution.py` e `tests/agenda/test_execution.py`; alterar `agenda/models.py`, `agenda/selectors.py` (caminhos sob `inovalab_app/`).

**Interfaces:**

- Produzir `TaskExecutionFacts(total: int, pendentes: int, iniciadas: int, ultima_conclusao: datetime | None)` e `ExecutionState(estado: str, rotulo: str, atrasado: bool, concluido_com_atraso: bool, concluido_em: datetime | None)`, dataclasses imutáveis em `execution.py`.
- Produzir `classify_execution(*, category: str, situation: str, cancelled: bool, now: datetime, deadline: datetime | None = None, tasks: TaskExecutionFacts | None = None, start: datetime | None = None, end: datetime | None = None, realized_at: datetime | None = None) -> ExecutionState`, sem consulta ou gravação.
- Estados exatos: `nao_aplicavel`, `aguardando_inicio`, `em_execucao`, `concluido`, `aguardando_encerramento`; rótulos: Não aplicável, Aguardando início, Em execução, Concluído, Aguardando encerramento.
- Produzir `annotate_service_execution(queryset: QuerySet) -> QuerySet`, `execution_for(booking, *, now: datetime | None = None) -> ExecutionState`, `prepare_execution(rows: list, *, now: datetime) -> list` e `filter_execution(rows: list, value: str = '') -> list`.
- `prepare_execution` guarda `_execucao` somente na instância desta leitura; propriedades `execucao`, `estado_execucao`, `atrasado`, `concluido_com_atraso` em `AgendaControle` usam essa leitura preparada ou delegam ao adaptador. `execution_for` com `now` explícito reclassifica os fatos nesse instante, sem acessar recursivamente `booking.execucao`. Não usar cache global ou invalidar datas de tarefas.
- Preservar chamadas existentes adicionando `now=None` como keyword-only a `visible_bookings`, `visible_booking`, `own_bookings`, `own_booking`; produzir `management_bookings(actor, *, now=None) -> list[PersonalBooking]`, exigindo admin ativo, incluindo cancelados e reutilizando a mesma preparação. Importação de `PersonalBooking` deve ser local para evitar ciclo.

- [x] **1. Escrever testes RED:** em `ExecutionPolicyTests`, testar `test_service_phases_and_deadline_boundaries`, `test_visit_interval_and_realization_precedence` e `test_non_applicable_has_no_alerts`. Usar instantes aware fixos em 08/10/2026, prazo 12:00, visita 09:00–10:00: serviço com `TaskExecutionFacts(0, 0, 0, None)` às 12:00 tem estado `aguardando_inicio` e `atrasado=False`; às 12:00:01 tem `atrasado=True`; fatos `(2, 1, 1, None)` dão `em_execucao`; `(2, 0, 2, prazo)` dão `concluido` sem atraso. Visita exatamente 09:00 está `em_execucao`, exatamente 10:00 está `aguardando_encerramento`; realização às 09:15 dá `concluido` mesmo antes de 10:00.

  Asserção adicional para conclusão posterior ao prazo (usar `datetime` aware e `timedelta` nos testes):

  ```python
  late = prazo + timedelta(seconds=1)
  state = classify_execution(category='servico', situation='confirmado', cancelled=False,
      now=late, deadline=prazo, tasks=TaskExecutionFacts(2, 0, 2, late))
  self.assertEqual(state.estado, 'concluido')
  self.assertEqual((state.atrasado, state.concluido_com_atraso), (False, True))
  self.assertEqual(state.concluido_em, late)
  ```
- [x] **2. Rodar RED:** `.\venv\Scripts\python.exe manage.py test inovalab_app.tests.agenda.test_execution --noinput`. Esperar falha por política/interface ausente, não erro de configuração.
- [x] **3. Implementar política e adaptador:** anotar `_exec_total`, `_exec_pendentes`, `_exec_iniciadas`, `_exec_ultima_conclusao` usando contagens distintas e `Max`, somente tarefas não excluídas; início significa `inicio` não nulo. Adaptador de serviço sem anotações faz uma única agregação; visita usa os dados do intervalo e `realizada_em` quando presente; equipamento retorna não aplicável. Filtros: `''`, `aguardando_inicio`, `em_execucao`, `concluido`, `atrasado`, `aguardando_encerramento`; inválido gera `ValidationError`, `''` conserva não aplicáveis. Não confundir status singular de tarefa com execução do serviço.
- [x] **4. Acrescentar testes de integração RED:** em `ExecutionReadTests`, `test_reopen_delete_relink_and_new_task_recompute_execution` reconsulta depois de cada mudança e verifica conclusão de todas, exclusão ignorada, vínculo removido, nova tarefa, alteração do prazo atual e retorno a Demanda com início conservado; `test_one_instant_and_queries_do_not_grow_per_card` compara leituras com 1 e 30 serviços, múltiplos vínculos, contador e etiquetas sem novas consultas, simulando relógio que avança entre leituras no fuso America/Sao_Paulo; `test_personal_reads_never_expose_foreign_tasks` mantém autorização e não altera versões/eventos. Rodar novamente e confirmar falha antes de integrar seletores.
- [x] **5. Integrar seletores e rodar GREEN:** preparar todas as leituras com um único `timezone.now()` resolvido na entrada, inclusive administrador do gerenciamento, sem consultar tarefas na renderização. Rodar o comando do passo 2 e `.\venv\Scripts\python.exe manage.py test inovalab_app.tests.agenda inovalab_app.tests.shared.test_dashboard --noinput`; esperar `OK` e saída 0.
- [x] **6. Commit:** `feat (agenda): calcula execução e alertas dos agendamentos.` Incluir somente arquivos e testes desta tarefa após `git diff --cached --check`.

## Task 2: Persistência e domínio de realização das visitas

**Arquivos:** alterar `agenda/models.py`, `services.py`, `policies.py`; criar `migrations/0007_realizacao_visitas.py`, `tests/agenda/test_visit_execution.py`, `tests/test_visit_execution_upgrade.py`; alterar `tests/agenda/test_concurrency.py`, `tests/test_task_links_upgrade.py`, `tests/test_adoption.py`, `tests/test_service_upgrade.py`.

**Interfaces:** consumir `ExecutionState`; produzir `mark_visit_realized(*, actor, booking_id: int, expected_version: int) -> AgendaVisita` em `services.py` e `can_mark_visit_realized(actor, booking, *, now=None) -> bool` em `policies.py`.

- [x] **1. Escrever testes RED:** `VisitExecutionServiceTests.test_only_active_admin_can_mark_from_start` verifica proibição para staff, titular externo, inativo e anônimo; admin antes de início falha, exatamente no início funciona. `test_realization_is_atomic_versioned_and_audited` exige `versao + 1`, `realizada_por_id=admin.pk`, instante congelado e um evento `realizar`, sem mudar `situacao`, aprovador ou autoria. `test_repeat_and_invalid_version_never_write` cobre pendente/recusado/cancelado, ausência/boolean/string/zero de versão, versão antiga e repetição com versão nova; a operação recebe ID exclusivamente da tabela de visitas, não um agendamento genérico.

  Para uma visita confirmada `visit` com versão inicial 1, sob relógio congelado no início:

  ```python
  saved = mark_visit_realized(actor=self.admin, booking_id=visit.pk, expected_version=1)
  self.assertEqual((saved.versao, saved.situacao), (2, 'confirmado'))
  self.assertEqual((saved.realizada_por_id, saved.realizada_em), (self.admin.pk, visit.inicio))
  self.assertEqual(saved.eventos.filter(acao='realizar').count(), 1)
  ```
- [x] **2. Rodar RED:** `.\venv\Scripts\python.exe manage.py test inovalab_app.tests.agenda.test_visit_execution --noinput`; esperar operação/campos ausentes.
- [x] **3. Implementar persistência e domínio:** adicionar `AgendaVisita.realizada_em` (`DateTimeField`, `null=True`, `blank=True`, não editável) e `realizada_por` (FK `null=True`, `blank=True`, não editável, `SET_NULL`, `settings.AUTH_USER_MODEL`, related name `visitas_realizadas`); acrescentar escolha `('realizar', 'Realizar')` ao evento. Gerar a migração dependente de `0006_tarefas_multiplos_vinculos`, sem preenchimento histórico. Na operação, exigir admin, obter lock de visitas como primeira operação da transação, carregar categoria visita, checar versão/estado/início no servidor, persistir via atualização condicional e registrar evento; reutilizar `_busy_as_conflict`. Incluir realização/ator em `_snapshot` apenas para visita. `can_mark_visit_realized` é leitura, não substitui a validação transacional.
- [x] **4. Acrescentar testes RED de coerência e concorrência:** `test_schedule_edit_cannot_move_start_after_realization` permite observações e mudanças compatíveis, proíbe início posterior ao registro; `test_actor_deletion_preserves_realization_and_history` mantém instante/nome histórico e FK nula; `test_parallel_realization_and_edit_cannot_overwrite` e `test_parallel_realizations_record_once` usam o padrão de `BookingConcurrencyTests`, esperando apenas um vencedor, versão/evento únicos e conflito para o perdedor. Falha forçada ao criar evento deve reverter campos e versão. Depois do RED, integrar guarda em `_save_visit`/`AgendaVisita.clean` e verificar cancelamento autorizado com realização preservada e execução não aplicável.
- [x] **5. Verificar migração:** em `VisitExecutionUpgradeTests`, migrar de `0006` a `0007`, comparar IDs/dados/eventos antigos e verificar campos nulos, serviço sem colunas extras e visita antiga sem conclusão presumida. Nos três testes existentes que restauram `0006`, restaurar os leaf nodes atuais no teardown; não alterar o alvo histórico que cada teste exercita. Rodar `.\venv\Scripts\python.exe manage.py test inovalab_app.tests.agenda.test_visit_execution inovalab_app.tests.agenda.test_concurrency inovalab_app.tests.test_visit_execution_upgrade inovalab_app.tests.test_task_links_upgrade inovalab_app.tests.test_adoption inovalab_app.tests.test_service_upgrade --noinput` e `.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run`; esperar `OK` e nenhuma alteração pendente. Não executar `migrate` no banco de trabalho nesta etapa.
- [x] **6. Commit:** `feat (agenda): registra realização administrativa de visitas.`

## Task 3: Ação web/API e contrato somente leitura

**Arquivos:** criar `agenda/execution_views.py`, `tests/agenda/test_execution_api.py`, `tests/agenda/test_execution_actions.py`; alterar `agenda/urls.py`, `api_urls.py`, `api.py`, `serializers.py`, `forms.py`.

**Interfaces:** consumir `mark_visit_realized`, `can_mark_visit_realized`, `ExecutionState`; produzir `VisitRealizeView.post(request, pk)` e `VisitRealizeForm` (`versao` positiva oculta, `retorno` opcional, ambos estritos), `RealizeVisitSerializer` (somente `versao` inteira positiva), `BookingViewSet.realizar` e `safe_realization_return(request, value: str, booking) -> str` em `execution_views.py`.

- [x] **1. Escrever testes RED:** `ExecutionActionTests.test_post_requires_admin_csrf_and_version` usa `Client(enforce_csrf_checks=True)`, exige POST e a mesma autorização no domínio; GET não modifica nada. `test_safe_return_preserves_filters_and_recovers_page` aceita somente detalhe da própria visita ou gerenciamento no prefixo da aplicação, preserva query validada e normaliza página ao intervalo disponível; URL externa, protocol-relative ou outra rota retorna detalhe. `ExecutionApiTests.test_realization_is_admin_post_not_patch` proíbe escrita de `realizada_em`, `realizada_por`, `estado_execucao`, `atrasado`, `concluido_com_atraso` e `situacao` em criação/PUT/PATCH, mantém resposta estrita e não aceita categoria serviço/equipamento.

  Com `APIClient` autenticado como admin, visita confirmada e relógio no início:

  ```python
  response = api.post(f'/api/v1/agendamentos/visita/{visit.pk}/realizar/', {'versao': 1}, format='json')
  self.assertEqual(response.status_code, 200)
  self.assertEqual((response.data['situacao'], response.data['estado_execucao']), ('confirmado', 'concluido'))
  self.assertEqual(api.post(f'/api/v1/agendamentos/visita/{visit.pk}/realizar/',
      {'versao': 1}, format='json').status_code, 409)
  ```
- [x] **2. Rodar RED:** `.\venv\Scripts\python.exe manage.py test inovalab_app.tests.agenda.test_execution_actions inovalab_app.tests.agenda.test_execution_api --noinput`; esperar ausência das novas rotas/campos.
- [x] **3. Implementar transporte:** URL web `visita/<int:pk>/realizar/`, nome `agenda:visit-realize`, antes das rotas genéricas; API `agendamentos/<str:category>/<int:pk>/realizar/`, nome `agendamentos-realizar`, mapeada explicitamente em `api_urls.py` (o projeto não usa router automático). Permission exige admin ativo; operação exige categoria visita. Respostas: sucesso API 200 com agendamento, web redirect 302 com mensagem; validação 400, conflito 409, sem autorização 403, objeto ausente 404. Reutilizar `CancelSerializer` como padrão de validação, sem aceitar retorno na API; erros não repetem POST.
- [x] **4. Implementar representação:** criar `ExecutionSerializerMixin` como base de `serializers.Serializer` em `serializers.py`, para que a metaclasse DRF reconheça seus campos somente leitura `estado_execucao`, `atrasado`, `concluido_com_atraso`, `concluido_em`; usar em `BookingSerializer`, `VisitSerializer` e `LegacyEquipmentBookingSerializer`. Preparar a instância com `execution_now` antes de representar e mapear `concluido_em` para `execucao.concluido_em`, sem exigir coluna/propriedade persistida adicional. Visita expõe também `realizada_em` e `realizada_por` por ID. Conservar todos os campos/contratos atuais. Contexto `execution_now` é definido uma vez por requisição e usado em seletores/representação; reconsultar o registro após mutações para não reutilizar classificação anterior.
- [x] **5. Rodar GREEN e regressões:** testar reenvio/conflito com zero eventos extras, tentativa CSRF ausente, strict payload e consulta pessoal sem campos de tarefas. Rodar comando do passo 2 mais `.\venv\Scripts\python.exe manage.py test inovalab_app.tests.agenda.test_api inovalab_app.tests.agenda.test_confirmation_task inovalab_app.tests.agenda.test_booking_access --noinput`; esperar `OK`/saída 0. A confirmação de serviço continua exigindo criação de tarefa na mesma transação.
- [x] **6. Commit:** `feat (agenda): expõe encerramento de visitas com versão e permissão.`

## Task 4: Gerenciamento com grupos e seção de atenção

**Arquivos:** alterar `agenda/views.py`, templates `agenda/requests.html`, `agenda/list.html`, `agenda/error.html`, `tarefas/form.html` (apenas texto), CSS `shared/modulos.css` e `shared/ui.css`; criar template `agenda/management_card.html`, `agenda/execution_badges.html` e `tests/agenda/test_management_execution.py`; ajustar `tests/agenda/test_requests.py` quando necessário.

**Interfaces:** consumir `management_bookings`, `filter_execution`, `ExecutionState`, rota `agenda:visit-realize`. Produzir contexto `execution_groups` (lista de dicts `key`, `label`, `count`, `bookings`), `execution_attention`, `historical_equipment`, `selected_execution`, `execution_choices`; manter `columns`, `stat_counts`, `selected_status`, `object_list` e nomes das rotas atuais. Fragmento `execution_badges.html` consome `booking.execucao`; `management_card.html` consome `booking` e `return_url`.

- [x] **1. Escrever testes RED:** `ManagementExecutionTests.test_confirmed_groups_partition_all_categories` usa serviços/visitas em cada fase, visita vencida, equipamento histórico e IDs iguais entre categorias; união dos cartões corresponde às confirmadas filtradas, sem duplicação. `test_total_counts_are_independent_of_current_page` cria 27 confirmadas, verifica contadores totais e cartões da página 2; nenhum grupo vazio nesta página deve afirmar que o total é zero. `test_all_tab_keeps_approval_groups_and_actions` verifica Todas/Pendentes/Canceladas/Recusadas, aprovação por tarefa, recusa/cancelamento e link de realização apenas elegível.

  No cenário de 27 confirmadas, com admin autenticado:

  ```python
  response = self.client.get('/agenda/solicitacoes/', {'status': 'confirmada', 'page': 2})
  self.assertEqual(response.context['paginator'].count, 27)
  self.assertEqual(len(response.context['object_list']), 2)
  self.assertContains(response, 'Gerenciamento de agendamentos')
  self.assertEqual(sum(group['count'] for group in response.context['execution_groups'])
      + response.context['execution_attention']['count']
      + response.context['historical_equipment']['count'], 27)
  ```
- [x] **2. Rodar RED:** `.\venv\Scripts\python.exe manage.py test inovalab_app.tests.agenda.test_management_execution --noinput`; esperar falta de título/contexto/grupos.
- [x] **3. Implementar contexto:** substituir leitura bruta de modelos de `BookingReviewListView` por `management_bookings`, aplicar busca/mês e filtro `execucao` antes de paginação; contadores de aprovação continuam independentes da aba, respeitando os demais filtros. Na aba Confirmadas, contar grupos no conjunto filtrado completo e distribuir somente os cartões da página atual; separar atenção e equipamentos históricos. Nas demais abas, manter colunas por aprovação. Um único instante é passado à seleção e elegibilidade da ação.
- [x] **4. Implementar UX:** título/links Gerenciamento de agendamentos; Confirmadas mostra três grupos, seção Aguardando encerramento e Equipamentos históricos. Extrair cartão atual sem trocar suas ações; acrescentar execução/alerta com texto, e POST administrativo de realização separado do POST de cancelamento. Todas usa etiquetas, não novos quadros aninhados. Grupo Concluídos contém serviços concluídos e visitas realizadas; alerta Concluído com atraso não duplica o rótulo principal. Ajustar espaçamento e quebra responsiva no CSS existente; preservar Montserrat/topbars/sheet. Não introduzir drag-and-drop de agendamentos.
- [x] **5. Testar filtros e GREEN:** `test_execution_filter_combines_with_tabs_and_clear_resets_everything` verifica valores válidos, inválido 400, pendentes com filtro de execução específico sem resultados, busca/mês preservados, abas sem página antiga e Limpar filtros retornando Todas/primeira página. Verificar que somente admin vê o acesso e que a sidebar continua Agendamentos. Rodar passo 2 e `.\venv\Scripts\python.exe manage.py test inovalab_app.tests.agenda.test_requests inovalab_app.tests.shared.test_clear_filters inovalab_app.tests.agenda.test_confirmation_task --noinput`; esperar `OK`. Atualizar expectativas textuais antigas, não enfraquecer testes de autorização ou confirmação.
- [x] **6. Commit:** `feat (agenda): organiza gerenciamento por execução dos agendamentos.`

## Task 5: Apresentação consistente em Agenda, detalhes e dashboard

**Arquivos:** alterar `agenda/views.py`, `agenda/personal.py`, `shared/dashboard.py`, templates `agenda/filters.html`, `list.html`, `detail.html`, `my_bookings.html`, `my_detail.html`, `shared/dashboard.html`; criar `tests/agenda/test_execution_frontend.py`; alterar `tests/shared/test_dashboard.py`, `tests/portability.py`, `tests/shared/test_clear_filters.py`.

**Interfaces:** consumir filtros/política/fragmento da tarefa 1/4 e ação da tarefa 3. Contexto de filtros usa `selected_execution`/`execution_choices` e parâmetro GET `execucao` em todas as três telas. Contexto de detalhes usa `can_mark_visit_realized` calculado no mesmo instante da execução.

- [x] **1. Escrever testes RED:** `ExecutionFrontendTests.test_same_state_labels_across_internal_and_personal_pages` exige aprovação visível e execução/alerta idênticos em Agenda, detalhes, Meus agendamentos e dashboard; não deve haver tarefas individuais em página de titular. `test_filters_preserve_calendar_and_clear_month_semantics` verifica fase, atraso, encerramento, busca/categoria/mês/página e Agenda com `mes=` ao limpar. `test_realization_action_is_admin_only_and_full_page_is_preserved` verifica registro/ator/hora em `dd/mm/aaaa hh:mm`, ausência da ação para não-admin e preservação de `sheet-layout` e topbars, sem novos modais.

  No teste de uma visita confirmada passada e ainda não realizada:

  ```python
  context = dashboard_context(self.admin, now=visit.fim + timedelta(seconds=1), booking_tab='concluidos')
  self.assertNotIn(('visita', visit.pk), [(row.categoria, row.pk) for row in context['bookings']])
  self.assertEqual(execution_for(visit, now=visit.fim).estado, 'aguardando_encerramento')
  ```
- [x] **2. Rodar RED:** `.\venv\Scripts\python.exe manage.py test inovalab_app.tests.agenda.test_execution_frontend inovalab_app.tests.shared.test_dashboard --noinput`; esperar ausência das etiquetas/filtros e comportamento antigo de concluídos.
- [x] **3. Integrar filtros e detalhes:** reusar `execution_badges.html`, seletor Execução com os seis rótulos aprovados, validação única e paginação atual. Preservar calendário/legenda e disponibilidade: execução não muda aprovação nem cálculo de conflito de horários. Em detalhes, mostrar realização e botão permitido; quando a FK do administrador foi excluída, obter nome histórico do evento `realizar`. Propriedade do titular não concede registro administrativo.
- [x] **4. Corrigir dashboard:** `dashboard_context(actor, *, now=None, ...)` passa seu `now` a `visible_bookings`; aba `concluidos` seleciona serviços/visitas pelo estado `concluido`, não por `fim <= now`. Ordenar estes pela `concluido_em` descendente; equipamento histórico conserva a regra temporal antiga, sem etiqueta de execução. Manter abas semana/próximos e calendário existentes; não criar uma nova fila de alertas no dashboard. Testar `test_past_unrealized_visit_is_not_completed`, `test_service_completion_ignores_deadline_until_all_tasks_complete`, conclusão antes do prazo, conclusão antecipada de visita e `test_historical_equipment_keeps_legacy_dashboard_behavior`.
- [x] **5. Verificar host e GREEN:** ampliar `NativeHostTests` com `test_visit_execution_uses_host_user_and_prefixed_routes`, conferindo FK `auth.User`, realização admin, rota de retorno `/laboratorio/`, ação e alertas sem exigir Accounts. Rodar comando do passo 2, `.\venv\Scripts\python.exe manage.py test inovalab_app.tests.agenda.test_personal inovalab_app.tests.shared.test_clear_filters --noinput` e `.\venv\Scripts\python.exe manage.py test inovalab_app.tests.portability --settings=inovalab_app.tests.host_settings --noinput`; esperar `OK`. Não aumentar silenciosamente timeout do subprocesso de portabilidade; revisar se novos testes ultrapassarem o limite existente.
- [x] **6. Commit:** `feat (agenda): padroniza execução nas telas de agendamentos.`

## Task 6: Verificação ponta a ponta e documentação da entrega

**Arquivos:** criar `scripts/verificar-execucao-agendamentos.cjs`, `docs/modules/30-gerenciamento-execucao-agendamentos.md`; atualizar `AGENTS.md`, a etapa da especificação e as caixas deste plano somente após confirmação dos resultados.

**Interfaces:** script consome `AGENDA_TEST_BASE_URL`, `AGENDA_TEST_ADMIN_SESSION`, `AGENDA_TEST_OWNER_SESSION` e `AGENDA_TEST_AXE_PATH` opcional. Base deve ser servidor/banco de teste descartável; não registrar cookies ou dados de acesso em logs. Reutilizar Playwright e Chrome dos verificadores existentes.

- [x] **1. Criar verificação RED no navegador:** script deve falhar quando Confirmadas não apresentar os três grupos/seção de atenção ou quando uma visita vencida aparecer como concluída. Fixtures isoladas incluem fases, serviço atrasado/concluído com atraso, visita durante intervalo/vencida/realizada, cancelados/recusados e equipamento histórico, com mais de 25 cartões. Confirmar que o teste detecta o comportamento antigo em cópia descartável da versão anterior, sem reverter arquivos do responsável. Fixar seletores acessíveis, por exemplo:

  ```javascript
  for (const label of ['Aguardando início', 'Em execução', 'Concluídos', 'Aguardando encerramento']) {
    await page.getByRole('heading', {name: new RegExp('^' + label)}).waitFor();
  }
  ```
- [x] **2. Rodar fluxo completo:** desktop 1440px e celular 390px, navegação por teclado, sem JavaScript, filtros automáticos já existentes, Limpar filtros, preservação de abas/query/paginação e retorno pós-ação. Marcar visita em curso, exigir apenas um POST e um evento, verificar saída de Em execução para Concluídos, versão incrementada e coerência API/detalhe. Titular externo não vê controles; sessão expirada, 403/409 e falha de rede não repetem gravação. Verificar overflow e acessibilidade com axe quando disponível; screenshots sem dados pessoais. Com ambiente configurado, rodar `node scripts/verificar-execucao-agendamentos.cjs`; sucesso exige saída 0 e todos os cenários relatados.
- [x] **3. Verificação automatizada final:** executar `.\venv\Scripts\python.exe manage.py check`, `.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run`, `.\venv\Scripts\python.exe manage.py test --noinput` e o comando de host da tarefa 5; esperar checks sem erros, nenhuma migração pendente e suítes `OK` com saída 0. Registrar números e resultados reais, sem assumir que os 598 testes da entrega anterior continuam sendo o total. Reexecutar também `scripts/verificar-limpeza-filtros.cjs` e `scripts/verificar-movimento-tarefas.cjs` com suas variáveis/fixtures descartáveis atuais, preservando regressões de filtros e drag-and-drop.
- [x] **4. Documentar e revisar:** documentar regras, estados/alertas, ação administrativa, contratos aditivos, limite temporal e migração sem inferência histórica. Informar que atualização temporal exige nova consulta, sem polling. Registrar comandos/resultados e limitações efetivamente encontradas; atualizar AGENTS para entrega implementada só quando concluída. Fazer revisão final independente, tratar os achados e reexecutar verificações afetadas antes da entrega.
- [x] **5. Commit e handoff:** `feat (docs): documenta gerenciamento e execução de agendamentos.` Validar `git diff --cached --check`, conferir arquivos incluídos e status; entregar resumo e pedir depuração do responsável antes de outro módulo. Migração do banco de trabalho/publicado e deploy ficam fora desta execução de teste; informar necessidade de backup e aplicação de `0007` no ambiente escolhido, sem fazê-lo automaticamente nem realizar push.

## Revisão do plano e escolha de execução

As tarefas seguem dependências: política → persistência/domínio → transportes → gerenciamento → integração das telas → verificação. Recomendação: execução nativa nesta sessão, com uma revisão independente final, porque as seis tarefas compartilham interfaces do mesmo módulo e não exigem implementadores concorrentes. Alternativa: execução por subagentes com revisão a cada tarefa, mais custosa em contexto.

Plano aprovado e executado nativamente na branch `feat/gerenciamento-execucao-agendamentos`. Ver resultados em `docs/modules/30-gerenciamento-execucao-agendamentos.md`. Revisão independente final concluída sem achados, liberando integração e push autorizados; migração de trabalho/publicação e deploy permanecem fora desta entrega.
