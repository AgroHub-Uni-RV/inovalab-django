# Agendas de serviços e equipamentos — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Separar as agendas locais de serviços e equipamentos e manter visitas exclusivamente na API do AgroHub.

**Architecture:** Duas models concretas derivadas de uma base abstrata. Eventos e recibos mantêm FKs tipadas; seletores agregam a apresentação e usam categoria/ID nas ações. Reservas de visita são objetos transitórios do cliente AgroHub.

**Tech Stack:** Python, Django, Django REST Framework, SQLite, templates Django, cliente HTTP AgroHub existente.

**Spec:** `docs/superpowers/specs/2026-10-07-agendas-servicos-equipamentos-design.md`

## Global Constraints

- Alterar somente este repositório; não modificar o monólito AgroHub.
- Persistir agendamentos somente em `AgendaServico` e `AgendaEquipamento`; a base compartilhada deve ser abstrata.
- Consultar e executar ações de visitas exclusivamente pela API autenticada do AgroHub, sem espelho, fila ou reserva local.
- Preservar papéis Accounts, isolamento entre usuários, CSRF, validação de payload e controle de versão nas agendas locais.
- Preservar o layout atual, filtros, calendário e as abas Todas/Pendentes/Canceladas/Recusadas de solicitações.
- Preservar os dados, equipamentos associados, históricos e recibos dos agendamentos locais existentes.
- Antes de excluir visitas ou espaços históricos da estrutura antiga, preservar seus dados fora do banco operacional em arquivo privado, excluído do Git.
- Executar a suíte automatizada Django e verificações básicas das páginas; registrar qualquer impedimento à verificação visual.
- Fazer commits convencionais em português por alteração importante.

### Task 1: Separação local e migração completa dos consumidores

**Files:** Modificar `agenda/models.py`, `services.py`, `selectors.py`, `forms.py`, `serializers.py`, `api.py`, `api_urls.py`, `views.py`, `urls.py`; templates de agenda, `core/dashboard.py`, `core/views.py`, template dashboard; `integracoes/models.py`, `services.py`, `selectors.py`, `serializers.py`, `api.py`, templates de recibos; testes consumidores em agenda/core/integrações. Criar migrations de agenda e integrações e `agenda/tests/test_split_agendas.py`, `test_split_migration.py`. Remover código runtime de `agenda/received_reservations.py`, `agenda/agrohub.py` e templates de fila/sincronização quando não usados. Adicionar exportador privado de legado e exclusão correspondente no `.gitignore`.

**Interfaces:** Produz `AgendaBase` abstrata, `AgendaServico`, `AgendaEquipamento`, `BOOKING_MODELS = {'servico': AgendaServico, 'equipamento': AgendaEquipamento}`; `visible_bookings(actor)` retorna lista de registros locais; `filter_bookings(bookings, *, month=None, category=None, situation=None)` retorna lista; `save_booking(*, actor, data, category=None, booking_id=None, expected_version=None)` e `cancel_booking`/`review_booking` recebem categoria para ações. Rotas de detalhes, edição, histórico, avaliação, foto e cancelamento usam categoria/ID. API local recebe somente serviço/equipamento. A apresentação pode manter categoria visita, mas ela nunca pertence a `BOOKING_MODELS`.

- [x] **Passo 1: Escrever testes de comportamento para duas reservas de mesmo ID e migração.** O teste deve salvar uma reserva de serviço e uma de equipamento com PK igual e verificar que detalhes/ações atingem apenas o alvo tipado; testes de migração usam MigrationExecutor, FK/M2M e datas literais, não expectativas calculadas pelo código migrador.

```python
def test_edicao_tipificada_nao_altera_outro_tipo(self):
    service = self.make_service_booking(pk=77, motivo='Serviço original')
    equipment = self.make_equipment_booking(pk=77, motivo='Equipamento original')
    changed = save_booking(actor=self.admin, category='servico', booking_id=77,
                          expected_version=1, data={'motivo': 'Serviço alterado'})
    equipment.refresh_from_db()
    self.assertEqual(changed.motivo, 'Serviço alterado')
    self.assertEqual(equipment.motivo, 'Equipamento original')
```

- [x] **Passo 2: Executar e registrar RED.** Executar `.\venv\Scripts\python.exe manage.py test agenda.tests.test_split_agendas agenda.tests.test_split_migration --noinput`; registrar a ausência do comportamento antes da implementação, sem confundir erro de sintaxe com falha esperada.
- [x] **Passo 3: Implementar a separação, suas migrations e adaptar todos os consumidores.** Campos comuns ficam na base; constraint de exatamente uma FK nos eventos/recibos; recursos específicos somente no tipo correto. A estrutura de seleção é:

```python
BOOKING_MODELS = {'servico': AgendaServico, 'equipamento': AgendaEquipamento}

def visible_bookings(actor):
    if not can_access_agenda(actor):
        return []
    rows = []
    for model in BOOKING_MODELS.values():
        query = model.objects.filter(cancelado_em__isnull=True)
        if not is_business_admin(actor):
            query = query.filter(criado_por=actor)
        rows.extend(query)
    return sorted(rows, key=lambda row: (row.inicio, row.categoria, row.pk))
```

Usar queries específicas de cada tipo para select/prefetch; não implementar um falso manager ou QuerySet para a model removida. Updates usam `type(booking).objects.filter(pk=booking.pk, versao=version, cancelado_em__isnull=True).update(...)`. `_snapshot` lê equipamentos/material somente em serviços. Recibos usam FK tipada e propriedade `agendamento`; reenvio preserva digest/idempotência. POST de categoria visita na API local retorna erro de validação sem criar registro.

Na UI, GET de agenda e solicitações consulta o cliente `reservations` sem `reconcile_reservations`. Confirmadas remotas são agregadas para calendário/lista/dashboard e têm link para uma rota de detalhe remoto preparada para a tarefa 2. Falhas remotas exibem indisponibilidade, mantendo locais acessíveis. Retirar todas as chamadas de fila/sincronização local. O fluxo de novas visitas deve apontar para o formulário remoto, completado na tarefa 2.

Para a migração, criar os destinos antes das novas FKs; copiar serviços/equipamentos preservando PK, timestamps e M2M; religar eventos/recibos antes de remover FKs antigas; preservar dados excluídos em exportação privada atomicamente, falhando se não puder escrever; remover tabela única e modelos de visitas. Não executar migrations no banco do responsável nesta tarefa. Cobrir o caminho inverso/recuperação documentada e isolamento dos arquivos de teste com diretório temporário.

- [x] **Passo 4: Executar GREEN e regressões locais.** Executar `.\venv\Scripts\python.exe manage.py test agenda core integracoes --noinput`, `.\venv\Scripts\python.exe manage.py check` e `.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run`. Atualizar testes do contrato intencionalmente substituído; não eliminar testes de permissões, concorrência, material ou integração para ocultar regressões. Os testes do espelho/outbox antigo são substituídos por testes de consulta remota sem persistência.
- [x] **Passo 5: Commit.** `git add` com os caminhos da entrega e `git commit -m "refactor (agenda): separa agendas locais de serviços e equipamentos."`. Registrar relatório com RED/GREEN, migrations, interfaces efetivas e qualquer diferença do plano.

### Task 2: Fluxo de visitas exclusivamente remoto

**Files:** Modificar `agenda/remote_requests.py`, `agenda/views.py`, `agenda/urls.py`, formulário/template de visitas; `agenda/templates/agenda/requests.html`, `list.html` e detalhe remoto; adaptar `agenda/tests/test_remote_requests.py`, `test_visits.py`, `test_agrohub.py` para os novos fluxos; reutilizar/estender stub HTTP `agenda/tests/agrohub_stub.py`.

**Interfaces:** Consome as duas models/seletores locais da tarefa 1. Produz `get_reservation(request, reservation_id) -> RemoteReservation`, `save_reservation(request, data, *, reservation_id=None) -> RemoteReservation`, `cancel_reservation(request, reservation_id) -> RemoteReservation`. Preservar `decide_reservation(request, reservation_id, decision)` para pendentes, com verificação de sala InovaLab e resposta final. Visitas usam `agenda:visit-detail`, `visit-create`, `visit-update`, `visit-cancel`, separadas das rotas locais.

- [x] **Passo 1: Escrever teste de confirmação, criação e edição sem linhas locais.** Utilizar servidor HTTP stub para exercer cliente autenticado real; contador de reservas locais antes/depois independe da implementação remota.

```python
def test_confirmacao_aparece_no_calendario_sem_copia_local(self):
    before = AgendaServico.objects.count() + AgendaEquipamento.objects.count()
    response = self.client.post(reverse('agenda:remote-decision', args=[61]),
                                {'decisao': 'confirmar'})
    self.assertEqual(response.status_code, 302)
    page = self.client.get(reverse('agenda:list'), {'mes': '2026-11'})
    self.assertContains(page, 'Visita confirmada de teste')
    self.assertEqual(AgendaServico.objects.count() + AgendaEquipamento.objects.count(), before)
```

Adicionar cenários de criação via POST reservas, edição via PATCH reservas/ID, cancelar confirmada via POST cancelar, CSRF, acesso próprio/administrador e salas de outro site. Acrescentar respostas malformadas, negativas e timeout sem falso sucesso.

- [x] **Passo 2: Executar RED.** `.\venv\Scripts\python.exe manage.py test agenda.tests.test_visits agenda.tests.test_remote_requests --noinput`; identificar o fluxo remoto que ainda falta.
- [x] **Passo 3: Implementar os adaptadores e telas.** Os únicos writes são no cliente existente:

```python
result = authenticated_request(request, 'POST', 'reservas/',
                               namespace='agendamentos', data=payload)
result = authenticated_request(request, 'PATCH', f'reservas/{reservation_id}/',
                               namespace='agendamentos', data=payload)
result = authenticated_request(request, 'POST', f'reservas/{reservation_id}/cancelar/',
                               namespace='agendamentos', data={})
```

Antes de enviar: validar dados do formulário e sala InovaLab por consulta autorizada; em edição/cancelamento verificar reserva e sala pela API. Depois de enviar: validar ID/sala/status/período e campos da resposta, reaproveitando o parser estrito. Usar mensagens de erro seguras e não reenviar automaticamente POST incerto. Não acrescentar lógica de autorização local que amplie privilégios do provedor. Os formulários remotos não usam versão local nem histórico local. Confirmar/recusar permanecem exclusivos do administrador e somente em pendentes. A confirmação informa que a visita aparecerá na agenda por consulta da API.

- [x] **Passo 4: Executar GREEN.** `.\venv\Scripts\python.exe manage.py test agenda.tests.test_visits agenda.tests.test_remote_requests agenda.tests.test_agrohub --noinput` e testes de integração/UI afetados.
- [x] **Passo 5: Commit.** `git commit -m "feat (agenda): mantém visitas e ações exclusivamente no AgroHub."` com testes e telas correspondentes.

### Task 3: Aplicação protegida, documentação e verificação final

**Files:** Modificar `README.md`, `AGENTS.md`; criar `docs/modules/14-agendas-servicos-equipamentos.md`; atualizar este plano com resultados. Banco/arquivos privados não entram no commit.

**Interfaces:** Consome migrations verificadas, exportador de legado e rotas tipadas/remotas. Produz banco operacional migrado neste ambiente, documentação do novo contrato e evidências de verificação.

- [x] **Passo 1: Testar a preservação antes de aplicar ao banco real.** Confirmar nos testes da tarefa 1 que materiais/M2M, eventos, recibos, datas e dados excluídos sobrevivem à migração/exportação. Executar `.\venv\Scripts\python.exe manage.py test --noinput` e revisar resultado integral.
- [x] **Passo 2: Criar backup consistente do SQLite e aplicar migrations.** Usar API de backup SQLite, com caminho absoluto no diretório temporário; não copiar arquivo aberto por operação de shell. Executar `.\venv\Scripts\python.exe manage.py migrate --noinput`, conferir tabelas, contagens e exportação; não realizar operações remotas de escrita durante a migração.

```python
import sqlite3
from pathlib import Path
from tempfile import gettempdir
source = sqlite3.connect('db.sqlite3')
target_path = Path(gettempdir()) / 'inovalab-antes-divisao-agendas-2026-10-07.sqlite3'
with sqlite3.connect(target_path) as target:
    source.backup(target)
source.close()
print(target_path)
```

- [x] **Passo 3: Verificar telas e ações sem mutações no provedor real.** Abrir agenda, solicitações, detalhes locais/remotos e dashboard em sessão autorizada; testar navegação, filtros, tabs e sidebar/móvel se navegador disponível. Caso ferramenta não ofereça superfícies, registrar impedimento e verificar HTTP/renderização com Django/client e sessão local. Criação/confirmação/recusa/cancelamento remotos são verificados no stub, não em reservas reais do usuário.
- [x] **Passo 4: Documentar e revisar.** Explicar modelos, rotas/API por categoria, fonte das visitas, falhas remotas, backup/exportação e recuperação; sobrescrever orientação antiga de visitas locais em AGENTS com nota da nova solicitação. Documentar comandos, quantidade de testes e cenários visuais pendentes. Revisar diff completo e não afirmar resultados sem evidência fresca.
- [x] **Passo 5: Commit final.** `git commit -m "docs (agenda): documenta agendas separadas e visitas pela API."`; conferir working tree limpo e apresentar branch/commits ao responsável. Manter entrega nesta branch local, sem push.

## Auto-revisão e confirmação

Todos os requisitos da spec estão cobertos pelas três tarefas. Os nomes das interfaces e das rotas coincidem entre produtores e consumidores. As duas primeiras tarefas são executadas sequencialmente, com revisão por tarefa; a terceira usa as evidências e a revisão final. Não há placeholders nem autorização pendente. Plano confirmado diretamente por autorização explícita do responsável; iniciar execução sem nova pergunta.

## Resultado da execução

As duas agendas locais foram entregues e as visitas passaram a usar exclusivamente os adaptadores remotos. As revisões por tarefa identificaram e verificaram duas correções: preservar busca pelo login do criador e manter a exigência de pendente na rechecagem do cancelamento em Solicitações.

A suíte completa final passou com 575 testes em 76,786 segundos, código de saída zero. `check`, `makemigrations --check --dry-run`, `migrate --plan` e `git diff --check` passaram. A inspeção encontrou as migrations já aplicadas; o backup anterior e a exportação privada foram conferidos contra o banco migrado, com integridade SQLite `ok`.

As consultas HTTP reais verificaram agenda, visita confirmada e seu detalhe, lista/filtro de visitas, formulários, dashboard e API local. Solicitações retornou 403 na sessão atual de equipe, preservando a proteção administrativa. Escritas remotas foram exercitadas somente no stub. A ferramenta não ofereceu navegador conectado; a avaliação visual de sidebar e menu móvel permanece para o responsável. Os comandos, contratos e evidências estão em `docs/modules/14-agendas-servicos-equipamentos.md`.

Entrega mantida na branch local `refactor/agendas-servicos-equipamentos`, no checkout do IDE.
