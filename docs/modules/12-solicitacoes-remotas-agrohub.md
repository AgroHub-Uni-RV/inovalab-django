# Solicitações pendentes do AgroHub — 07/10/2026

O responsável solicitou que `/agenda/solicitacoes/` mostre as reservas pendentes exibidas em [reservas cadastradas do monólito](https://agrohub.unirv.edu.br/InovaLab/laboratorio/), consultadas pela API. O repositório `AgroHub-Uni-RV/unirv-monolith` foi consultado somente para leitura; as alterações desta entrega pertencem ao InovaLab Django.

A solicitação seguinte autoriza **Confirmar e Cancelar** ao lado de cada reserva. Ela amplia a entrega inicialmente limitada à consulta; as decisões abaixo alteram a reserva no AgroHub somente quando o administrador aciona um botão.

## Origem e autorização

O contrato utilizado é [Agendamentos](https://agrohub.unirv.edu.br/api/v1/schema/redoc/#tag/Agendamentos). Accounts fornece identidade, papéis e Bearer da sessão do usuário; as reservas são obtidas em Agendamentos.

A página do monólito filtra `sala__site_code=inovalab` e ordena por `-created_at`, `-pk`: [views/public.py](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/inovalab/views/public.py). A API utiliza `owned_by`: contas com a flag administrativa `is_staff` do provedor podem consultar todas as reservas, e as outras recebem somente as próprias. Isso foi conferido em [models.py](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/models.py) e [api/views.py](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/api/views.py).

O acesso à tela permanece exclusivo de administradores do laboratório conforme `roles` do Accounts. O provedor conserva a decisão sobre quais reservas cada Bearer pode consultar. Uma conta técnica somente local recebe orientação para entrar com uma conta administrativa vinculada ao AgroHub; não há credencial compartilhada.

## Consulta entregue

1. `GET /api/v1/agendamentos/salas/?site_code=inovalab&ativas=false` resolve as salas do site, incluindo inativas quando a conta tiver a permissão do provedor. `ativas=false` foi conferido no código da API do monólito.
2. Para cada sala, `GET /api/v1/agendamentos/reservas/?sala=SLUG&status=pendente` consulta as reservas. As duas listas usam `page` e `page_size=100` e Bearer da sessão.
3. Cada registro é validado e conferido novamente contra a sala/status solicitados; reservas de outros sites ou com situação confirmada/cancelada/recusada ficam fora da listagem. Duplicações iguais de ID são eliminadas e divergências interrompem a consulta.
4. Ordenação por criação/ID decrescentes acompanha o monólito. Busca por número/título/sala/solicitante e filtro opcional por mês de início, no fuso de Brasília, são aplicados aos registros consultados. A apresentação usa 25 registros por página.

A tabela mostra número/título, sala, nome do solicitante, período, quantidade de pessoas, situação Pendente e ações Confirmar/Cancelar. Não depende da existência de um `Agendamento` local. A consulta GET/HEAD não altera reservas. Os endpoints locais anteriores de avaliação continuam com suas permissões e validações, sem serem acionados por esta lista.

Falha de consulta ou resposta inválida exibe aviso com HTTP 503, sem apresentar um resultado vazio ou parcial como sucesso. Recusa de autenticação/permissão da consulta retorna 403. Consulta vazia bem-sucedida tem mensagem própria. A sessão suporta renovação com validação do mesmo usuário. A página usa `no-store`, texto externo escapado e o layout compartilhado do painel.

O cliente limita a consulta completa a 40 requisições de listagem, com até 100 registros por resposta e limite de 512 KB por resposta. URLs `next` nunca são seguidas: a paginação reconstrói a rota na origem configurada, preservando sala/status e evitando enviar Bearer a outra origem. Atingir o limite interrompe a listagem com aviso, sem truncamento silencioso. Não há migração de banco nesta entrega.

## Confirmar e cancelar

Cada linha contém um formulário POST com CSRF para `/agenda/solicitacoes/ID/decidir/`. O ID é o da reserva remota e não é utilizado para localizar ou criar um agendamento local. A view mantém o acesso exclusivo de administradores, exige vínculo/sessão AgroHub e aceita somente as decisões `confirmar`/`cancelar`, além dos campos de busca/mês para o retorno à lista. GET não executa decisões; campos desconhecidos ou repetidos são recusados.

Antes de alterar, consulta `GET /api/v1/agendamentos/reservas/ID/` e as salas InovaLab para validar o ID, a sala e a situação pendente. Reservas de outro site recebem 403; reservas já confirmadas/canceladas/recusadas recebem 409, sem novo envio da decisão.

| Botão | Operação no AgroHub | JSON |
| --- | --- | --- |
| Confirmar | `PATCH /api/v1/agendamentos/reservas/ID/` | `{"status":"confirmada"}` |
| Cancelar | `POST /api/v1/agendamentos/reservas/ID/cancelar/` | `{}` |

O Bearer é o da sessão do administrador. O AgroHub exige `is_staff` da conta do provedor para mudar o status; cancelamento permite proprietário ou staff e exige reserva pendente/confirmada que ainda não iniciou. As regras de horário/disponibilidade e demais validações permanecem na API: [endpoints](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/api/views.py), [regras de reserva](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/reservations.py). Papéis locais não concedem essas permissões ao provedor.

Só há mensagem de sucesso após conferir ID/sala/status da resposta. O retorno preserva busca/mês e recomeça na primeira página; a reserva decidida sai da lista de pendentes. Falhas 400/403/404 e conflitos 409 exibem orientação e link para as solicitações. Falha de conexão/servidor ou resposta inválida retorna 503 e pede atualização da lista para conferir o resultado, pois a API pode ter gravado a decisão antes de a resposta falhar. Não há repetição automática após essas falhas; a renovação de credenciais após 401 segue o cliente existente.

A API não disponibiliza versão/condição de atualização nesse contrato: a leitura antes do envio detecta decisões anteriores, mas não garante exclusão mútua entre dois administradores que decidam simultaneamente. Não há cópias locais de reservas nem mudanças no repositório do monólito.

## Validação e depuração

Comandos executados:

```powershell
.\venv\Scripts\python.exe manage.py test agenda.tests.test_remote_requests agenda.tests.test_requests --noinput
.\venv\Scripts\python.exe manage.py test --noinput
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Na entrega inicial, **37 testes específicos e 588 testes da suíte completa passaram**. Os resultados da entrega com botões estão registrados abaixo.

Na entrega com Confirmar/Cancelar, **45 testes específicos e 596 testes da suíte completa passaram**. O check do Django não encontrou problemas, não há migrações a gerar e `git diff --check` passou.

Testes HTTP com provedor isolado cobrem Bearer/papéis, todas as salas InovaLab inclusive inativas, status pendente, exclusão de outros sites/situações, ausência de gravações locais/remotas de reservas, ordenação, busca, mês, paginação, URL next externa, limite de consulta, refresh, permissão negada, falhas/respostas inválidas, conta somente local e escape de texto externo.

A verificação HTTP real da entrega com botões em `/agenda/solicitacoes/`, pela sessão administrativa existente, retornou **200 com 6 botões Confirmar e 6 Cancelar**, CSRF e `no-store`. Na entrega inicial havia cinco reservas pendentes. As verificações no provedor real foram consultas; as decisões foram verificadas com o servidor HTTP isolado dos testes.

Os testes das ações cobrem confirmação/cancelamento e saída da lista, ID remoto, sala de outro site, reserva já decidida, CSRF, papéis, conta somente local, métodos HTTP, campos forjados/repetidos, mês/ID inválidos, erros do provedor, resultado inconclusivo sem repetição, resposta inválida, renovação de Bearer e ausência de gravações locais de reservas.

Verificação visual pendente: o inventário de ferramentas desta sessão não disponibilizou apps nem navegadores. Conferir a tabela/botões com sidebar expandida/recolhida, navegação/paginação, busca/mês e layout móvel. Depurar também com reservas apropriadas para teste e as demais contas reais, inclusive recusa por falta de permissão no provedor. As ações permanecem sujeitas às permissões e à disponibilidade da API.
