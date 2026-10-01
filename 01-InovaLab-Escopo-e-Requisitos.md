# InovaLab — Escopo e requisitos

Versão 0.1 • 01/10/2026 • Levantamento preliminar para validação.

## 1. Fontes e limites

- **F1:** `InovaLab - Modelagem.pdf`, páginas 1 a 3, lido integralmente, incluindo tabelas e respostas às dúvidas.
- **F2:** solicitação do responsável: sistema semelhante ao Trello, porém mais completo, desenvolvido em Django.
- **Fontes pendentes:** `1.png`, `2.png`, `3.png`, `4.png`, `5.png` e `6.png` não ficaram disponíveis. Nenhum conteúdo dessas imagens foi presumido.

Classificação usada em todos os arquivos: **C = confirmado pela fonte**, **D = derivado da fonte para permitir funcionamento coerente**, **P = proposta a validar**. Uma regra D ou P não representa aprovação do responsável. Prioridades são propostas: **MVP**, **seguinte** e **condicional**.

As respostas da página 3 prevalecem sobre a lista inicial: não haverá status `re-criar`; a tarefa recusada retorna a `criacao`. A unificação dos agendamentos também está confirmada. O termo “Agendamento Figma” identifica uma proposta de modelagem no PDF, não uma integração confirmada com a ferramenta Figma.

## 2. Objetivo e escopo

Centralizar as demandas do InovaLab, sua execução por responsáveis, a agenda de serviços e recursos, o cadastro de materiais e a administração de banners. A experiência tipo Trello sugere um quadro Kanban; quadros múltiplos, equipes, comentários e anexos ainda não estão confirmados.

Módulos identificados: tarefas; serviços; equipamentos; espaços; agendamentos e integração AgroHub; materiais; banners; identidade e autorização.

Não são requisitos confirmados: cobrança, pagamentos, projetos hierárquicos, múltiplas organizações, chat, aplicativo nativo, IA, automações configuráveis, sincronização em tempo real e integração com Trello/Figma.

## 3. Atores e permissões

| Ator | Responsabilidades e acesso | Base |
| --- | --- | --- |
| Administrador | Ver todas as tarefas; criar, editar e excluir tarefas de qualquer responsável; criar, editar e excluir agendamentos pela interface | C — F1 p. 2–3 |
| Usuário interno | Ver somente suas tarefas e alterar somente o status delas | C — F1 p. 3 |
| Solicitante AgroHub | Solicitar agendamento pelo sistema externo; não é automaticamente usuário interno | C — F1 p. 2; distinção D |
| Sistema AgroHub | Enviar a solicitação pela API como ator de suporte | C — F1 p. 2 |
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
| RF06 | Trabalhar com demanda, criação, avaliação e concluído, retornando recusadas para criação | C — F1 p. 2–3 | MVP | `re-criar` não é uma opção; recusa resulta em `criacao`; autoridade de avaliação depende de Q03 |
| RF07 | Exibir tarefas em quadro Kanban e permitir movimentação conforme permissão | P — F2 | MVP | Colunas refletem status; movimentação negada não modifica o cartão persistido |
| RF08 | Consultar e manter equipamentos com nome, descrição e status | Campos C; manutenção P — F1 p. 1 | MVP | Aceita disponível, ocupado e indisponível; alteração de disponibilidade respeita decisão Q06 |
| RF09 | Consultar e manter espaços com nome, capacidade máxima e status | Campos C; manutenção P — F1 p. 1 | MVP | Capacidade é positiva; status segue disponível, ocupado e indisponível |
| RF10 | Consultar e manter serviços com nome, descrição e status | Campos C; manutenção P — F1 p. 1 | MVP | Serviço aceita disponível ou indisponível |
| RF11 | Disponibilizar os serviços pré-cadastrados do PDF | C — F1 p. 1–2 | MVP | Os 11 nomes da seção 6 existem, sem duplicação ao repetir a carga |
| RF12 | Unificar agenda e formulário, com seleção por serviço, equipamento ou espaço | C — F1 p. 3 | MVP | Cada categoria lista apenas seus objetos; todas aparecem na agenda comum |
| RF13 | Permitir ao administrador criar, editar e excluir agendamentos | C — F1 p. 2 | MVP | Operações persistem e refletem na agenda; tratamento de histórico depende de Q08 |
| RF14 | Receber agendamentos do AgroHub pela API | C — F1 p. 2 | MVP | Solicitação válida cria um registro na agenda unificada e devolve seu identificador |
| RF15 | Registrar categoria, objeto, motivo, data, início, fim e requerente no agendamento unificado | C/D — união dos modelos F1 p. 2 | MVP | Categoria e alvo correspondem; requerente é preservado sem exigir conta local |
| RF16 | Impedir sobreposição para recursos de uso exclusivo | P — lacuna da agenda | MVP | Dois pedidos concorrentes para o mesmo recurso e intervalo não geram duas reservas; exclusividade de serviço depende de Q05 |
| RF17 | Consultar e manter materiais com nome, categoria, quantidade, status e fonte | Campos C; manutenção P — F1 p. 2 | MVP | Dados persistem; unidade e vocabulários dependem de Q09 |
| RF18 | Consultar e manter banners com título, imagem WebP, status e local | Campos C; manutenção P — F1 p. 3 | MVP | Status ativo/inativo/agendado e local home/sobre são preservados |
| RF19 | Publicar banners conforme local e período de exibição | D/P — F1 p. 3 | Condicional | Inativo não aparece; agendado aparece apenas no período definido em Q10 |
| RF20 | Filtrar tarefas por status, serviço, responsável e prazo | P | Seguinte | Filtros nunca ampliam as permissões de RF02 |
| RF21 | Registrar histórico de alterações relevantes | P | MVP | Operação registra ator, instante e mudança; histórico só é acessível a autorizados |
| RF22 | Tratar reenvios de agendamento externo sem duplicação | P — integração RF14 | MVP | Mesma origem e chave, com o mesmo conteúdo, retornam o registro anterior; conteúdo diferente gera conflito |

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

Nomes e descrições transcritos de F1 p. 1–2. Células vazias permanecem sem definição.

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
| RN04 | Agendamento pertence a uma das três categorias e referencia exatamente um alvo compatível | C/D |
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

## 8. Questões em aberto

| ID | Decisão necessária | Impacto |
| --- | --- | --- |
| Q01 | Reenviar as seis imagens e identificar se são telas, requisitos ou fluxos | Cobertura completa das fontes |
| Q02 | Haverá vários quadros, projetos, equipes ou apenas um quadro do laboratório? | Escopo e relacionamento das tarefas |
| Q03 | Quem avalia, aprova, recusa e reabre? Usuário pode concluir a própria tarefa? Quais transições são livres? | Permissões e fluxo; o PDF não reserva aprovação ao admin |
| Q04 | Quais campos são obrigatórios? Início é previsto ou real? Prazo contém horário? | Validações e datas das tarefas |
| Q05 | Serviços podem atender simultaneamente? Agendamento exige equipamento, espaço e operador associados? | Modelo de capacidade e conflitos |
| Q06 | Status ocupado é manual ou calculado? Indisponibilidade pode ter período? | Consistência da agenda |
| Q07 | Quem hospeda a API? Qual contrato, autenticação e ID do requerente o AgroHub oferece? Edição/exclusão deve voltar ao AgroHub? | Integração e fonte oficial dos dados |
| Q08 | Excluir significa apagar ou cancelar/arquivar? Agendamento exige aprovação? | Auditoria e ciclo da reserva |
| Q09 | Quais categorias, status, unidades e significado de “fonte” dos materiais? Haverá entradas, saídas e consumo por tarefa? | Cadastro simples versus estoque |
| Q10 | Quais datas controlam banner agendado? Haverá ordem e vários banners por local? | Publicação automática |
| Q11 | Administrador gerencia contas? Haverá recuperação de senha ou login institucional? | Identidade e acesso |
| Q12 | Quem administra serviços, espaços, equipamentos, materiais e banners? | Permissões ainda não documentadas |
| Q13 | Qual horário de funcionamento, antecedência, duração mínima/máxima e política de feriados? | Validação de reservas |
| Q14 | Quantas pessoas usarão a reserva? É necessário verificar a capacidade do espaço? | Campo ausente para aplicar capacidade |

## 9. Evolução sugerida, fora do escopo confirmado

Após validar o núcleo: comentários e anexos em tarefas, checklist, prioridade, notificações, indicadores de atraso, histórico de estoque e associação entre demanda e reserva. Cada recurso precisa de requisitos e permissões próprios; “mais completo que Trello” não autoriza assumir todos eles como obrigatórios.
