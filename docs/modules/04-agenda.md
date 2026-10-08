# Módulo 4 — Agenda interna

> Atualização de 08/10/2026: serviços com prazo e bloqueio de novas reservas de equipamento. Consulte [25-servicos-tarefas-infraestrutura.md](25-servicos-tarefas-infraestrutura.md); os contratos anteriores abaixo permanecem como histórico.

> Atualização de 07/10/2026: o módulo de integradores, seus recibos e metadados associados foram removidos. As referências a esse recebimento abaixo descrevem entregas anteriores. Agendamentos e eventos históricos permanecem. Ver [remoção](23-remocao-integracoes.md).

**Solicitação mais recente de 07/10/2026:** Recusar usa a API do AgroHub; confirmadas saem do quadro de solicitações e viram agendamentos locais, vinculados sem duplicação. Ver [recusa e confirmações na agenda](13-recusa-e-confirmacoes-na-agenda.md). A autorização atual permite o registro local das confirmadas.

**Solicitações posteriores de 07/10/2026:** `/agenda/solicitacoes/` consulta reservas do InovaLab no AgroHub via API, com abas Todas/Pendentes/Canceladas e quadro no padrão do Fluxo de tarefas. Mantém busca/mês/paginação e botões Confirmar/Cancelar nas pendentes, aplicando decisões no provedor. Ver [solicitações remotas](12-solicitacoes-remotas-agrohub.md); descrições anteriores da lista de pedidos locais são históricas.

**Atualização de 07/10/2026:** o modelo `Espaco` e sua FK foram removidos. Reservas antigas conservam ID/nome como dados históricos, eventos, recibos e consulta/cancelamento. Categorias atuais continuam Serviços, Equipamentos e Visitas. Ver [remoção de espaços](11-remocao-espacos.md); as referências abaixo à FK registram a implementação anterior.

Entrega inicial local em 02/10/2026, autorizada para implementação direta com [plano simples](../superpowers/plans/2026-10-02-agenda.md). Em 06/10/2026, a solicitação posterior autoriza [reservar a sala 1 no AgroHub na criação de visitas](10-visitas-agrohub.md). As seções abaixo registram a entrega inicial e suas evoluções; o contrato externo atual está nesse guia.

## Uso e permissões

Entre com superusuário ativo ou conta ativa do grupo `Administradores` e abra `/agenda/`. O papel de negócio não exige `is_staff`. Usuários internos ativos consultam seus próprios registros e criam solicitações pendentes. Somente administradores editam, cancelam e avaliam pedidos; staff sem esse papel não recebe gestão administrativa. Sem sessão, as telas redirecionam ao login e a API retorna 403.

A tela reúne calendário mensal, contagem de reservas por dia e lista de até 25 registros por página. Filtros: mês e categoria. Reservas que atravessam dias ou meses aparecem em todos os períodos ocupados; uma reserva terminando à meia-noite não conta no dia seguinte. As contagens incluem todo o filtro, independentemente da página da lista. Os formulários usam horário de Brasília (`America/Sao_Paulo`).

Selecione uma categoria; as opções são atualizadas automaticamente via JavaScript. Escolha Equipamento, Serviço ou Visita. Recursos recebem objeto, motivo obrigatório, observações opcionais, dia e horários. Visita recebe apenas dia, início e término. O responsável é o usuário autenticado que cadastrou o agendamento, definido pelo servidor. Para Serviço com material do laboratório, escolha o material cadastrado e informe o gasto em gramas. A atualização das opções conserva os campos que existem na categoria escolhida e as datas não salvas e a versão original de uma edição. Usa POST com CSRF para manter esses dados fora da URL. Depois de uma edição concorrente, recarregue o formulário antes de reaplicar alterações. Veja [usuário e horários do agendamento](../frontend/12-usuario-e-horarios-do-agendamento.md).

| Caminho web | Operação |
| --- | --- |
| `/agenda/` | Calendário mensal e lista filtrada |
| `/agenda/novo/` | Formulário de criação |
| `/agenda/{id}/` | Detalhe |
| `/agenda/{id}/editar/` | Edição com versão |
| `/agenda/{id}/cancelar/` | Confirmação; somente POST cancela |
| `/agenda/{id}/historico/` | Eventos paginados, com valores anteriores e novos |

O frontend de identidade foi preservado, com apenas um link para a agenda nas contas autorizadas. As novas telas são listas, formulários e ações simples.

## Regras entregues

- **Correção confirmada em F5 (06/10/2026):** novas categorias são Equipamentos, Serviços e Visitas. Espaços permanecem no catálogo, sem novas reservas. Serviço/equipamento é exclusivo por objeto; equipamentos associados a serviços não criam reservas automáticas.
- API interna: `categoria` (`servico`, `equipamento`, `visita`), `inicio` e `fim`. Recursos exigem também `objeto` e `motivo`; troca para recurso exige categoria/objeto juntos. Visita rejeita objeto, motivo, observações e campos de serviço, mesmo vazios. Troca para visita limpa dados incompatíveis com auditoria. Serviço mantém equipamentos e campos de material.
- O campo livre `requerente` foi removido do modelo e da API interna. `criado_por` identifica o usuário criador e não pode ser enviado ou alterado pelo cliente. A API também retorna `criado_por_nome`. Motivo é obrigatório em serviços/equipamentos e tem espaços nas extremidades removidos. Integrações conservam seus metadados externos, sem inventar uma conta interna.
- `observacoes` é texto opcional somente para serviços/equipamentos. Omitido fica vazio; PATCH sem esse campo preserva o anterior. Edição/limpeza são auditadas. Visitas não recebem observações.
- FKs protegidas de serviço/equipamento; visita com todas as FKs nulas e indicador `visita=True`. FK de espaço permanece exclusivamente para legado. Restrições impedem alvos incompatíveis e textos em visitas, exigem versão positiva e intervalo positivo.
- Intervalos `[início, fim)`; sobreposição no mesmo objeto retorna conflito, horários adjacentes são permitidos. A edição exclui o próprio registro da busca de conflito. Falhas não deixam mudanças parciais.
- Cada criação, edição e cancelamento grava um evento na mesma transação, com ator, instante, ação e mudanças. Datas nas mudanças são normalizadas em UTC para evitar diferenças fictícias entre fusos equivalentes.
- Edição e cancelamento exigem versão inteira positiva. Versão desatualizada retorna 409. Cada gravação incrementa a versão, inclusive edição sem mudança material, que pode ter evento com alterações vazias.

**Escolhas de implementação para depuração, sem novas respostas a Q06/Q08/Q13/Q14:**

- Cancelamento lógico libera o intervalo e preserva o registro/eventos. Canceladas ficam fora da lista, detalhe e histórico operacionais; não há restauração nem consulta de canceladas nesta entrega. Os registros permanecem no banco, inclusive as referências protegidas ao catálogo.
- Usuários comuns criam pedidos pendentes; avaliação administrativa revalida disponibilidade e conflitos antes de confirmar. Não há criação automática de tarefa.
- `indisponivel` impede reserva nova, troca de alvo ou mudança de período. Alteração apenas do motivo de uma reserva existente continua possível após desativar o alvo; cancelamento também. `ocupado` manual não bloqueia automaticamente reservas futuras. Reservar/cancelar não muda o status do catálogo.
- O formulário escolhe um dia e um intervalo positivo dentro desse dia. Datas passadas continuam permitidas, sem impor funcionamento, feriados, antecedência, duração mínima/máxima ou margem entre reservas ainda não definidos. O armazenamento e a API conservam `inicio`/`fim` com fuso horário, inclusive períodos antigos que atravessam dias. Não há campo de participantes nem validação de capacidade do espaço.

## API entregue

JSON, autenticação por sessão Django e CSRF obrigatório nas escritas; nenhum acesso público ou credencial AgroHub foi acrescentado.

| Método e caminho | Resultado |
| --- | --- |
| `GET /api/v1/agendamentos/` | Todos os ativos, paginados 25; filtros opcionais `mes=AAAA-MM`, `categoria`; `page` seleciona página |
| `POST /api/v1/agendamentos/` | Cria conforme os campos da categoria, 201 |
| `GET /api/v1/agendamentos/{id}/` | Detalhe, 200 |
| `PUT /api/v1/agendamentos/{id}/` | Salva conforme os campos da categoria, com `versao`, 200 |
| `PATCH /api/v1/agendamentos/{id}/` | Altera campos informados, com `versao`, 200 |
| `DELETE /api/v1/agendamentos/{id}/` | Cancela com corpo `{"versao": 1}`, 204 |
| `GET /api/v1/agendamentos/{id}/historico/` | Eventos mais recentes primeiro, paginados 25 |

Criação, usando um ID real obtido no catálogo:

```json
{
  "categoria": "servico",
  "objeto": 1,
  "motivo": "Produzir protótipo",
  "inicio": "2026-11-01T14:00:00-03:00",
  "fim": "2026-11-01T15:00:00-03:00"
}
```

A resposta acrescenta `id`, `objeto_nome`, `versao`, `criado_por` e `criado_em`. Horários exigem ISO 8601 com fuso; UTC também é aceito. Campos internos/protegidos e desconhecidos são rejeitados. `objeto` e `versao` exigem inteiros JSON, rejeitando strings, booleanos e decimais. A criação não aceita `versao`: começa em 1.

Erros: 400 para payload/filtro inválido ou objeto indisponível; 403 para ausência de autorização/CSRF; 404 para ID inexistente/cancelado. Conflitos retornam 409 com `detail` e `code`:

| Código | Significado |
| --- | --- |
| `horario_ocupado` | Sobreposição para o mesmo objeto |
| `versao_desatualizada` | Edição/cancelamento baseado em versão antiga |
| `agenda_ocupada` | SQLite ocupado por outra transação; atualizar e tentar novamente |

Para PATCH somente de texto, envie por exemplo `{"versao": 1, "motivo": "Descrição corrigida"}`. A ausência dos dois campos de alvo preserva o existente. Para recursos, enviar somente categoria ou objeto retorna 400. `{"versao": 1, "categoria": "visita"}` muda para visita e limpa os dados anteriores do recurso.

## Concorrência e integridade

`save_booking`, `cancel_booking` e `visible_bookings` centralizam operações/escopo. O primeiro acesso ao banco dentro da transação é um UPDATE sem mudança do status do alvo; na troca, os alvos antigo e novo são bloqueados em ordem estável. Só depois são revalidados versão, disponibilidade e sobreposição. Reserva e evento são persistidos juntos; edições/cancelamentos também usam UPDATE condicionado à versão.

No SQLite, a escrita anterior às leituras adquire o bloqueio de escrita; `select_for_update` sozinho não protegeria esse fluxo. O SQLite serializa escritores, inclusive de objetos distintos, e busy/locked vira conflito recuperável. Referências: [transações SQLite](https://www.sqlite.org/lang_transaction.html), [SQLite no Django](https://docs.djangoproject.com/en/6.0/ref/databases/#sqlite-notes).

Esta estratégia foi verificada no SQLite local com duas conexões reais, threads e `TransactionTestCase`. O teste de ordem SQL falhou ao remover temporariamente a proteção, depois voltou a passar. Não foi executada validação de concorrência/carga em PostgreSQL ou ambiente de produção; banco e hospedagem de produção continuam pendentes. Escritas diretas via ORM fora dessas operações não representam uma API autorizada e podem ignorar a proteção de sobreposição.

## Verificação realizada

Em 02/10/2026, Python 3.14.3, Django 6.1.1 e DRF 3.18.1:

```powershell
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py test agenda.tests
& .\venv\Scripts\python.exe manage.py test
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\venv\Scripts\python.exe -m pip check
git diff --check
```

42 testes da agenda passaram: 17 de domínio, 3 de concorrência, 10 de API e 12 web. Suíte completa: **159 testes passaram**, sem falhas. Check, drift de migrações, dependências e diff sem pendências. Migração local aplicada de forma aditiva.

Chrome: cadastro das três categorias; atualização de opções preservando rascunho; conflito de período; adjacência; edição; história de valores; cancelamento e nova reserva no horário liberado; API com sessão/CSRF; conflito de versão após edição via API e refresh do formulário; usuário staff sem papel negado em telas/API; teclado e layout 360 px sem rolagem horizontal da página. Sem exceções JavaScript da aplicação. Datas nativas foram preenchidas por automação do DOM e submetidas pelo formulário real. Apenas fixtures temporárias identificadas por IDs/prefixo foram removidas; contas e cadastros anteriores foram preservados.

Revisão independente única: um Important corrigido — atualizar opções renovava indevidamente a versão; duas regressões demonstraram RED/GREEN, e a suíte voltou a passar. **Minor adiado:** intervalo histórico durante a repetição de hora do horário de verão em fevereiro de 2019 pode ser rejeitado incorretamente. Exemplo API: início `2019-02-16T23:30:00-02:00`, fim `2019-02-16T23:15:00-03:00` (45 minutos válidos em UTC). A comparação local com `ZoneInfo` precisa ser normalizada em UTC em correção posterior; a aceitação de datas históricas tem essa limitação conhecida.

## Depuração mais profunda pelo responsável

1. Revisar as escolhas provisórias de cancelamento/histórico, indisponibilidade, funcionamento e capacidade com a operação do laboratório.
2. Exercitar várias abas e administradores simultâneos: criação, edição de período, troca entre alvos e cancelamento, conferindo versão, bloqueio e eventos. Testar carga no banco/ambiente que vier a ser escolhido para produção.
3. Testar reservas longas e viradas de mês/ano, segundos/frações pela API e preservação ao editar pelo navegador, além do caso histórico de horário de verão conhecido.
4. Testar volume alto, paginação dos eventos, filtros, textos grandes e operação em navegadores/dispositivos adicionais.
5. Confirmar o contrato AgroHub (Q07): autenticação, identidade externa, chave de idempotência, fuso/período, edição/cancelamento e dados mínimos antes do próximo módulo.

## Visitas e reservas de espaços antigas — correção de 06/10/2026

Visita não exige cadastro no catálogo. Criação interna:

```json
{"categoria": "visita", "inicio": "2026-11-01T14:00:00-03:00", "fim": "2026-11-01T15:00:00-03:00"}
```

Os instantes devem pertencer ao mesmo dia em `America/Sao_Paulo`, mesmo que enviados em UTC. Usuário criador, situação, versão e auditoria são automáticos. A resposta mantém o formato comum, com `objeto=null`, nome Visita e textos vazios. Formulário/detalhe ocultam campos de recurso.

**Proposta provisória pendente de resposta:** uma visita confirmada por intervalo; visitas não bloqueiam serviços/equipamentos. A linha `ControleAgendaVisitas(pk=1)` serializa criação, edição, avaliação e cancelamento antes de consultar sobreposições. Cancelamento libera horário; pedidos pendentes não bloqueiam até aprovação.

**Legado preservado:** migração 0008 mantém reservas e eventos de espaços, sem conversão nem exclusão. Aparecem como Espaço (legado), consultáveis e canceláveis. Edição e aprovação de espaços são bloqueadas; não há nova reserva por interface/API/integração. Reenvio externo idêntico de pedido anterior retorna o registro original.

Requisitos correntes: [F5/RF12/RF15/RF16/RN04/Q05](../../01-InovaLab-Escopo-e-Requisitos.md). Resultados de verificação anteriores acima documentam as entregas históricas.

## Verificação desta correção

- `venv/Scripts/python.exe manage.py test --noinput`: **445 testes passaram** (42,257 s), incluindo visitas, concorrência real SQLite, reenvio externo legado e migração 0007→0008 preservando reserva/evento.
- `venv/Scripts/python.exe manage.py migrate --noinput`: 0008 aplicada ao SQLite local.
- `venv/Scripts/python.exe manage.py check`: sem problemas.
- `venv/Scripts/python.exe manage.py makemigrations --check --dry-run`: sem alterações pendentes.
- `git diff --check`: sem erros de espaços; avisos normais de LF/CRLF no Windows.
- Chrome em banco isolado: troca Serviço→Visita conservou dia/horários e retirou campos de recurso; criação, detalhe, conflito 409, filtro/contador de visitas e retorno à seleção de equipamentos. Formulário em 360 px e 1201 px com sidebar expandida sem transbordamento horizontal; nenhuma exceção JavaScript da aplicação.
- Revisão independente: sem Critical/Important; link de edição indevido no legado identificado e corrigido com teste que falhou antes da correção.

Depuração restante: confirmar simultaneidade de visitas e política definitiva para reservas de espaços antigas; validar concorrência/carga no PostgreSQL e atualização do consumidor AgroHub. Esta entrega não foi publicada na Vercel nem migrou o banco de produção.
