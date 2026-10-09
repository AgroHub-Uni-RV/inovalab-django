# Execução de agendamentos: serviços e visitas

Data: 08/10/2026. Etapa: desenho escrito para revisão do responsável; implementação ainda não iniciada.

## Objetivo e decisões aprovadas

Identificar o que foi efetivamente concluído e o que ainda exige atenção, sem confundir aprovação de uma solicitação com execução do agendamento.

O responsável aprovou:

- Serviços concluídos automaticamente quando todas as tarefas válidas vinculadas estiverem concluídas, exigindo pelo menos uma tarefa. Tarefas excluídas não entram na conta.
- Serviços confirmados, não cancelados e ainda não concluídos ficam atrasados depois do prazo. Conclusão posterior ao prazo aparece como Concluído com atraso.
- Reabrir uma tarefa faz o serviço deixar de estar concluído; o atraso é reavaliado.
- Visitas não são concluídas pelo simples decurso da data. Somente administradores ativos podem registrar sua realização.
- A ação se chama Marcar como realizada, distinta de Confirmar, que continua aprovando a solicitação.
- A ação pode ser executada a partir do horário de início, inclusive antes do horário de término.
- Visitas confirmadas que passaram do término sem registro aparecem como Aguardando encerramento, não como Atrasadas.
- Cancelados e recusados não recebem alertas de atraso ou execução pendente.

Este documento consolida essas decisões e propõe os detalhes técnicos abaixo para revisão. Sua aprovação precede o plano e a implementação.

## Separação entre aprovação e execução

Preservar `situacao`, seus valores e contratos atuais: `pendente`, `confirmado`, `rejeitado`, além de `cancelado_em`. A interface mantém as traduções existentes. Concluir um serviço ou registrar uma visita não substitui Confirmado, não muda o aprovador e não remove registros de Solicitações.

Adicionar uma representação de execução compartilhada, somente leitura. Serviços e visitas confirmados e não cancelados participam dela; os demais registros têm execução não aplicável. Equipamentos históricos permanecem fora desta mudança.

| Categoria e condição | Execução exibida |
| --- | --- |
| Serviço com pelo menos uma tarefa válida e todas concluídas | Concluído ou Concluído com atraso |
| Serviço não concluído, com instante atual maior que o prazo | Atrasado |
| Serviço não concluído, antes ou exatamente no prazo | Em aberto |
| Visita com realização registrada | Realizada |
| Visita sem registro, com instante atual maior que o término | Aguardando encerramento |
| Visita sem registro, antes ou exatamente no término | Em aberto |
| Pendente, recusado, cancelado ou equipamento histórico | Não aplicável |

Os limites usam data e hora completas com fuso horário do projeto. A comparação é estrita para atraso/encerramento pendente: exatamente no prazo ou término ainda não ultrapassou o limite.

## Serviços: estado derivado das tarefas

Considerar somente as tarefas daquele `AgendaServico`, com `excluida_em` nulo. Um serviço sem tarefas válidas não é concluído por vacuidade: continua em aberto ou atrasado. A regra de criar tarefa para confirmar novas solicitações permanece intacta.

Quando todas estiverem concluídas, a conclusão do serviço é a maior data de `conclusao` entre essas tarefas. Exibir Concluído com atraso quando essa data for maior que o prazo atual do serviço. Atraso em aberto e conclusão com atraso são indicadores diferentes: um serviço concluído não permanece na lista de Atrasados.

Calcular a representação a partir dos registros atuais, sem uma segunda coluna de status a ser sincronizada e sem job periódico. Alterações de status pelo detalhe, API ou drag-and-drop, criação/exclusão/revinculação de tarefas e mudanças de prazo se refletem na próxima consulta. Os filtros e as listas devem usar a mesma regra, evitando uma etiqueta calculada de forma diferente do contador.

Os históricos existentes de tarefas e de alterações do serviço continuam sendo a fonte de auditoria. A classificação não grava eventos ao consultar páginas. Reabertura e nova conclusão seguem as datas e eventos atuais das tarefas. O histórico do prazo permanece nos eventos do serviço; esta entrega não cria um prazo congelado adicional.

Preparar contagem de tarefas válidas, contagem não concluída e maior conclusão em lote nas consultas, evitando carregar responsáveis, materiais ou descrições das tarefas apenas para calcular execução. Isso também evita divulgar tarefas individuais para o titular do agendamento.

## Visitas: registro persistido e ação administrativa

Adicionar em `AgendaVisita` os metadados não editáveis `realizada_em` e `realizada_por`, com usuário do hospedeiro via `settings.AUTH_USER_MODEL`. O instante registra quando o administrador confirmou a realização; não pretende medir a hora real em que os visitantes saíram.

Uma operação de domínio para Marcar como realizada deve:

1. Exigir administrador de negócio ativo, também para visitas do próprio administrador.
2. Carregar somente a categoria visita e exigir solicitação confirmada, não cancelada, ainda sem realização.
3. Validar a versão positiva recebida e verificar, no servidor, que o instante atual é maior ou igual ao início.
4. Persistir administrador/instante, incrementar versão e registrar o evento `realizar` em uma única transação, usando a proteção de concorrência existente.
5. Rejeitar reenvio ou conflito sem duplicar o evento e orientar a consultar os dados atualizados.

A interface oculta a ação antes do início, depois da realização e nos pendentes/recusados/cancelados. Ocultar não substitui a validação de domínio. Não é necessário aguardar o término; visitas com encerramento pendente podem ser registradas normalmente.

Proposta de coerência para revisão: manter as edições atualmente autorizadas, mas impedir uma edição de data/horário que mova o início para depois de `realizada_em`, pois isso tornaria o registro uma realização de visita futura. Alterar observações não remove a realização. Não adicionar ação de desfazer realização, registro de ausência ou remarcação especial nesta entrega.

As regras atuais de cancelamento permanecem; se um agendamento realizado for cancelado por uma ação já permitida, Cancelado prevalece na exibição, sem apagar o registro de realização ou o histórico.

## UX e integração

- Mostrar execução em Agenda, detalhes, Meus agendamentos e representações existentes no dashboard/Solicitações, com os mesmos rótulos e uma apresentação compartilhada. Manter o status de aprovação identificável, sem trocar as abas administrativas existentes.
- Preservar `sheet-layout`, topbars padronizadas, ações existentes e todos os conteúdos; acrescentar a execução junto ao status, com quebra móvel e sem depender somente de cor.
- No detalhe da visita, oferecer Marcar como realizada somente quando permitido e exibir quem registrou e quando, em `dd/mm/aaaa hh:mm`.
- Oferecer filtro adicional de execução em Agenda e Meus agendamentos: Todos, Em aberto, Concluídos, Atrasados e Aguardando encerramento. Em aberto inclui serviços não concluídos e visitas não realizadas, inclusive os que têm alertas; Concluídos inclui serviços concluídos e visitas realizadas; Atrasados inclui somente serviços em aberto vencidos. Aguardando encerramento inclui somente visitas vencidas sem realização. Esses filtros de execução excluem os registros não aplicáveis; Todos não acrescenta essa restrição. Manter busca, mês, categoria, paginação e Limpar filtros.
- Usar POST com CSRF e versão no fluxo web, com alternativa sem JavaScript e retorno ao detalhe. Atualizar o conteúdo após a ação sem repetir a gravação automaticamente em falhas de conexão.
- Na API, acrescentar informações de execução somente leitura e uma ação administrativa específica de realização de visita. Não liberar a escrita desses metadados por criação/PATCH comum, nem aceitar novos valores em `situacao`.
- As etiquetas temporais são reavaliadas a cada consulta. Não prometer polling, atualização entre abas ou alteração automática de uma página deixada aberta e sem novas consultas.

## Compatibilidade e migração

Apenas visitas precisam de novos campos persistidos e do novo tipo de evento. A migração deixa a realização nula nos registros existentes; não presumir que visitas históricas aconteceram por estarem no passado. Visitas antigas confirmadas e vencidas aparecem como Aguardando encerramento até registro administrativo.

Serviços históricos são classificados pelas tarefas válidas existentes; registros confirmados sem tarefas permanecem em aberto/atrasados, sem criar tarefas ou datas fictícias. Preservar IDs, vínculos, arquivos, autoria, versões e eventos. Não alterar Accounts, papéis atuais, equipamentos históricos ou o repositório do monólito.

As mudanças de resposta da API são aditivas. As autorizações de consulta continuam limitando os registros pessoais; a agregação de execução não concede acesso às tarefas vinculadas.

## Alternativas consideradas

1. **Execução derivada para serviços, realização persistida para visitas (proposta):** evita sincronização duplicada e registra a decisão humana onde ela é necessária.
2. **Um único status misturando aprovação, atraso e conclusão:** alteraria contratos/permissões e apagaria a distinção entre agendamento aprovado e executado.
3. **Conclusão automática de visitas ao passar o horário:** simples, mas atestaria uma realização sem comprovação; rejeitada pelo responsável.

## Critérios de aceite e testes da implementação

- Serviço com uma tarefa; várias tarefas; conclusão parcial; ausência de tarefas; exclusão de tarefa; reabertura; nova conclusão; criação ou mudança de vínculo após conclusão.
- Limites antes/exatamente/depois do prazo, conclusão no prazo e posterior, prazo alterado e fuso horário.
- Nenhum alerta de execução em pendentes, recusados e cancelados; equipamento histórico inalterado.
- Visita antes/exatamente/depois do início, realização anterior ao término, encerramento pendente depois do término e ausência de conclusão automática.
- Administrador autorizado; responsável interno, visitante titular, conta inativa e anônimo proibidos de registrar realização, inclusive pela API.
- Versão antiga, duas requisições concorrentes, reenvio, CSRF ausente e falha transacional não duplicam ou deixam gravações parciais.
- Migração conserva registros e deixa visitas antigas sem realização presumida; edição não produz realização anterior ao início.
- Coerência entre etiquetas, filtros, contadores, listas e API; consulta pessoal sem vazamento de tarefas; URLs com prefixo e usuário nativo do hospedeiro.
- Fluxos desktop/móvel, teclado, sem JavaScript, atualização após ação, filtros/limpeza, retorno e preservação dos layouts.
- Executar suíte Django completa, testes do hospedeiro nativo e verificações básicas no navegador. A depuração profunda pelo responsável permanece após a entrega.

## Próxima etapa

Revisar esta especificação, incluindo os detalhes propostos de edição e apresentação. Após aprovação escrita, preparar o plano de implementação e submetê-lo ao responsável antes de alterar código ou banco.
