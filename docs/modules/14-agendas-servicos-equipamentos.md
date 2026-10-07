# Agendas locais e visitas no AgroHub

A decisão de 07/10/2026 separa os agendamentos locais em **AgendaServico** e **AgendaEquipamento**. Todas as visitas permanecem no AgroHub, inclusive quando confirmadas. Esta decisão substitui a criação de cópias locais descrita na entrega anterior.

## Estrutura dos dados

| Componente | Responsabilidade |
| --- | --- |
| `AgendaBase` | Classe abstrata com período, motivo, observações, criação, situação, avaliação, versão e cancelamento. Não cria tabela. |
| `AgendaServico` | Um serviço obrigatório; equipamentos utilizados e informações de material. |
| `AgendaEquipamento` | Um equipamento obrigatório e os campos comuns. |
| Eventos | Histórico local ligado a exatamente uma das duas agendas por FK. |
| Pedidos de integração | Recibo e chave de idempotência ligados a exatamente uma das duas agendas por FK. |
| Reservas de visita | Dados transitórios retornados pela API, sem tabela, fila ou espelho local. |

A interface continua apresentando agendamentos em uma única lista e calendário. O tipo faz parte da identificação dos registros locais: um serviço e um equipamento podem ter o mesmo número sem serem o mesmo agendamento. Ações e links devem incluir a categoria junto ao ID. O tipo de um registro existente não é alterado durante uma edição.

| Rota local | Uso |
| --- | --- |
| `/agenda/` | Lista e calendário unificados |
| `/agenda/novo/` | Escolher Visita, Equipamento ou Serviços |
| `/agenda/novo/?categoria=servico` | Criar serviço local |
| `/agenda/novo/?categoria=equipamento` | Criar equipamento local |
| `/agenda/<categoria>/<id>/` | Detalhe local |
| `/agenda/<categoria>/<id>/editar/` | Editar local |
| `/agenda/<categoria>/<id>/cancelar/` | Cancelar local |
| `/agenda/<categoria>/<id>/historico/` | Histórico local |
| `/api/v1/agendamentos/` | Listar ou criar registros locais |
| `/api/v1/agendamentos/<categoria>/<id>/` | Consultar, editar ou cancelar registro local |
| `/api/v1/agendamentos/<categoria>/<id>/historico/` | Consultar eventos locais |

Nas rotas locais, `<categoria>` é `servico` ou `equipamento`. A API de criação mantém o payload de categoria, objeto, motivo e período; material e equipamentos associados são campos exclusivos de serviços. Edição e cancelamento usam a versão atual do registro. Visita não é aceita como categoria de criação na API local. Consumidores que usavam apenas o ID precisam passar a categoria na URL; não há resolução arbitrária entre IDs iguais. Recibos externos retornam a categoria junto ao ID.

Materiais e equipamentos associados são exclusivos de serviços. As duas agendas preservam controle de versão, cancelamento com histórico, permissões e verificação transacional de conflitos. Associar equipamentos a um serviço mantém a regra anterior de não reservar automaticamente esses equipamentos.

## Fonte das visitas

Agendamentos mostra visitas confirmadas consultando a API autenticada. Solicitações continua com Todas, Pendentes, Canceladas e Recusadas. Confirmar muda a situação no AgroHub; na consulta seguinte a visita aparece na agenda, sem inserção local. Dashboard e calendário utilizam os mesmos dados remotos autorizados pela sessão.

Os botões de confirmar, recusar e cancelar continuam nas solicitações pendentes. Criação, detalhe, edição e cancelamento de visitas utilizam rotas próprias, separadas dos registros locais. O sistema verifica que a sala pertence ao InovaLab e valida a resposta do provedor antes de apresentar sucesso.

| Rota de visita | Uso |
| --- | --- |
| `/agenda/visitas/` | Consultar as visitas autorizadas pela sessão remota, incluindo pedidos pendentes |
| `/agenda/visitas/novo/` | Solicitar visita pela API |
| `/agenda/visitas/<id>/` | Consultar detalhe remoto |
| `/agenda/visitas/<id>/editar/` | Editar pela API |
| `/agenda/visitas/<id>/cancelar/` | Cancelar pela API |

A entrada de criação oferece três cards com ícones: Visita, Equipamento e Serviços. A escolha abre o formulário específico, com confirmação antes da gravação ou envio; consultar `15-fluxo-criacao-agendamento.md`. A lista de visitas permite reencontrar um pedido ainda pendente sem conceder acesso administrativo a Solicitações. Se uma criação tiver resultado inconclusivo, consultar essa lista antes de reenviar: não há repetição automática nem fila local para POST.

Se a consulta remota falhar, a interface informa que não foi possível carregar as visitas e continua mostrando os agendamentos locais. Não há dados antigos de visitas apresentados como atuais nem conciliação no banco local. Reservas canceladas ou recusadas permanecem consultáveis em Solicitações pela API.

| Operação | Endpoint do AgroHub |
| --- | --- |
| Consultar salas | `GET /api/v1/agendamentos/salas/?site_code=inovalab` |
| Consultar reservas | `GET /api/v1/agendamentos/reservas/?sala=<slug>` |
| Consultar uma visita | `GET /api/v1/agendamentos/reservas/<id>/` |
| Criar visita | `POST /api/v1/agendamentos/reservas/` |
| Editar visita | `PATCH /api/v1/agendamentos/reservas/<id>/` |
| Confirmar ou recusar | `PATCH /api/v1/agendamentos/reservas/<id>/` com `status=confirmada` ou `recusada` |
| Cancelar visita | `POST /api/v1/agendamentos/reservas/<id>/cancelar/` |

Criação e edição usam título, quantidade de pessoas, data e horários `HH:MM`, além das observações. A sala é identificada pelo slug. O provedor decide a situação inicial conforme a sala; a administração local não força confirmação na criação. Uma conta sem privilégio staff no provedor edita somente sua reserva pendente e não pode enviar alteração de sala ou status. Cancelar aceita reservas pendentes ou confirmadas futuras, sujeito à validação do provedor. Fontes primárias: [views da API](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/api/views.py), [serializers](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/api/serializers.py) e [regras de reservas](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/reservations.py), conferidas com o schema publicado em 07/10/2026.

As credenciais continuam na sessão Accounts; requisições usam o cliente existente, com refresh e restrição de origem. A API limita quais reservas a conta consegue consultar e alterar. Não há modificação do monólito nesta entrega.

## Preservação e recuperação

A migração copia serviços e equipamentos mantendo IDs, datas, versão, situação, material e associações. Eventos e recibos são religados antes da remoção da estrutura antiga.

Visitas e espaços históricos não têm destino nas duas novas agendas. Seus dados, eventos, recibos e vínculos anteriores são preservados fora do banco operacional, em arquivo privado ignorado pelo Git, antes de retirar as tabelas. Falha de preservação deve interromper a migração. Nenhuma reserva é criada ou alterada no AgroHub durante esse processo.

Antes de aplicar a migração local foi criado o backup consistente `%TEMP%\inovalab-antes-divisao-agendas-2026-10-07.sqlite3`, com integridade SQLite `ok`. Ele contém o estado anterior completo. Não substituir o banco de um ambiente em uso sem interromper os processos e conferir qual backup e qual versão do código correspondem à restauração. O arquivo de legado preserva registros históricos; a recuperação integral de um ambiente exige seu backup do banco e a versão anterior do código.

Não enviar arquivos privados de backup, exportações ou credenciais ao Git. Em outro ambiente, criar seu próprio backup antes de executar migrations.

Em desenvolvimento, o arquivo de legado fica em `.private/agenda-legacy/`, ignorado pelo Git. Fora de `DEBUG`, a migração com dados legados exige `AGENDAS_LEGACY_ARCHIVE_DIR` apontando para armazenamento privado durável; sem essa configuração, ela falha antes de excluir os registros. O nome do arquivo é único, para evitar substituir uma exportação anterior.

A reversão das agendas locais conserva novos registros e remapeia IDs quando as duas tabelas têm o mesmo número. Para também recuperar os dados retirados, selecionar explicitamente o arquivo correspondente com `AGENDAS_LEGACY_RESTORE_FILE` antes da reversão; o sistema não escolhe automaticamente o arquivo mais recente. As FKs referidas pelo arquivo, como usuário e cliente de integração, precisam existir no ambiente de recuperação. Em caso de dúvida sobre a origem do arquivo ou do banco, usar o backup completo correspondente em um ambiente separado.

A remoção da tabela antiga altera o esquema esperado pelo código anterior. Esta entrega fica na branch local, sem deploy. Em ambientes com migração durante o build, como o deploy Vercel/Neon deste projeto, preparar a preservação do legado fora do filesystem temporário do build e coordenar a troca de versão do código com a migração. Um rollback somente do código não recupera o esquema anterior.

## Verificação

```powershell
.\venv\Scripts\python.exe manage.py test --noinput
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe manage.py migrate --noinput
git diff --check
```

O roteiro cobre migração com os dois tipos locais, IDs iguais, material, equipamentos associados, datas, histórico, recibos e exportação de legado; CRUD, concorrência, versões, isolamento e idempotência; visitas consultadas e alteradas via stub HTTP sem persistência local; filtros, solicitações, calendário e dashboard.

Verificação visual depende de navegador disponível na sessão. Quando a ferramenta não disponibilizar superfícies, registrar o impedimento e executar verificações HTTP/renderização; a depuração visual de sidebar expandida/recolhida e móvel fica com o responsável. Decisões remotas reais devem ser depuradas em reservas próprias para teste. A verificação automatizada usa stub para não alterar reservas reais.

### Evidências desta entrega

A suíte completa `.\venv\Scripts\python.exe manage.py test --noinput` passou com **575 testes em 76,786 segundos**, código de saída zero. Os adaptadores e fluxos remotos passaram em 54 testes focados, incluindo a rechecagem que impede cancelar pela tela de Solicitações uma reserva já confirmada. A suíte relevante de agenda, core e integrações passou com 251 testes antes dessa correção; a suíte completa final inclui a nova regressão.

As verificações `check`, `makemigrations --check --dry-run` e `migrate --plan` passaram: sem problemas, sem alterações de model pendentes e sem migrações a aplicar. O banco e o backup SQLite retornaram integridade `ok`. O arquivo privado de legado preserva a única visita antiga, seu evento e seu vínculo remoto; as duas agendas locais permanecem com zero registros neste ambiente. Os cenários completos de preservação de serviços/equipamentos foram exercitados nos bancos temporários de teste.

As consultas HTTP no servidor local, com a sessão Accounts atual de equipe (`staff`), retornaram 200 para agenda, lista e detalhe de visitas, filtro de pendentes, formulários de criação, dashboard e API local. A visita confirmada apareceu na agenda por consulta remota. Solicitações e suas abas retornaram 403 para essa sessão, como exige a proteção administrativa; o acesso administrativo e as decisões foram cobertos pelos testes. Essas verificações não realizaram escritas no AgroHub e não alteraram as contagens das agendas locais.

A ferramenta de navegador apresentou inventário vazio, sem aplicações ou browsers conectados. Por isso, não foi possível avaliar visualmente a sidebar expandida/recolhida e o menu móvel; os templates e a navegação HTTP foram verificados. Essa avaliação visual permanece para a depuração pelo responsável.

A entrega fica na branch local `refactor/agendas-servicos-equipamentos`, no checkout usado pelo IDE, para depuração antes de outra etapa.
