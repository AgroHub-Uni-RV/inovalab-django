# Solicitações pendentes do AgroHub — 07/10/2026

O responsável solicitou que `/agenda/solicitacoes/` mostre as reservas pendentes exibidas em [reservas cadastradas do monólito](https://agrohub.unirv.edu.br/InovaLab/laboratorio/), consultadas pela API. O repositório `AgroHub-Uni-RV/unirv-monolith` foi consultado somente para leitura; as alterações desta entrega pertencem ao InovaLab Django.

## Origem e autorização

O contrato utilizado é [Agendamentos](https://agrohub.unirv.edu.br/api/v1/schema/redoc/#tag/Agendamentos). Accounts fornece identidade, papéis e Bearer da sessão do usuário; as reservas são obtidas em Agendamentos.

A página do monólito filtra `sala__site_code=inovalab` e ordena por `-created_at`, `-pk`: [views/public.py](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/inovalab/views/public.py). A API utiliza `owned_by`: contas com a flag administrativa `is_staff` do provedor podem consultar todas as reservas, e as outras recebem somente as próprias. Isso foi conferido em [models.py](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/models.py) e [api/views.py](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/api/views.py).

O acesso à tela permanece exclusivo de administradores do laboratório conforme `roles` do Accounts. O provedor conserva a decisão sobre quais reservas cada Bearer pode consultar. Uma conta técnica somente local recebe orientação para entrar com uma conta administrativa vinculada ao AgroHub; não há credencial compartilhada.

## Consulta entregue

1. `GET /api/v1/agendamentos/salas/?site_code=inovalab&ativas=false` resolve as salas do site, incluindo inativas quando a conta tiver a permissão do provedor. `ativas=false` foi conferido no código da API do monólito.
2. Para cada sala, `GET /api/v1/agendamentos/reservas/?sala=SLUG&status=pendente` consulta as reservas. As duas listas usam `page` e `page_size=100` e Bearer da sessão.
3. Cada registro é validado e conferido novamente contra a sala/status solicitados; reservas de outros sites ou com situação confirmada/cancelada/recusada ficam fora da listagem. Duplicações iguais de ID são eliminadas e divergências interrompem a consulta.
4. Ordenação por criação/ID decrescentes acompanha o monólito. Busca por número/título/sala/solicitante e filtro opcional por mês de início, no fuso de Brasília, são aplicados aos registros consultados. A apresentação usa 25 registros por página.

A tabela mostra número/título, sala, nome do solicitante, período, quantidade de pessoas e situação Pendente. Não depende da existência de um `Agendamento` local. A consulta não cria/agrega registros locais de reservas nem altera a situação no AgroHub; a tela aceita GET/HEAD e não contém formulários de aprovação/recusa. Os endpoints locais anteriores de avaliação continuam com suas permissões e validações, sem serem acionados por esta lista.

Falha de consulta ou resposta inválida exibe aviso com HTTP 503, sem apresentar um resultado vazio ou parcial como sucesso. Recusa de autenticação/permissão da consulta retorna 403. Consulta vazia bem-sucedida tem mensagem própria. A sessão suporta renovação com validação do mesmo usuário. A página usa `no-store`, texto externo escapado e o layout compartilhado do painel.

O cliente limita a consulta completa a 40 requisições de listagem, com até 100 registros por resposta e limite de 512 KB por resposta. URLs `next` nunca são seguidas: a paginação reconstrói a rota na origem configurada, preservando sala/status e evitando enviar Bearer a outra origem. Atingir o limite interrompe a listagem com aviso, sem truncamento silencioso. Não há migração de banco nesta entrega.

## Validação e depuração

Comandos executados:

```powershell
.\venv\Scripts\python.exe manage.py test agenda.tests.test_remote_requests agenda.tests.test_requests --noinput
.\venv\Scripts\python.exe manage.py test --noinput
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Resultados: **37 testes específicos e 588 testes da suíte completa passaram**. O check do Django não encontrou problemas, não há migrações pendentes de geração e a verificação do diff passou.

Testes HTTP com provedor isolado cobrem Bearer/papéis, todas as salas InovaLab inclusive inativas, status pendente, exclusão de outros sites/situações, ausência de gravações locais/remotas de reservas, ordenação, busca, mês, paginação, URL next externa, limite de consulta, refresh, permissão negada, falhas/respostas inválidas, conta somente local e escape de texto externo.

A verificação HTTP real em `/agenda/solicitacoes/`, pela sessão administrativa existente, retornou **200 com 5 reservas pendentes** e sem mensagem de falha. Foram feitas somente consultas de reservas no provedor; nenhum cadastro ou avaliação de reserva real foi executado.

Verificação visual pendente: o inventário de ferramentas desta sessão não disponibilizou apps nem navegadores. Conferir a tabela com sidebar expandida/recolhida, navegação/paginação, busca/mês e layout móvel, além de confirmar os cinco registros com a página do monólito e as permissões das demais contas reais. A consulta permanece sujeita às permissões e à disponibilidade da API.
