# Agenda de visitas local

A solicitação posterior de 07/10/2026 remove a integração de visitas com a API de reservas do AgroHub. Serviços, equipamentos e visitas passam a ser registrados em três tabelas independentes: `AgendaServico`, `AgendaEquipamento` e `AgendaVisita`. Esta decisão substitui as orientações dos módulos 14, 15 e 16 sobre visitas exclusivamente remotas.

## Dados e persistência

`AgendaVisita` possui cinco campos de negócio: `quantidade_pessoas`, `data`, `hora_inicio`, `hora_termino` e `observacoes`. Não possui colunas para título, sala, motivo, objeto de catálogo ou período duplicado em datetimes. Quantidade deve ser um inteiro positivo; data e horários são obrigatórios; o término deve ser posterior ao início no mesmo dia. Observações são opcionais. Horários seguem Brasília.

A base abstrata `AgendaControle` reúne observações e os metadados técnicos necessários para autoria, situação, aprovação, versão, criação e cancelamento. A base abstrata `AgendaBase` mantém motivo/início/fim dos equipamentos e serviços; suas tabelas e regras não mudam. As propriedades calculadas `inicio`/`fim` das visitas permitem usar os mesmos calendários sem gravar campos extras. O nome fixo de apresentação é Visita ao InovaLab, sem título editável.

`EventoAgendamento` passa a aceitar também uma FK para visitas. A restrição exige exatamente uma das três agendas por evento. Criação, alteração, confirmação, recusa e cancelamento registram ator e mudanças na mesma transação. Cancelar preserva registro e histórico e libera o período.

Migration: `0016_agenda_visita_local`. Ela adiciona a tabela, o vínculo de histórico, índices e restrições, sem importar reservas remotas ou modificar serviços/equipamentos. As migrations antigas e os arquivos de legado permanecem preservados. IDs das antigas rotas de ações remotas não são convertidos em IDs locais.

## Fluxo e permissões

Adicionar Agendamento continua abrindo os três cards em `/agenda/novo/`. Visita abre `/agenda/visitas/novo/` com os cinco campos. Administradores criam visitas confirmadas; equipe cria solicitações pendentes para confirmação administrativa, assim como nas demais agendas. Criação e gestão mantêm os papéis internos existentes de Accounts. Qualquer conta ativa autenticada consulta seus próprios registros em Meus agendamentos, inclusive contas externas ou staff do provedor, sem depender de um contrato remoto de titularidade.

Os administradores confirmam, recusam, editam e cancelam localmente. Confirmação e alteração verificam conflitos com visitas confirmadas não canceladas; horários adjacentes são permitidos. Pendentes não reservam o horário. As ações usam categoria/ID e versão para impedir colisões entre tabelas e alterações concorrentes. SQLite serializa as gravações; PostgreSQL utiliza um bloqueio transacional da agenda de visitas.

Agenda, contadores, calendário, dashboard, Solicitações, detalhes e histórico usam os registros locais. Solicitações reúne pendentes, canceladas e recusadas das três categorias, preservando busca, mês, abas e paginação. Confirmadas aparecem na agenda. Meus agendamentos filtra o titular pela conta autenticada, inclusive para administradores, e mantém canceladas/recusadas.

| Rota | Responsabilidade |
| --- | --- |
| `/agenda/visitas/novo/` | Formulário local de criação |
| `/agenda/visita/<id>/` | Detalhe da visita local |
| `/agenda/visita/<id>/editar/` | Edição administrativa |
| `/agenda/visita/<id>/avaliar/` | Confirmação ou recusa administrativa por POST |
| `/agenda/visita/<id>/cancelar/` | Cancelamento administrativo com versão |
| `/agenda/visita/<id>/historico/` | Histórico local |
| `/agenda/meus/visitas/<id>/` | Detalhe local pertencente à conta autenticada |
| `/api/v1/agendamentos/visita/<id>/` | Consulta/edição/cancelamento pela API interna |

A API interna aceita criação com `categoria=visita` e os cinco campos; edição exige `versao`. Campos de sala, título, motivo, objeto e datetimes não são aceitos para visitas. Lista mista serializa cada categoria pelo seu contrato.

## Integrações preservadas

O código de consultas e ações remotas de visitas foi removido. Não há envio, consulta, importação, espelho ou fila de visitas remotas. O monólito não foi alterado.

Accounts continua autenticando e sincronizando papéis/sessões. A integração de eventos do dashboard e das páginas públicas continua funcionando. Contato e outras integrações existentes não foram modificados. A API de recebimento por integradores mantém o contrato de serviços/equipamentos: sua escolha de categoria fica explicitamente limitada a essas duas opções para não expandir o contrato ao adicionar `AgendaVisita` no registro de modelos locais.

## Verificação

Os testes cobrem os cinco campos, rejeição dos campos removidos, criação e aprovação, conflitos/adjacência, edição/cancelamento/versões, histórico, CSRF, recusadas/canceladas, API interna, calendário/dashboard, titularidade e categorias com IDs iguais. Testes com HTTP simulado verificam a continuidade de Accounts e a ausência de chamadas à API de reservas; o carregador de eventos continua sendo invocado. Criações e aprovações simultâneas de visitas confirmam somente uma reserva no período e preservam os históricos.

Comandos de entrega:

```powershell
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\venv\Scripts\python.exe manage.py migrate --noinput
git diff --check
```

Resultado final: **548 testes Django passaram**, incluindo concorrência de visitas e isolamento entre categorias. `check`, `makemigrations --check --dry-run` e `git diff --check` passaram. A migration foi aplicada ao SQLite local após backup privado em `.private/`; as contagens anteriores de serviços, equipamentos, históricos e recibos foram preservadas.

A conferência visual no navegador depende da ferramenta de Computer Use, cujo pipe nativo não está disponível nesta sessão. Renderização, navegação e ações foram verificadas pelo cliente Django. Na depuração, conferir desktop/celular, formulário de cinco campos, Solicitações e Meus agendamentos com dados reais. Concorrência foi testada em SQLite; a execução em PostgreSQL e as integrações reais permanecem para validação no ambiente correspondente.
