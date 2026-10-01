# InovaLab — Escopo e requisitos

Versão 0.3 • 01/10/2026 • PDF original conferido; decisões do responsável identificadas por fonte.

## 1. Fontes e limites

- **F1:** `Referencias/InovaLab - Modelagem.pdf`, três páginas, lidas integralmente e conferidas visualmente em 01/10/2026, incluindo tabela de serviços e respostas às dúvidas. A comparação com os requisitos está no arquivo 06.
- **F2:** solicitação anterior do responsável: sistema semelhante ao Trello, porém mais completo, desenvolvido em Django.
- **F3:** solicitação do responsável em 01/10/2026: revisar a documentação, projetar a arquitetura e desenvolver frontend básico e endpoints de API para futuras integrações. Na mesma conversa, definiu que somente administradores aprovam, recusam e reabrem tarefas; o responsável executa e envia para avaliação. Também definiu um único serviço, equipamento ou espaço como alvo de cada reserva no MVP.
- **F4:** seis telas examinadas em `Referencias/`: `ADM - Agendamentos.png`, `ADM - Dashboard.png`, `ADM - Estoque.png`, `ADM - Tarefas.png`, `Banners.png` e `Usuarios.png`. Não foi estabelecida correspondência com os antigos nomes `1.png` a `6.png`.

Classificação usada em todos os arquivos: **C = confirmado pela fonte**, **D = derivado da fonte para permitir funcionamento coerente**, **P = proposta a validar**. Uma regra D ou P não representa aprovação do responsável. Uma observação C de uma tela confirma o elemento visual, sem aprovar automaticamente suas regras de negócio. Prioridades são propostas: **MVP**, **seguinte** e **condicional**.

As respostas da página 3 prevalecem sobre a lista inicial: não haverá status `re-criar`; a tarefa recusada retorna a `criacao`. A unificação dos agendamentos também está confirmada. O termo “Agendamento Figma” identifica uma proposta de modelagem no PDF, não uma integração confirmada com a ferramenta Figma.

## 2. Objetivo e escopo

Centralizar as demandas do InovaLab, sua execução por responsáveis, a agenda de serviços e recursos, o cadastro de materiais e a administração de banners. F4 apresenta um quadro Kanban com demanda, criação, avaliação e concluído. Quadros múltiplos, equipes, comentários e anexos ainda não estão confirmados.

F3 confirma frontend básico e endpoints de API para integração futura. A interface e a API devem compartilhar regras de negócio e autorização. A abrangência de cada endpoint, autenticação externa e tecnologia do frontend serão detalhadas por etapa; a proposta está no arquivo 05.

Módulos identificados: tarefas; serviços; equipamentos; espaços; agendamentos e integração AgroHub; materiais; banners; identidade e autorização.

Não são requisitos confirmados: cobrança, pagamentos, projetos hierárquicos, múltiplas organizações, chat, aplicativo nativo, IA, automações configuráveis, sincronização em tempo real e integração com Trello/Figma.

## 3. Atores e permissões

| Ator | Responsabilidades e acesso | Base |
| --- | --- | --- |
| Administrador | Ver e administrar todas as tarefas; aprovar, recusar e reabrir tarefas; administrar agendamentos pela interface | C — F1 p. 2–3; decisão F3 |
| Usuário interno | Ver somente suas tarefas; executar e enviar para avaliação, alterando somente status; campos automáticos são definidos pelo servidor conforme política aprovada | Acesso C — F1 p. 3/F3; campos automáticos P |
| Solicitante AgroHub | Solicitar agendamento pelo sistema externo; não é automaticamente usuário interno | C — F1 p. 2; distinção D |
| Sistema AgroHub | Participar da integração de agendamento por API; envio ao InovaLab é o fluxo proposto | Integração C — F1 p. 2; direção D/P, Q07 |
| Visitante do site | Visualizar banners publicados em home/sobre | D — F1 p. 3 |

Gestão dos cadastros, materiais, banners e contas pelo administrador é proposta. O PDF não define esses responsáveis. Não conceder acesso global ao usuário interno por analogia com o Trello.

## 4. Requisitos funcionais

Os critérios abaixo são a especificação operacional proposta; onde o comportamento não aparece expressamente no PDF, prevalece a classificação D/P.

| ID | Requisito | Origem | Prioridade | Critério de aceite |
| --- | --- | --- | --- | --- |
| RF01 | Autenticar usuários internos e identificar seu perfil | D — permissões F1 p. 3 | MVP | Uma sessão identifica um usuário e suas permissões; sessão encerrada não acessa dados privados |
| RF02 | Restringir consulta de tarefas por responsável | C — F1 p. 3 | MVP | Admin vê todas; usuário não recebe tarefas alheias em listas, detalhes ou buscas |
| RF03 | Permitir ao administrador criar, editar e excluir tarefas de qualquer responsável | C — F1 p. 3 | MVP | Alterações válidas persistem; usuário interno não executa essas operações |
| RF04 | Registrar serviço, descrição, responsável, status, início, prazo e conclusão da tarefa | C — F1 p. 2 | MVP | Dados salvos reaparecem na consulta; obrigatoriedade de cada data depende de Q04 |
| RF05 | Permitir ao usuário alterar somente o status de suas próprias tarefas | C — F1 p. 3 | MVP | Tentativas de alterar responsável, descrição ou tarefa alheia são rejeitadas |
| RF06 | Trabalhar com demanda, criação, avaliação e concluído, retornando recusadas para criação | C — F1 p. 2–3; F3 | MVP | `re-criar` não é uma opção; somente admin aprova, recusa e reabre; recusa resulta em `criacao`; destino da reabertura ainda proposto |
| RF07 | Exibir tarefas em quadro Kanban e permitir movimentação conforme permissão | Quadro C — F4; movimentação D/P | MVP | Colunas refletem status; movimentação negada não modifica o cartão persistido; há alternativa por botão/seletor |
| RF08 | Consultar e manter equipamentos com nome, descrição e status | Campos C; manutenção P — F1 p. 1 | MVP | Aceita disponível, ocupado e indisponível; alteração de disponibilidade respeita decisão Q06 |
| RF09 | Consultar e manter espaços com nome, capacidade máxima e status | Campos C; manutenção e capacidade positiva P — F1 p. 1 | MVP | Capacidade é positiva pela proposta; status segue disponível, ocupado e indisponível |
| RF10 | Consultar e manter serviços com nome, descrição e status | Campos C; manutenção P — F1 p. 1 | MVP | Serviço aceita disponível ou indisponível |
| RF11 | Disponibilizar os serviços pré-cadastrados do PDF | C — F1 p. 1–2 | MVP | Os 11 nomes da seção 6 existem, sem duplicação ao repetir a carga |
| RF12 | Unificar agenda e formulário, com seleção por serviço, equipamento ou espaço | C — F1 p. 3 | MVP | Cada categoria lista apenas seus objetos; todas aparecem na agenda comum |
| RF13 | Permitir ao administrador criar, editar e excluir agendamentos | C — F1 p. 2 | MVP | Operações persistem e refletem na agenda; tratamento de histórico depende de Q08 |
| RF14 | Viabilizar agendamento via API para o usuário do AgroHub; propor recebimento no InovaLab | Integração C — F1 p. 2; direção/contrato D/P, Q07 | MVP | No fluxo proposto, solicitação válida cria um registro na agenda unificada e devolve seu identificador |
| RF15 | Registrar categoria, objeto, motivo, data, início, fim e requerente no agendamento unificado | Campos C; união D — F1 p. 2–3 | MVP | Preserva a informação dos modelos originais, inclusive `data_hora` na representação unificada; categoria e alvo correspondem; requerente sem conta local é derivação a detalhar |
| RF16 | Impedir sobreposição para recursos de uso exclusivo | P — lacuna da agenda | MVP | Dois pedidos concorrentes para o mesmo recurso e intervalo não geram duas reservas; exclusividade de serviço depende de Q05 |
| RF17 | Consultar e manter materiais com nome, categoria, quantidade, status e fonte | Campos C; manutenção P — F1 p. 2 | MVP | Dados persistem; unidade e vocabulários dependem de Q09 |
| RF18 | Consultar e manter banners com título, imagem WebP, status e local | Campos C; manutenção P — F1 p. 3 | MVP | Status ativo/inativo/agendado e local home/sobre são preservados |
| RF19 | Publicar banners conforme local e período de exibição | D/P — F1 p. 3 | Condicional | Inativo não aparece; agendado aparece apenas no período definido em Q10 |
| RF20 | Filtrar tarefas por status, serviço, responsável e prazo | P | Seguinte | Filtros nunca ampliam as permissões de RF02 |
| RF21 | Registrar histórico de alterações relevantes | P | MVP | Operação registra ator, instante e mudança; histórico só é acessível a autorizados |
| RF22 | Tratar reenvios de agendamento externo sem duplicação | P — integração RF14 | MVP | Mesma origem e chave, com o mesmo conteúdo, retornam o registro anterior; conteúdo diferente gera conflito |
| RF23 | Expor operações por API para integração com outros sistemas | Objetivo C — F3; contrato P | MVP por etapa | Cada módulo entregue possui os endpoints acordados, documentação de contrato e as mesmas permissões e validações da interface |
| RF24 | Oferecer frontend básico para as operações internas | C — F3; telas F4 como referência | MVP por etapa | Usuário realiza o fluxo entregue pelo navegador; interface mostra erros e respeita o acesso definido no servidor |

O PDF apresenta dois modelos de agendamento na página 2: “Agendamento Figma” (`servico`, `data_hora`, `requerente`) e “Agendamento AgroHub já existente” (`categoria`, `objeto_agendadado`, `motivo`, `data`, `horario_inicio`, `horario_fim`). A página 3 confirma sua unificação. Representar `data_hora` por início completo ou por data/horário é derivação técnica; a fonte não define a conversão nem fornece horário final no primeiro modelo. Não inventar duração para registros antigos; esclarecer essa eventual migração em Q07.

## 5. Requisitos não funcionais

Exceto RNF01, todos são propostas a validar. Metas numéricas não constam no PDF.

| ID | Requisito | Verificação proposta |
| --- | --- | --- |
| RNF01 | Desenvolver o sistema em Django — C, F2 | Backend implementado em Django; versão escolhida na implementação |
| RNF02 | Aplicar autorização no servidor em todas as entradas | Testes de consulta direta e alteração por ID alheio não expõem nem modificam dados |
| RNF03 | Proteger credenciais, sessões e integração | Senhas não armazenadas em texto puro; operações de navegador protegidas contra CSRF; API rejeita credencial inválida; produção usa HTTPS |
| RNF04 | Preservar integridade em concorrência | Duas reservas simultâneas conflitantes produzem no máximo um sucesso para recurso exclusivo |
| RNF05 | Registrar falhas operacionais sem expor segredos | Erros têm identificador de correlação; logs omitem credenciais e conteúdo pessoal desnecessário |
| RNF06 | Permitir uso em celular e por teclado | Agenda e tarefas funcionam em largura de 360 px; mudança de status possui alternativa ao arrastar |
| RNF07 | Responder consultas comuns em até 2 s no percentil 95 | Meta inicial: 50 sessões simultâneas e 10 mil tarefas; medir ambiente e volume acordados, excluindo rede do usuário |
| RNF08 | Manter recuperação de dados | Meta inicial: RPO de 24 h e RTO de 4 h; executar restauração de banco e arquivos em ambiente de teste |
| RNF09 | Manter contrato versionado da integração | Documentar autenticação, campos, erros, fuso horário e comportamento de reenvio |
| RNF10 | Limitar exposição e retenção de dados pessoais | Definir quais dados de requerente são necessários, quem acessa e quando remover; política ainda pendente |

## 6. Serviços iniciais

Nomes e descrições transcritos e conferidos diretamente em F1 p. 1–2. São onze serviços nomeados; linhas inteiramente vazias da tabela não representam serviços adicionais. Descrições vazias permanecem sem definição.

| Serviço | Descrição na fonte |
| --- | --- |
| Identidade Visual | Não informada |
| Impressão Sublimática | Não informada |
| Criação de Banners | Não informada |
| Impressão 3D | Modelagem e Impressão 3D. |
| Corte a laser | Cortes e gravações em diversos materiais. |
| Plotter de recorte | Recorte de vinil adesivo e outros materiais. |
| Óculos de realidade virtual | Dispositivos para experiências imersivas. |
| Scanner 3D manual | Digitalização de objetos para 3D. |
| Plotter de Impressão | Imprima em alta qualidade. |
| Consultoria técnica | Suporte e orientação para o desenvolvimento do projeto. |
| Uso do espaço | Uso do espaço para aula, demonstração e outros. |

O PDF lista “Óculos de realidade virtual” e “Scanner 3D manual” como serviços. Não reclassificá-los silenciosamente como equipamentos. O serviço “Criação de Banners” é uma oferta do laboratório; a entidade Banner administra imagens do site e tem finalidade distinta.

## 7. Regras de negócio

| ID | Regra | Classificação |
| --- | --- | --- |
| RN01 | Administrador consulta e administra todas as tarefas | C |
| RN02 | Usuário consulta somente tarefas cujo responsável é ele e altera somente seu status | C |
| RN03 | Não existe etapa “recriar”; recusa na avaliação retorna à criação | C |
| RN04 | No MVP, cada agendamento referencia exatamente um serviço, equipamento ou espaço, compatível com a categoria | C — F1/F3; integridade D |
| RN05 | Serviço possui status disponível/indisponível; espaço e equipamento também admitem ocupado | C |
| RN06 | Horário final deve ser posterior ao inicial | D |
| RN07 | Intervalos são tratados como [início, fim); reservas adjacentes são permitidas | P |
| RN08 | Recurso indisponível não aceita nova reserva; reservas existentes exigem tratamento explícito | P |
| RN09 | Estado “ocupado agora” não basta para determinar disponibilidade futura | D |
| RN10 | Quantidade de material não pode ser negativa; unidade e precisão devem ser definidas | P |
| RN11 | Ao concluir uma tarefa, o sistema registra a conclusão; ao reabrir, preserva o evento no histórico | P |
| RN12 | Remoção de cadastros referenciados não pode deixar tarefas ou reservas sem referência | D |
| RN13 | A API e a interface aplicam as mesmas validações de agenda | D |
| RN14 | Banner usa imagem WebP e local home/sobre | C |
| RN15 | Criação de agendamento não cria tarefa automaticamente sem uma regra aprovada | P — postura provisória |
| RN16 | Somente administradores aprovam, recusam e reabrem tarefas; o responsável executa e envia para avaliação | C — decisão F3 |

## 8. Questões em aberto

| ID | Decisão necessária | Impacto |
| --- | --- | --- |
| Q01 | PDF original conferido e seis telas locais incorporadas como F4; apenas a correspondência com os antigos nomes numerados não foi estabelecida | Fontes locais disponíveis revisadas; o PDF não menciona imagens numeradas |
| Q02 | Haverá vários quadros, projetos, equipes ou apenas um quadro do laboratório? | Escopo e relacionamento das tarefas |
| Q03 | Decidido em F3: somente administradores aprovam, recusam e reabrem; responsável executa e envia para avaliação. Confirmar destino da reabertura e eventuais retornos durante execução | Autoridade definida; mapa restante no arquivo 03 é proposta |
| Q04 | Quais campos são obrigatórios? Início é previsto ou real? Prazo contém horário? | Validações e datas das tarefas |
| Q05 | Decidido em F3: no MVP cada reserva tem um único serviço, equipamento ou espaço, sem bloqueio automático de outros alvos. Falta definir atendimento simultâneo/exclusividade por serviço | Modelo inicial definido; política de conflito de serviços ainda pendente |
| Q06 | Status ocupado é manual ou calculado? Indisponibilidade pode ter período? | Consistência da agenda |
| Q07 | Quem hospeda a API? Qual contrato, autenticação e ID do requerente o AgroHub oferece? Edição/exclusão deve voltar ao AgroHub? Haverá migração de agendamentos existentes e como tratar `data_hora` sem fim no modelo Figma? | Direção da integração, fonte oficial dos dados e eventual migração |
| Q08 | Excluir significa apagar ou cancelar/arquivar? Agendamento exige aprovação? | Auditoria e ciclo da reserva |
| Q09 | Quais categorias, status, unidades e significado de “fonte” dos materiais? Haverá entradas, saídas e consumo por tarefa? | Cadastro simples versus estoque |
| Q10 | Quais datas controlam banner agendado? Haverá ordem e vários banners por local? | Publicação automática |
| Q11 | Administrador gerencia contas? Haverá recuperação de senha ou login institucional? | Identidade e acesso |
| Q12 | Quem administra serviços, espaços, equipamentos, materiais e banners? | Permissões ainda não documentadas |
| Q13 | Qual horário de funcionamento, antecedência, duração mínima/máxima e política de feriados? | Validação de reservas |
| Q14 | Quantas pessoas usarão a reserva? É necessário verificar a capacidade do espaço? | Campo ausente para aplicar capacidade |
| Q15 | “Eventos/Reuniões”, recessos/feriados e gestão de “usuários do AgroHub” nas telas ampliam o escopo? A ordem de banners precisa ser editável? | Divergências e elementos visuais adicionais registrados no arquivo 05 |

## 9. Decisões registradas

| Data | Fonte | Decisão | Consequência |
| --- | --- | --- | --- |
| 01/10/2026 | F3 — solicitação | Frontend básico e API para futuras integrações | RF23/RF24; revisar a orientação anterior de restringir API ao AgroHub |
| 01/10/2026 | F3 — resposta a Q03 | Somente administradores aprovam, recusam e reabrem | RN16; UC04/UC05 e cenários de transição devem testar essa autorização |
| 01/10/2026 | F3 — resposta a Q05 | Cada reserva seleciona um único serviço, equipamento ou espaço no MVP | RN04; três referências opcionais e exatamente uma preenchida; sem alocações compostas no MVP |

## 10. Evolução sugerida, fora do escopo confirmado

Após validar o núcleo: comentários e anexos em tarefas, checklist, prioridade, notificações, indicadores de atraso, histórico de estoque e associação entre demanda e reserva. Cada recurso precisa de requisitos e permissões próprios; “mais completo que Trello” não autoriza assumir todos eles como obrigatórios.
