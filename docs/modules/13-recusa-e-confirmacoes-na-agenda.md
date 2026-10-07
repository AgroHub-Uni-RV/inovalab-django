# Recusa e confirmações na agenda — 07/10/2026

O responsável autorizou adicionar Recusar às solicitações pendentes e determinou que reservas confirmadas sejam agendamentos do sistema, sem coluna Confirmadas em Solicitações. A autorização permite persistir as confirmadas localmente; pendentes/canceladas/recusadas sem vínculo anterior continuam sendo consultadas diretamente na API. O repositório do monólito permanece sem alterações.

## Recusar

O botão Recusar fica ao lado de Confirmar e Cancelar nas pendentes. Usa o formulário POST com CSRF existente e `decisao=recusar`. O servidor confere acesso administrativo, sessão AgroHub, ID/sala InovaLab e status pendente antes de enviar:

```http
PATCH /api/v1/agendamentos/reservas/ID/
Authorization: Bearer TOKEN_DA_SESSAO
Content-Type: application/json

{"status":"recusada"}
```

Não existe uma action `/recusar/` nesse contrato: usa atualização parcial de status. A conta precisa de `is_staff` no AgroHub para alterar status. Fontes consultadas somente para leitura: [serializer](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/api/serializers.py), [permissões de alteração](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/reservations.py). Confirmação continua usando PATCH com `confirmada`, e cancelamento usa POST em `/cancelar/`.

Só há sucesso após validar ID/sala/status e os campos completos da resposta. Recusada permanece na coluna Recusadas em Todas, sem botões, e não cria agendamento. Abas, busca, mês, paginação, renovação de credenciais e erros do provedor seguem o fluxo anterior.

## Agendamentos confirmados

Solicitações mantém abas Todas/Pendentes/Canceladas/Recusadas e colunas Pendentes/Canceladas/Recusadas. A solicitação posterior acrescenta a aba Recusadas com `status=recusada`, preservando busca/mês/paginação e mensagem própria de resultado vazio. Todas e seus contadores excluem confirmadas. Há um link para Agendamentos explicando onde consultar as confirmadas.

A solicitação posterior move o acesso a Solicitações da sidebar para o cabeçalho de `/agenda/`, antes de Adicionar Agendamento. O link usa `secondary-button`, fundo branco e contorno azul, visível para administradores. O grupo de ações fica lado a lado no desktop e se organiza verticalmente no celular. A sidebar destaca Agendamentos também nas solicitações.

Validação dessa mudança: **606 testes passaram**, Django check/diff sem problemas e HTTP real **200** em `/agenda/`, com link ausente da sidebar e botão secundário antes de Adicionar Agendamento. Conferência visual no navegador permanece pendente.

A leitura autenticada por administrador em `/agenda/solicitacoes/` ou `/agenda/` consulta todas as reservas das salas InovaLab e concilia o resultado completo antes de aplicar os filtros de tela. Assim, uma confirmação anterior não depende de estar no mês, busca, aba ou página selecionados para entrar na agenda. Depois do PATCH de confirmação, a resposta validada é conciliada imediatamente, antes da mensagem de sucesso.

`reconcile_reservations` utiliza uma transação local e o controle de concorrência da agenda de visitas. `ReservaAgroHub` mantém o vínculo único `(origem, reserva_id)` já existente, e ganha `recebida`, booleano inicialmente falso para preservar as integrações de saída anteriores.

- Confirmada sem vínculo cria **um `Agendamento` confirmado de categoria Visita**, com início, fim e quantidade de pessoas recebidos. Não há criação de modelo/cadastro de Espaço.
- O vínculo marca `recebida=True` e conserva título, nome do solicitante, sala/slug/ID, período e criação remota em metadados. A lista, o calendário e os detalhes usam o título e o solicitante do provedor. Não se inventa uma conta local para o solicitante; `criado_por` fica vazio nas recebidas. O histórico identifica a conciliação como AgroHub.
- Vínculo de saída já existente é reaproveitado, atualizando a visita correspondente sem criar outra. Payloads de saída e operações locais ainda pendentes são preservados; uma consulta não substitui uma intenção local ainda não enviada.
- Atualizações de título, período e pessoas nas recebidas atualizam o mesmo agendamento. Nova consulta sem mudanças não incrementa versão nem cria evento.
- Cancelamento, recusa ou retorno a pendente de uma recebida existente retira sua ocupação do calendário e preserva o registro/histórico. Confirmada novamente reativa o mesmo vínculo. Uma reserva ausente do resultado não é excluída: a visibilidade da API pode mudar.
- Não são feitas requisições de criação de reservas no AgroHub durante essa conciliação. Uma recebida não utiliza o fluxo de reenvio das visitas criadas localmente.

Reservas recebidas podem ser consultadas na lista, calendário, detalhes, histórico e API interna conforme as permissões existentes. Editar/cancelar localmente uma recebida é bloqueado no serviço e os respectivos controles ficam ocultos; suas alterações são feitas no sistema de origem e recebidas na próxima consulta. Isso evita que uma edição local reenvie uma reserva sem a referência usada pelas integrações de saída. Visitas originalmente criadas neste sistema preservam o fluxo anterior.

O calendário recebe confirmadas de todas as salas InovaLab autorizadas pelo provedor. Para conflito de novas visitas locais, destinadas à sala 1, recebidas de outras salas não bloqueiam o horário. A API do provedor continua responsável pela disponibilidade da sala específica.

Dados incompletos/inválidos ou falha de paginação impedem a conciliação parcial. Falha na consulta de Solicitações mostra o erro; na agenda, um aviso informa que os últimos dados recebidos permanecem disponíveis. Caso o PATCH seja aceito e a resposta ou gravação local falhe, atualizar a tela concilia a confirmação. A sincronização acontece nessas consultas e nas decisões; não há webhook ou processo de atualização em segundo plano.

## Migração e validação

Migração `agenda.0012_identifica_reservas_recebidas_agrohub` aplicada localmente. Backup anterior em `%TEMP%\inovalab-antes-importacao-reservas-2026-10-07.sqlite3`. Em outro ambiente, executar `manage.py migrate` antes de iniciar o código atualizado.

```powershell
.\venv\Scripts\python.exe manage.py migrate --noinput
.\venv\Scripts\python.exe manage.py test agenda.tests.test_remote_requests agenda.tests.test_requests agenda.tests.test_agrohub --noinput
.\venv\Scripts\python.exe manage.py test --noinput
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check
```

As verificações cobrem recusa por PATCH, ausência de coluna Confirmadas, conversão imediata e de confirmações anteriores, idempotência, título/solicitante/período/pessoas, calendário, busca, edição/cancelamento local bloqueados para recebidas, atualização/cancelamento remoto, reaproveitamento de saída, preservação de operações pendentes, ausência de importação parcial e conflitos entre salas distintas. Mantêm os testes anteriores de papéis, CSRF, origem, paginação, falhas e resultados inconclusivos.

**606 testes da suíte completa passaram**, incluindo os novos cenários. `manage.py check`, `makemigrations --check --dry-run` e `git diff --check` passaram.

Na entrega da aba Recusadas, a consulta real a `/agenda/solicitacoes/?status=recusada` retornou **200**, com a aba ativa e somente a coluna Recusadas, sem erro. O teste de recusa também verifica o filtro, a preservação da aba e o resultado vazio dessa tela. Os **606 testes passaram novamente**, e check/migrações/diff passaram sem mudanças de banco.

HTTP real: `/agenda/solicitacoes/` retornou **200**, com **4 botões Recusar**, sem coluna Confirmadas ou erro. Uma reserva anteriormente confirmada gerou **um vínculo recebido**; `/agenda/?mes=` retornou **200** e manteve esse mesmo vínculo, sem duplicação. Essa verificação consultou a API e registrou a confirmação localmente; não executou decisões em reservas reais.

Depuração visual pendente: o inventário da sessão não disponibilizou navegador. Conferir botões/cartões com sidebar expandida/recolhida e layout móvel, além da reserva recebida na lista, calendário e detalhe, selecionando seu mês. Depurar decisões reais em reservas apropriadas para teste e com as demais contas autorizadas.
