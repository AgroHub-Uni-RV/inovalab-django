# Gerenciamento e execução de agendamentos

Entrega de 09/10/2026, conforme especificação aprovada em 08/10/2026. A aprovação da solicitação continua independente da execução: concluir não altera `situacao`, aprovador ou cancelamento.

## Regras e apresentação

`/agenda/solicitacoes/` conserva URL, nomes de rota e acesso administrativo, agora com título Gerenciamento de agendamentos. Todas mantém colunas por aprovação e etiquetas de execução. Confirmadas contém Aguardando início, Em execução e Concluídos; visitas vencidas não realizadas aparecem em Aguardando encerramento e equipamentos históricos em seção própria. Contadores consideram todo o conjunto filtrado, cartões respeitam a paginação global de 25 registros, sem duplicação por categoria/ID.

Serviços consideram somente tarefas vinculadas não excluídas:

- Pelo menos uma tarefa e todas concluídas: Concluído; instante da maior conclusão. Se posterior ao prazo atual: Concluído com atraso, sem alerta de atraso em aberto.
- Alguma tarefa iniciada, sem conclusão de todas: Em execução. Início conservado ao retornar a Demanda continua sendo evidência de execução.
- Nenhuma tarefa iniciada (inclusive nenhum vínculo válido): Aguardando início.
- Não concluído e `agora > prazo`: etiqueta adicional Atrasado; exatamente no prazo não está atrasado.

Reabertura, exclusão, novo vínculo, revinculação e mudança do prazo se refletem na próxima consulta, sem criar datas, tarefas fictícias, eventos de leitura ou espelho de status.

Visitas não realizadas: antes do início Aguardando início; `inicio <= agora < fim` Em execução; a partir do término Aguardando encerramento. Não são concluídas automaticamente nem classificadas como Atrasadas. Realização registrada prevalece sobre o intervalo, inclusive antes do término.

Pendentes, recusados, cancelados e equipamentos históricos não recebem execução/alertas. Cancelamento permitido de visita realizada conserva o registro e o histórico, prevalecendo na apresentação. Equipamentos mantêm sua seleção temporal antiga no dashboard.

Agenda, detalhes, Meus agendamentos e dashboard reutilizam o fragmento de etiquetas. Os detalhes mantêm sheet-layout/topbars e conteúdo. O filtro `execucao` aceita vazio/Todos, `aguardando_inicio`, `em_execucao`, `concluido`, `atrasado`, `aguardando_encerramento`; combina com os filtros existentes, sem trocar a aba de aprovação. Limpar filtros também o remove, preservando `mes=` na Agenda para limpar o mês padrão administrativo.

## Realização administrativa de visitas

Somente administrador de negócio ativo pode Marcar como realizada, a partir do início, em visita confirmada não cancelada e ainda não realizada. Titularidade, papel de responsável ou equipe não concedem essa ação. Confirmação de serviços continua exigindo criar uma nova tarefa na mesma transação.

- Web: POST `visita/<id>/realizar/` (`agenda:visit-realize`), CSRF, `versao` inteira positiva e `retorno` opcional.
- API: POST `agendamentos/visita/<id>/realizar/` (`agendamentos-realizar`), somente `versao`.
- Transação única: instante/administrador, incremento de versão e um evento `realizar`. Conflitos/reenvios não duplicam eventos.
- Retorno web: somente detalhe da própria visita ou gerenciamento sob o prefixo do hospedeiro; preserva query validada e recupera paginação válida. URL externa/malformada retorna ao detalhe.
- Sucesso: web 302, API 200; validação 400, conflito 409, não autorizado 403, inexistente 404. GET não realiza visitas.

Os detalhes mostram realização em `dd/mm/aaaa hh:mm` e administrador. Se a conta for removida, a FK fica nula e o nome vem do evento histórico. Edição de data/horário não pode mover início para depois de `realizada_em`; observações e cancelamento permitido não apagam a realização. Não há desfazer realização ou registrar ausência nesta entrega.

## Modelagem e API

`agenda/execution.py` centraliza política, agregações e filtro. `ExecutionState` é representação somente leitura; propriedades não são colunas. Agregações de tarefas são preparadas em lote após seleção autorizada, sem carregar descrições/responsáveis/materiais privados por cartão. Cada resposta usa um único instante de referência.

Respostas de agendamento acrescentam `estado_execucao`, `atrasado`, `concluido_com_atraso`, `concluido_em`; visitas também expõem `realizada_em` e `realizada_por` por ID. Os novos campos são somente leitura e payloads comuns que tentam gravá-los são rejeitados, mantendo contratos estritos. Consulta pessoal não passa a conceder acesso às tarefas.

Classificações temporais mudam na próxima consulta. Não há polling, job periódico, sincronização entre abas ou atualização de uma página deixada aberta sem nova consulta. POST de realização usa navegação/retorno normal, também sem JavaScript, e não é repetido automaticamente após erro de rede.

## Atualização do ambiente

Migração `0007_realizacao_visitas`: somente os campos anuláveis não editáveis `realizada_em`, `realizada_por` (usuário do hospedeiro) e escolha de evento `realizar`. Não presume realização histórica. Visitas antigas confirmadas vencidas ficam Aguardando encerramento até registro administrativo.

O SQLite de trabalho e bancos publicados não foram migrados nesta entrega. Antes de executar a nova versão num ambiente existente: fazer backup, coordenar a atualização e aplicar `python manage.py migrate` no banco escolhido. Deploy é etapa separada. Testes usam bancos descartáveis; o hospedeiro nativo usa `auth.User`, URLs `/laboratorio/` e não exige Accounts.

## Verificações

- `python manage.py check`: sem erros.
- `python manage.py makemigrations --check --dry-run`: nenhuma alteração de modelo sem migração.
- `python manage.py test --noinput`: 633 testes, OK.
- `python manage.py test inovalab_app.tests.portability --settings=inovalab_app.tests.host_settings --noinput`: 10 testes, OK.
- `node scripts/verificar-execucao-agendamentos.cjs`: grupos, contadores/paginação, filtros/limpeza, realização com um POST/um evento/uma versão, API/detalhes, teclado/celular, sem JS, 403/409/sessão expirada/rede e axe WCAG A/AA.
- O novo verificador falhou na versão anterior `da6974a` em cópia descartável: grupo Aguardando início ausente. Nenhum arquivo do checkout foi revertido.
- Regressões: `node scripts/verificar-limpeza-filtros.cjs` e `node scripts/verificar-movimento-tarefas.cjs`, com bancos/sessões descartáveis.

### Fixtures do navegador

Executar somente contra servidor/banco descartável com migrations aplicadas. `AGENDA_TEST_BASE_URL` inclui o prefixo (ex.: `http://127.0.0.1:8130/laboratorio`); `AGENDA_TEST_ADMIN_SESSION` é sessão de administrador ativo e `AGENDA_TEST_OWNER_SESSION` de titular externo. `AGENDA_TEST_AXE_PATH` é opcional, aponta para axe-core; disponibilizar playwright-core por instalação local ou `NODE_PATH`. Não registrar os valores das sessões.

O verificador é mutante: registra duas realizações. Preparar fixtures novas antes de repetir. Busca usa `Execução browser`, com 28 confirmados e três registros de controle:

- Três serviços, título com esse prefixo: um aguardando com prazo futuro, um iniciado ainda aberto com prazo passado, um concluído após o prazo. As tarefas válidas têm status/datas coerentes.
- Vinte outros serviços com prazo antigo, sem início, para paginação. Os cenários principais têm prazo/data mais recentes, aparecendo na primeira página; a segunda contém três cartões.
- Quatro visitas do titular externo, com observações exatas `Execução browser · futura`, `Execução browser · em curso`, `Execução browser · encerramento`, `Execução browser · realizada`: futura, durante o intervalo, vencida sem realização, realizada. A visita em curso deve permanecer no intervalo durante todo o teste.
- Um equipamento histórico confirmado com nome contendo o prefixo.
- Um serviço pendente, um recusado e um cancelado, título com o prefixo, sem alerta de execução.

As regressões de filtros/movimento exigem suas fixtures próprias, incluindo pelo menos 26 tarefas em Demanda, atribuídas ao responsável de teste. Rodar execução antes do movimento, que altera os status dessas tarefas. Depuração profunda, validação PostgreSQL real e deploy ficam para a etapa do responsável; nenhuma nova regra de outro módulo foi iniciada.
