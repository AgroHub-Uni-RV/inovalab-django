# Gerenciamento e execução de agendamentos: serviços e visitas

Data: 08/10/2026. Etapa: especificação escrita aprovada pelo responsável; plano de implementação aguarda revisão e escolha de execução. Implementação ainda não iniciada.

## Objetivo e decisões aprovadas

Transformar a apresentação de Solicitações em Gerenciamento de agendamentos, identificando o que aguarda início, está em execução, foi concluído ou ainda exige atenção, sem confundir aprovação de uma solicitação com execução do agendamento.

O responsável aprovou:

- Renomear a página para Gerenciamento de agendamentos, preservando sua URL, acesso administrativo e fluxo de aprovação.
- Organizar as confirmadas em Aguardando início, Em execução e Concluídos. Serviços iniciam a execução pelas tarefas, sem novo botão de início.
- Visitas ficam Em execução somente durante o intervalo previsto e enquanto não houver registro de realização. Depois do término, sem registro, saem desse grupo e aparecem em uma seção de atenção Aguardando encerramento.
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

Preservar `situacao`, seus valores e contratos atuais: `pendente`, `confirmado`, `rejeitado`, além de `cancelado_em`. A interface mantém as traduções existentes. Concluir um serviço ou registrar uma visita não substitui Confirmado, não muda o aprovador e não remove registros do gerenciamento.

Adicionar uma representação de execução compartilhada, somente leitura. Serviços e visitas confirmados e não cancelados participam dela; os demais registros têm execução não aplicável. Equipamentos históricos permanecem fora desta mudança.

| Categoria e condição | Estado de execução | Alerta complementar |
| --- | --- | --- |
| Serviço com pelo menos uma tarefa válida e todas concluídas | Concluído | Concluído com atraso se a última conclusão superar o prazo |
| Serviço não concluído, com alguma tarefa válida iniciada | Em execução | Atrasado se o instante atual superar o prazo |
| Serviço não concluído, sem tarefa válida iniciada | Aguardando início | Atrasado se o instante atual superar o prazo |
| Visita com realização registrada | Concluído | Nenhum; exibir também os dados da realização |
| Visita sem registro, antes do início | Aguardando início | Nenhum |
| Visita sem registro, do início inclusive até o término exclusive | Em execução | Nenhum |
| Visita sem registro, a partir do término | Aguardando encerramento | Atenção administrativa, fora dos três grupos principais |
| Pendente, recusado, cancelado ou equipamento histórico | Não aplicável | Nenhum |

Os limites usam data e hora completas com fuso horário do projeto. Para serviços, atraso exige `agora > prazo`; conclusão exatamente no prazo não é tardia. Para visitas, o intervalo Em execução é `inicio <= agora < fim`: exatamente no término já pertence a Aguardando encerramento. Este limite substitui a comparação estrita de término da primeira versão do desenho. Realização registrada prevalece sobre o intervalo, inclusive quando registrada antes do término.

O atraso não substitui o estado de execução: um serviço pode estar Aguardando início e Atrasado, ou Em execução e Atrasado. Aguardando encerramento é uma classificação derivada específica de visitas, não um novo valor de aprovação.

## Serviços: estado derivado das tarefas

Considerar somente as tarefas daquele `AgendaServico`, com `excluida_em` nulo. Um serviço sem tarefas válidas não é concluído por vacuidade: permanece Aguardando início, com alerta Atrasado se vencer. A regra de criar tarefa para confirmar novas solicitações permanece intacta.

Primeiro verificar a conclusão de todas as tarefas válidas. Caso não estejam todas concluídas, alguma tarefa válida com `inicio` preenchido coloca o serviço Em execução; caso contrário, Aguardando início. O modelo atual conserva `inicio` ao retornar uma tarefa para Demanda: respeitar essa evidência de início, sem apagar datas ou alterar as transições existentes. Exclusão ou revinculação reavalia apenas as tarefas válidas que continuam ligadas ao serviço.

Quando todas estiverem concluídas, a conclusão do serviço é a maior data de `conclusao` entre essas tarefas. Exibir Concluído com atraso quando essa data for maior que o prazo atual do serviço. Atraso em aberto e conclusão com atraso são indicadores diferentes: um serviço concluído não permanece na lista de Atrasados.

Calcular a representação a partir dos registros atuais, sem uma segunda coluna de status a ser sincronizada e sem job periódico. Alterações de status pelo detalhe, API ou drag-and-drop, criação/exclusão/revinculação de tarefas e mudanças de prazo se refletem na próxima consulta. Os filtros e as listas devem usar a mesma regra, evitando uma etiqueta calculada de forma diferente do contador.

Os históricos existentes de tarefas e de alterações do serviço continuam sendo a fonte de auditoria. A classificação não grava eventos ao consultar páginas. Reabertura e nova conclusão seguem as datas e eventos atuais das tarefas. O histórico do prazo permanece nos eventos do serviço; esta entrega não cria um prazo congelado adicional.

Preparar contagem de tarefas válidas, contagem não concluída, existência de início e maior conclusão em lote nas consultas, evitando carregar responsáveis, materiais ou descrições das tarefas apenas para calcular execução. Isso também evita divulgar tarefas individuais para o titular do agendamento.

## Modelagem dos estados e alertas calculados

Persistir os fatos: aprovação/cancelamento, prazo do serviço, status e datas das tarefas, intervalo da visita e seu registro administrativo de realização. Não criar colunas `atrasado` ou um segundo status de execução para sincronizar.

Centralizar a classificação em uma política compartilhada, com um único instante de referência por resposta. Propriedades somente leitura como `estado_execucao`, `atrasado` e `concluido_com_atraso` podem expor essa política nos modelos; `@property` não cria coluna no banco. Nas listagens, usar as agregações em lote e condições equivalentes de consulta para filtros e contadores, sem consultar tarefas por cartão. Não tentar usar uma propriedade Python diretamente em `.filter(atrasado=True)` nem duplicar regras nos templates.

Consultar páginas não grava mudanças de estado, não incrementa versões e não produz eventos. Não é necessário um job periódico para atualizar alertas; eles são calculados ao consultar.

## Visitas: registro persistido e ação administrativa

Adicionar em `AgendaVisita` os metadados não editáveis `realizada_em` e `realizada_por`, com usuário do hospedeiro via `settings.AUTH_USER_MODEL`. O instante registra quando o administrador confirmou a realização; não pretende medir a hora real em que os visitantes saíram.

Uma operação de domínio para Marcar como realizada deve:

1. Exigir administrador de negócio ativo, também para visitas do próprio administrador.
2. Carregar somente a categoria visita e exigir solicitação confirmada, não cancelada, ainda sem realização.
3. Validar a versão positiva recebida e verificar, no servidor, que o instante atual é maior ou igual ao início.
4. Persistir administrador/instante, incrementar versão e registrar o evento `realizar` em uma única transação, usando a proteção de concorrência existente.
5. Rejeitar reenvio ou conflito sem duplicar o evento e orientar a consultar os dados atualizados.

A interface oculta a ação antes do início, depois da realização e nos pendentes/recusados/cancelados. Ocultar não substitui a validação de domínio. Não é necessário aguardar o término; visitas com encerramento pendente podem ser registradas normalmente.

Coerência de edição: manter as edições atualmente autorizadas, mas impedir uma edição de data/horário que mova o início para depois de `realizada_em`, pois isso tornaria o registro uma realização de visita futura. Alterar observações não remove a realização. Não adicionar ação de desfazer realização, registro de ausência ou remarcação especial nesta entrega.

As regras atuais de cancelamento permanecem; se um agendamento realizado for cancelado por uma ação já permitida, Cancelado prevalece na exibição, sem apagar o registro de realização ou o histórico.

## UX e integração

- Renomear título, cabeçalho e links de acesso de Solicitações para Gerenciamento de agendamentos. Preservar `/agenda/solicitacoes/`, nomes de rota, acesso exclusivo de administradores e seleção de Agendamentos na sidebar.
- Preservar as abas Todas, Pendentes, Confirmadas, Canceladas e Recusadas e seus contadores de aprovação. Na aba Confirmadas, apresentar os três grupos Aguardando início, Em execução e Concluídos, com a seção adicional Aguardando encerramento para visitas vencidas sem registro. Alertas de serviço aparecem no próprio cartão, sem duplicá-lo em outra seção.
- Na aba Todas, manter o agrupamento atual por aprovação e acrescentar etiquetas compactas de execução, sem aninhar três novos quadros na coluna Confirmadas. Demais abas preservam sua organização e ações. Equipamentos históricos confirmados permanecem acessíveis em seção própria de registros históricos na aba Confirmadas, sem ganhar regras de execução de serviço ou visita.
- Cada serviço ou visita confirmado e não cancelado pertence a exatamente um grupo ou à seção de encerramento. Contadores consideram o conjunto filtrado completo; cartões respeitam a paginação existente. Diferenciar ausência de resultados da página e total do grupo, preservando busca, mês, abas e paginação válida.
- Mostrar execução em Agenda, detalhes, Meus agendamentos e representações existentes no dashboard/gerenciamento, com os mesmos rótulos e uma apresentação compartilhada. Manter o status de aprovação identificável.
- Preservar `sheet-layout`, topbars padronizadas, ações existentes e todos os conteúdos; acrescentar a execução junto ao status, com quebra móvel e sem depender somente de cor.
- No detalhe da visita e no cartão administrativo, oferecer Marcar como realizada somente quando permitido; no detalhe, exibir quem registrou e quando, em `dd/mm/aaaa hh:mm`. Confirmar continua sendo aprovação, inclusive com criação obrigatória de tarefa para serviços; nenhuma ação de execução substitui as permissões existentes de cancelamento.
- Oferecer filtro adicional de execução em Agenda, Meus agendamentos e Gerenciamento: Todos, Aguardando início, Em execução, Concluídos, Atrasados e Aguardando encerramento. Os três filtros de fase correspondem aos grupos da tabela; Atrasados inclui somente serviços não concluídos vencidos, independentemente da fase; Aguardando encerramento inclui somente visitas vencidas sem realização. Esses filtros excluem os registros não aplicáveis; Todos não acrescenta essa restrição. No gerenciamento, combinar com a aba de aprovação, sem trocar silenciosamente sua seleção. Manter busca, mês, categoria quando existente, paginação e Limpar filtros, que também remove o filtro de execução.
- Usar POST com CSRF e versão no fluxo web, com alternativa sem JavaScript e retorno seguro à origem (detalhe ou gerenciamento), mantendo filtros e paginação válida. Atualizar o conteúdo após a ação sem repetir a gravação automaticamente em falhas de conexão.
- Na API, acrescentar informações de execução somente leitura e uma ação administrativa específica de realização de visita. Não liberar a escrita desses metadados por criação/PATCH comum, nem aceitar novos valores em `situacao`.
- As etiquetas temporais são reavaliadas a cada consulta. Não prometer polling, atualização entre abas ou alteração automática de uma página deixada aberta e sem novas consultas.

## Compatibilidade e migração

Apenas visitas precisam de novos campos persistidos e do novo tipo de evento. A migração deixa a realização nula nos registros existentes; não presumir que visitas históricas aconteceram por estarem no passado. Visitas antigas confirmadas e vencidas aparecem como Aguardando encerramento até registro administrativo.

Serviços históricos são classificados pelas tarefas válidas existentes; registros confirmados sem tarefas permanecem Aguardando início, com alerta de atraso quando cabível, sem criar tarefas ou datas fictícias. Preservar IDs, vínculos, arquivos, autoria, versões e eventos. Não alterar Accounts, papéis atuais, equipamentos históricos ou o repositório do monólito.

As mudanças de resposta da API são aditivas. As autorizações de consulta continuam limitando os registros pessoais; a agregação de execução não concede acesso às tarefas vinculadas.

## Alternativas consideradas

1. **Execução derivada para serviços, realização persistida para visitas (proposta):** evita sincronização duplicada e registra a decisão humana onde ela é necessária.
2. **Um único status misturando aprovação, atraso e conclusão:** alteraria contratos/permissões e apagaria a distinção entre agendamento aprovado e executado.
3. **Conclusão automática de visitas ao passar o horário:** simples, mas atestaria uma realização sem comprovação; rejeitada pelo responsável.

## Critérios de aceite e testes da implementação

- Serviço com uma tarefa; várias tarefas; conclusão parcial; ausência de tarefas; exclusão de tarefa; reabertura; nova conclusão; criação ou mudança de vínculo após conclusão; início conservado ao retornar para Demanda.
- Limites antes/exatamente/depois do prazo, conclusão no prazo e posterior, prazo alterado e fuso horário.
- Nenhum alerta de execução em pendentes, recusados e cancelados; equipamento histórico inalterado.
- Visita antes/exatamente/depois do início, realização anterior ao término, encerramento pendente exatamente no término e depois dele, saída do grupo Em execução e ausência de conclusão automática.
- Administrador autorizado; responsável interno, visitante titular, conta inativa e anônimo proibidos de registrar realização, inclusive pela API.
- Versão antiga, duas requisições concorrentes, reenvio, CSRF ausente e falha transacional não duplicam ou deixam gravações parciais.
- Migração conserva registros e deixa visitas antigas sem realização presumida; edição não produz realização anterior ao início.
- Coerência entre propriedades, etiquetas, filtros, contadores, listas e API; agregações sem consultas por cartão; único instante de referência; consulta pessoal sem vazamento de tarefas; URLs com prefixo e usuário nativo do hospedeiro.
- Gerenciamento mantém URL, abas, aprovação/recusa/cancelamento e confirmação com tarefa; grupos e seção de atenção sem perda ou duplicação de registros, inclusive equipamentos históricos; contadores totais corretos com paginação e filtros combinados.
- Fluxos desktop/móvel, teclado, sem JavaScript, atualização após ação, filtros/limpeza, retorno e preservação dos layouts.
- Executar suíte Django completa, testes do hospedeiro nativo e verificações básicas no navegador. A depuração profunda pelo responsável permanece após a entrega.

## Próxima etapa

O responsável aprovou esta especificação escrita. Revisar o plano em `docs/superpowers/plans/2026-10-08-gerenciamento-agendamentos.md` e escolher a execução antes de alterar código ou banco.
