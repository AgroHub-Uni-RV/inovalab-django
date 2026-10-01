# InovaLab — Conferência dos requisitos com o PDF

01/10/2026 • Fonte: `Referencias/InovaLab - Modelagem.pdf`, três páginas. Conferência por extração de texto e leitura visual de todas as páginas, inclusive a tabela de serviços. Esta análise verifica a documentação; não certifica uma implementação.

## 1. Resultado

O núcleo do levantamento está de acordo com o PDF. Todos os campos e objetivos explícitos estão representados nos requisitos. Os onze serviços e suas descrições correspondem à tabela original. As respostas da página 3 foram corretamente usadas para eliminar `re-criar`, unificar os agendamentos e definir o acesso às tarefas.

Não foi encontrado requisito explícito do PDF sem cobertura. Foram corrigidas a ausência de referência explícita a `data_hora` do modelo Figma, a classificação da direção da API e a informação desatualizada de que o PDF não estava disponível. A regra de capacidade positiva foi identificada como proposta, pois o PDF somente nomeia o campo de capacidade.

## 2. Comparação por página

| Página e item | Conteúdo confirmado no PDF | Cobertura documental | Resultado |
| --- | --- | --- | --- |
| 1 — Equipamento | Nome, descrição; disponível/ocupado/indisponível | RF08, RN05; UC06; modelo no arquivo 04 | Conforme; gestão e responsáveis não definidos no PDF |
| 1 — Espaço | Nome, capacidade máxima; disponível/ocupado/indisponível | RF09, RN05; UC06; arquivo 04 | Conforme; capacidade positiva e participantes são complementos propostos |
| 1 — Serviço | Nome, descrição; disponível/indisponível | RF10, RN05; UC06; arquivo 04 | Conforme |
| 1–2 — Serviços iniciais | Onze serviços nomeados e oito descrições preenchidas | RF11; seção 6 do arquivo 01; CT24 | Nomes e descrições conferidos; três descrições e linhas inteiramente vazias permanecem sem conteúdo |
| 2 — Tarefa | Serviço, descrição, responsável User, status, início, prazo e conclusão | RF04/RF06; UC03–UC05; arquivo 04 | Campos cobertos; valores finais de status seguem a resposta da página 3 |
| 2 — Agendamento Figma | Serviço, `data_hora` e requerente | RF15; nota explicativa no arquivo 01; arquivo 04 | Referência explícita a `data_hora` acrescentada; normalização é derivação |
| 2 — Agendamento AgroHub | Categoria serviço/equipamento/espaço, `objeto_agendadado`, motivo, data, início e fim | RF12/RF15; UC08–UC09; arquivo 04 | Conforme; grafia original registrada, sem obrigar sua reprodução na API nova |
| 2 — Operações de agenda | Usuário externo AgroHub agenda via API; admin cria, edita e exclui via sistema | RF13/RF14; UC08–UC09 | Conforme; o PDF não fornece endpoints, autenticação ou direção inequívoca da chamada entre servidores |
| 2 — Materiais | Nome, categoria, quantidade, status e fonte | RF17; UC10; arquivo 04 | Conforme; unidade, vocabulários e movimentações não especificados |
| 3 — Banner | Título, imagem WebP, ativo/inativo/agendado, home/sobre | RF18; RN14; UC11–UC12; arquivo 04 | Conforme; período, ordenação e publicação automática são complementos |
| 3 — Unificação da agenda | Uma interface, mesmo formulário, separação por categoria | RF12; UC07–UC09 | Conforme; um alvo por reserva foi depois confirmado pelo responsável em F3 |
| 3 — Recusa de tarefa | Retornar para criação sem outra categoria | RF06, RN03; UC05; CT04 | Conforme; `re-criar` da lista inicial não deve ser implementado |
| 3 — Acesso às tarefas | Admin vê todas, cria/edita/exclui; usuário vê próprias e só altera status | RF02/RF03/RF05; RN01/RN02; CT05–CT07 | Conforme; aprovação/recusa/reabertura exclusivas de admin vêm de F3 |

## 3. Requisitos que complementam o PDF

| Requisitos | Fonte ou classificação correta |
| --- | --- |
| RF01 — autenticação | Derivação necessária das permissões; PDF não define login ou provisionamento |
| RF07 — Kanban | Referência visual F4 e intenção F2; PDF define estados, sem especificar o quadro ou arrastar |
| RF16 — não sobreposição | Proposta de integridade; PDF não define exclusividade, capacidade paralela ou conflitos |
| RF19 — publicação por período | Derivação/proposta do status agendado; datas de exibição não constam no PDF |
| RF20 — filtros completos | Proposta; alguns controles aparecem em F4, sem definir todas as combinações |
| RF21 — histórico | Proposta; PDF não exige eventos de auditoria |
| RF22 — idempotência | Proposta para integração confiável; não especificada no PDF |
| RF23/RF24 — API geral e frontend básico | Solicitação posterior F3, além da integração AgroHub presente no PDF |
| RNF01 — Django | Solicitação F2/F3; o PDF não determina framework |
| RNF02–RNF10 | Propostas técnicas de segurança, concorrência, acessibilidade, desempenho, recuperação e contrato; metas não constam no PDF |

Nos requisitos de cadastro RF08–RF10, RF17 e RF18, os campos são confirmados pelo PDF; responsáveis e manutenção são propostas, reforçadas em parte pelas telas. A presença de uma tabela de entidade não define automaticamente todas as operações e permissões de CRUD.

## 4. Decisões posteriores preservadas

- Somente administradores aprovam, recusam e reabrem tarefas; o responsável executa e envia para avaliação. O PDF permite mudança de status pelo responsável, mas não define quais transições. A decisão F3 detalha essa lacuna, sem contrariar uma autoridade de avaliação explicitamente definida na fonte.
- Uma reserva do MVP tem exatamente um serviço, equipamento ou espaço, sem bloquear recursos associados. Isso detalha a categoria/alvo da agenda unificada. Atendimento simultâneo por serviço ainda precisa de definição.
- Frontend básico e API para futuras integrações permanecem no escopo por solicitação F3, mesmo sem descrição de uma API geral no PDF.

## 5. Lacunas reais que permanecem

Continuam em aberto as obrigatoriedades e semântica das datas de tarefa; destino da reabertura; exclusividade e disponibilidade temporal dos recursos; direção, credencial e contrato AgroHub; exclusão física versus cancelamento; vocabulários/unidades dos materiais; datas de banners agendados; provisionamento de contas e gestão dos cadastros.

O PDF apresenta o agendamento AgroHub como já existente. Isso não demonstra que seus dados devam ser migrados ou que o InovaLab deva substituir seu armazenamento. Caso haja migração, o modelo Figma não contém fim ou duração; não preencher esse dado por suposição. Essa questão foi incorporada a Q07.

Calendário de eventos/reuniões, recessos/feriados, terceiros/devoluções, ordenação de banners e gestão de usuários do AgroHub são elementos das telas F4, não exigências explícitas desse PDF. Permanecem separados como decisões pendentes Q09–Q15.
