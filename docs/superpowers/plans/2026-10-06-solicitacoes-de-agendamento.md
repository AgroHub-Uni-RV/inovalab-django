# Plano de implementação: solicitações de agendamento

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans para executar este plano diretamente na sessão, conforme autorização do responsável. Passos usam checkboxes para acompanhamento.

**Goal:** Permitir pedidos próprios por usuários comuns, com aprovação administrativa para reservar horários.

**Architecture:** Ampliar o Agendamento existente com estado e avaliação, usando os serviços transacionais como fronteira de escrita. Consultas filtram pelo autor antes de qualquer carregamento; ações administrativas continuam separadas. Views, API e widgets consomem essas mesmas regras.

**Tech Stack:** Python do venv, Django, Django REST Framework, SQLite/PostgreSQL, templates Django, CSS e JavaScript existentes.

**Spec:** `docs/superpowers/specs/2026-10-06-solicitacoes-de-agendamento-design.md`

## Global Constraints

- Desenvolver somente o módulo de agenda nesta entrega.
- Manter login, perfil e gestão técnica de contas exclusiva de superusuários ativos.
- Manter a política administrativa definida por `accounts.policies.is_business_admin`.
- Manter o padrão visual e a escala definidos em `core/static/core/ui.css`.
- Manter os filtros com atualização parcial, sem recarregar a página inteira.
- Manter equipamentos opcionais nos serviços e as regras atuais de material próprio e gasto.
- Manter integrações autenticadas existentes com criação de reservas confirmadas.
- Não adicionar dependências para implementar este fluxo.
- Fazer commits convencionais em português por alteração importante.
- Executar testes automatizados Django e verificações básicas no navegador na entrega da implementação.

Execução na cópia atual, branch `feat/solicitacoes-agendamento`, derivada de `main`.
A base foi verificada: 355 testes passaram antes da implementação. O responsável
autorizou execução direta; não haverá delegação a subagentes.

## Task 1: estados, criação por perfil e avaliação transacional

**Files:** modificar `agenda/models.py`, `agenda/services.py`, `agenda/selectors.py`;
criar `agenda/policies.py` e `agenda/migrations/0005_agendamento_avaliado_em_agendamento_avaliado_por_and_more.py`
e `agenda/tests/test_requests.py`; adaptar expectativas antigas em
`agenda/tests/test_services.py`; ampliar `agenda/tests/test_concurrency.py`.

**Interfaces:**
- Consome `is_business_admin(actor)`, `_lock_targets(*targets)`,
  `_load(booking_id, version)`, `_persist_existing(booking, version)`.
- Produz `save_booking(*, actor, data, booking_id=None, expected_version=None) -> Agendamento`:
  usuário ativo cria pendente; só administrador edita.
- Produz `review_booking(*, actor, booking_id, expected_version, decision) -> Agendamento`,
  com decision `aprovar` ou `rejeitar`, exclusivo de administrador.
- Produz `visible_bookings(actor) -> QuerySet[Agendamento]`, com registros próprios
  para usuário ativo e todos os registros não cancelados para administrador.
- Mantém `_save_booking` como núcleo confiável para integrações confirmadas.

- [x] Escrever testes de criação pendente, isolamento e rejeição de campos protegidos.

```python
def test_normal_creation_is_pending_and_owned(self):
    booking = save_booking(actor=self.user, data=self.data)
    self.assertEqual((booking.situacao, booking.criado_por_id), ('pendente', self.user.pk))
    self.assertEqual(list(visible_bookings(self.other)), [])
```

Usar fixtures reais: usuários comuns `solicitante` e `outro`, administrador do
grupo Administradores, serviço cadastrado e intervalo `2026-11-01T14:00:00-03:00`
a `2026-11-01T15:00:00-03:00`. Testar criação pendente sobre reserva confirmada,
aprovação impedida por conflito, rejeição, repetição, versão antiga, inativos,
restrição de espaços e indisponibilidade de equipamentos/material na avaliação.

- [x] Rodar `& .\venv\Scripts\python.exe manage.py test agenda.tests.test_requests --noinput`.
  Esperado inicialmente: falha porque usuário comum não pode criar.
- [x] Implementar estado e criação controlada pelo servidor.

```python
situacao = models.CharField(max_length=10, choices=[('pendente', 'Pendente'),
    ('confirmado', 'Confirmado'), ('rejeitado', 'Rejeitado')], default='confirmado', editable=False)
avaliado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
    null=True, blank=True, editable=False, related_name='agendamentos_avaliados')
avaliado_em = models.DateTimeField(null=True, blank=True, editable=False)
```

Criar `can_access_agenda(actor)` como política local: autenticado e ativo. O
facade `save_booking` aplica essa política e exige administrador para edição.
Na criação normal, passar internamente `situacao='pendente'` ao núcleo; os
campos públicos continuam sem situação/autor/avaliação. O núcleo tem default
confirmado para preservar integrações. Incluir estado e avaliação no snapshot
e nos campos persistidos. Migração usa default confirmado para dados existentes.

- [x] Implementar decisões com bloqueio de alvo, recarga de versão e histórico.

```python
with transaction.atomic():
    _lock_targets(_target(booking), *(('equipamento', pk) for pk in equipment_ids))
    booking = _load(booking_id, expected_version)
    if booking.situacao != 'pendente':
        raise BookingConflict('pedido_avaliado', 'Esta solicitação já foi avaliada.')
    before = _snapshot(booking)
    booking.situacao = 'confirmado' if decision == 'aprovar' else 'rejeitado'
    booking.avaliado_por = actor
    booking.avaliado_em = timezone.now()
    _persist_existing(booking, expected_version)
    _record(actor, booking, decision, before)
```

Antes de persistir uma aprovação, validar recursos disponíveis, material e
`booking.full_clean()`, e consultar sobreposição com `situacao='confirmado'` e
`cancelado_em__isnull=True`. A criação confirmada usa esse mesmo filtro. Pedido
pendente não valida sobreposição. Manter o primeiro acesso dentro da transação
como escrita no alvo para concorrência SQLite. Testar disputa de duas aprovações
e aprovação contra criação administrativa usando o helper de threads existente.

- [x] Rodar testes de serviços, pedidos e concorrência; corrigir regressões.
- [x] Gerar a migração e verificar com `manage.py makemigrations --check --dry-run`.
- [x] Commit: `feat (agenda): adiciona solicitações e aprovação administrativa.`

## Task 2: interface, API e seleção de espaços por perfil

**Files:** modificar `agenda/views.py`, `agenda/forms.py`, `agenda/widgets.py`,
`agenda/api.py`, `agenda/serializers.py`, `agenda/urls.py`,
`agenda/templatetags/agenda_access.py`, templates list/detail/form/space_option;
criar templates `agenda/templates/agenda/requests.html`, `filters.html` e `review_actions.html`;
modificar `core/navigation.py`, `core/dashboard.py`, `core/static/core/modulos.css`
e `core/static/core/painel.css`, usando a escala de `ui.css`; testar em
`agenda/tests/test_requests.py` e adaptar testes antigos web/API/core/foto/widget.

**Interfaces:**
- Consome os serviços e seletores da Task 1.
- Produz `BookingReviewListView`, `BookingReviewView`, rota
  `agenda:requests` em `/agenda/solicitacoes/` e `agenda:review` em
  `/agenda/<pk>/avaliar/`.
- `BookingForm(*args, booking=None, actor=None, **kwargs)` recebe ator;
  `ReviewForm` aceita apenas `versao` e `decisao` além do CSRF.
- `SpaceRadioSelect` recebe `is_admin`, desabilita opções restritas só para comuns.

- [x] Escrever testes web/API de criação própria, filtros, acesso cruzado,
  decisões administrativas, CSRF, estado e bloqueio dos três espaços.

```python
def test_user_cannot_read_another_booking(self):
    booking = save_booking(actor=self.other, data=self.data)
    self.client.force_login(self.user)
    self.assertEqual(self.client.get(f'/agenda/{booking.pk}/').status_code, 404)
    self.assertEqual(self.client.get(f'/agenda/{booking.pk}/historico/').status_code, 404)
```

- [x] Rodar os testes novos; esperado: views/API negam criação e leitura normal.
- [x] Separar mixins de usuário ativo e administrador; edição e cancelamento
  exigem administrador. Toda consulta de detalhes usa `visible_bookings`.
  API libera list/retrieve/create/historico a usuários ativos; update,
  partial_update e destroy continuam exclusivos de administradores.
- [x] Acrescentar campos de saída somente leitura na API.

```python
situacao = serializers.CharField(read_only=True)
avaliado_por = serializers.IntegerField(source='avaliado_por_id', read_only=True)
avaliado_em = serializers.DateTimeField(read_only=True)
```

- [x] Implementar listagem administrativa com filtro inicial pendente, sem mês,
  e ações POST explícitas com versão. Capturar conflitos como HTTP 409 e
  validação como 400. Sucesso redireciona para a listagem administrativa.
- [x] Listagem comum usa mês opcional vazio por padrão; administrativa mantém
  mês atual quando parâmetro ausente. Calendário sempre recebe mês válido:
  `calendar_month = selected_month or timezone.localdate().strftime('%Y-%m')`.
  Filtrar calendário e contagens de ocupação por confirmado. Validar estado
  contra choices antes de filtrar. Preservar filtros `data-auto-apply` existentes.
- [x] Adicionar estado visível a listagem/detalhes, avaliação nos detalhes,
  mensagens de solicitação pendente e botões administrativos condicionais.

```html
<span class="badge booking-status {{ booking.situacao }}">{{ booking.get_situacao_display }}</span>
{% if is_business_admin %}<a href="{% url 'agenda:update' booking.pk %}">Editar</a>{% endif %}
```

- [x] Passar ator ao formulário em GET, POST e atualização assíncrona. Na opção
  de espaço usar `restricted = space.somente_administradores and not self.is_admin`;
  se restrita, adicionar `option['attrs']['disabled'] = True`. O `clean_objeto`
  verifica novamente a política; o serviço permanece a última barreira.
- [x] Mostrar entrada Agendamentos para ativos e Solicitações só para admin.
  Corrigir destaque da navegação para não marcar as duas entradas na página de
  solicitações. Dashboard consulta somente confirmados pelo seletor do ator.
- [x] Rodar `manage.py test agenda core integracoes --noinput` e verificar
  isolamento, filtros, materiais, reservas por integração e layout dos widgets.
- [x] Commit: `feat (agenda): permite pedidos próprios e avaliação pela interface.`

## Task 3: validação final e documentação da entrega

**Files:** atualizar o acompanhamento deste plano e criar
`docs/frontend/11-solicitacoes-de-agendamento.md`; revisar migração e testes,
incluindo `agenda/tests/test_request_migration.py` para dados existentes.

**Interfaces:** consome todas as entregas anteriores; produz instruções de
depuração, comandos/resultados e cenários restantes ao responsável.

- [x] Executar suíte completa: `& .\venv\Scripts\python.exe manage.py test --noinput`.
- [x] Executar check, dry-run de migrações e `git diff --check`; todos sem erros.
- [x] Aplicar migração local e confirmar que registros anteriores estão
  confirmados e mantêm seus campos de cancelamento e criador.
- [x] Iniciar servidor temporário com cópia isolada do banco para o navegador.
  Usar contas temporárias, sem alterar credenciais reais. Testar usuário comum
  solicitando, administrador rejeitando/aprovando e usuário acompanhando estado.
- [x] Verificar cadeados e seleção dos espaços para ambos os papéis, isolamento
  entre contas, filtros sem navegação completa, sidebar expandida e tela móvel.
- [x] Registrar resultados e limites da verificação, concluir checkboxes e
  commitar: `docs (agenda): registra validação do fluxo de solicitações.`
- [x] Usar finishing-a-development-branch ao encerrar e informar commits e estado
  da branch. Aguardar depuração do responsável antes de outro módulo.

## Revisão do plano

Cobertura conferida contra a especificação: estados/migração, domínio,
concorrência, isolamento web/API/foto/histórico, administração, calendário,
filtros, espaços por perfil e verificação final estão nas três tarefas.
Assinaturas e campos usam os mesmos nomes em todas as tarefas. Não há etapas
sem definição do resultado ou decisões pendentes de implementação.
