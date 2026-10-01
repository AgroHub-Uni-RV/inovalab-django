# InovaLab — Casos de uso

Versão 0.1 • 01/10/2026. Ler as classificações e questões de `01-InovaLab-Escopo-e-Requisitos.md`. Base: PDF p. 1–3 e solicitação do usuário; as seis imagens estão pendentes.

Todos os casos têm escopo no sistema InovaLab e nível de objetivo do usuário, exceto UC09, que representa integração. Fluxos detalhados são uma elaboração derivada/proposta, mesmo quando o objetivo é confirmado. Não há implementação entregue.

## UC01 — Acessar o sistema

- **Base:** D; RF01. **Ator:** usuário interno ou administrador.
- **Interesse:** acessar apenas funções e dados autorizados.
- **Pré-condição:** conta existente e habilitada; provisionamento depende de Q11.
- **Fluxo principal:** 1. Ator informa credenciais. 2. Sistema valida identidade e acesso. 3. Inicia sessão. 4. Exibe a área permitida para o perfil.
- **Alternativas:** credenciais inválidas não criam sessão; conta bloqueada tem acesso negado; sessão expirada exige nova autenticação.
- **Pós-condição:** sessão autenticada com identidade e permissões associadas.

## UC02 — Consultar tarefas

- **Base:** C para visibilidade; P para Kanban/filtros. RF02, RF07, RF20.
- **Ator:** usuário interno ou administrador.
- **Interesse:** acompanhar o trabalho sem exposição de tarefas alheias.
- **Pré-condição:** sessão autenticada.
- **Fluxo principal:** 1. Ator abre tarefas. 2. Sistema aplica o escopo de acesso. 3. Agrupa por status. 4. Ator seleciona um cartão. 5. Sistema apresenta os dados autorizados.
- **Alternativas:** nenhum resultado exibe estado vazio; acesso direto a ID alheio é negado sem revelar dados; filtros são aplicados depois do escopo de permissão.
- **Pós-condição:** tarefas exibidas sem alteração dos registros.

## UC03 — Administrar tarefas

- **Base:** C; RF03, RF04. **Ator:** administrador. **Interessados:** responsável e gestor.
- **Pré-condições:** administrador autenticado; serviço e responsável válidos disponíveis.
- **Fluxo principal:** 1. Admin solicita nova tarefa. 2. Informa serviço, descrição, responsável e datas aplicáveis. 3. Sistema valida referências e campos. 4. Salva a tarefa; status inicial `demanda` é proposta. 5. Tarefa passa a aparecer para o responsável e administradores.
- **Alternativas:** edição atualiza campos válidos; reatribuição retira o acesso do responsável anterior; exclusão solicita confirmação e segue Q08; erro de validação preserva os dados digitados; usuário comum recebe acesso negado.
- **Pós-condição:** criação, edição ou exclusão persistida sem referências inválidas; histórico proposto em RF21.

## UC04 — Atualizar status da tarefa

- **Base:** C para alteração pelo responsável; P para mapa de transições. RF05, RF06.
- **Ator:** responsável pela tarefa; administrador também pode editar via UC03.
- **Pré-condições:** sessão válida, tarefa acessível e transição autorizada pela política aprovada em Q03.
- **Fluxo principal:** 1. Ator seleciona a tarefa. 2. Escolhe o próximo status. 3. Sistema revalida responsável e transição. 4. Atualiza somente o status e campos automáticos previstos. 5. Reposiciona o cartão.
- **Alternativas:** tarefa alheia ou tentativa de editar outros campos é rejeitada; transição não autorizada mantém o estado anterior; edição concorrente exige atualização da tela antes de nova tentativa, conforme proposta técnica.
- **Pós-condição:** status atualizado de forma consistente; registro automático de datas depende de Q04/RN11.

## UC05 — Avaliar uma tarefa

- **Base:** C para retorno à criação; P para ator e demais passos. RF06, RF21.
- **Ator proposto:** administrador avaliador. Essa exclusividade ainda não foi aprovada.
- **Interesse:** aceitar a entrega ou solicitar correção.
- **Pré-condições:** tarefa em avaliação e ator autorizado por Q03.
- **Fluxo principal:** 1. Ator consulta a tarefa em avaliação. 2. Verifica a entrega pelos meios definidos pelo laboratório. 3. Aprova. 4. Sistema altera para concluído e registra conclusão, conforme RN11.
- **Alternativas:** recusa retorna à criação, sem status `re-criar`; motivo da recusa é campo proposto; estado já alterado por outro ator exige nova leitura; reabertura depende de Q03.
- **Pós-condição:** tarefa concluída ou devolvida para criação. Anexar uma entrega dentro do sistema não é pré-requisito confirmado.

## UC06 — Administrar serviços, equipamentos e espaços

- **Base:** C para dados; P para manutenção pelo admin. RF08–RF11.
- **Ator proposto:** administrador. **Interesse:** catálogo correto para tarefas e agenda.
- **Pré-condição:** permissão de cadastro, a validar em Q12.
- **Fluxo principal:** 1. Seleciona o tipo de cadastro. 2. Informa os campos específicos. 3. Sistema valida capacidade e status aplicáveis. 4. Salva e disponibiliza para consultas autorizadas.
- **Alternativas:** edita cadastro existente; marca indisponibilidade; tentativa de exclusão com vínculos é bloqueada ou substituída por desativação conforme política; indisponibilizar não cancela silenciosamente reservas existentes.
- **Pós-condição:** catálogo atualizado e vínculos preservados. Serviços iniciais carregados conforme RF11.

## UC07 — Consultar agenda unificada

- **Base:** C para unificação; D para consulta. RF12, RF15.
- **Ator:** administrador. Consulta por outros perfis ainda depende de validação.
- **Pré-condição:** permissão para acessar agenda.
- **Fluxo principal:** 1. Ator escolhe período e categoria. 2. Sistema consulta reservas do intervalo. 3. Exibe objeto, horário, motivo e requerente conforme autorização. 4. Ator abre um registro.
- **Alternativas:** período sem reservas exibe agenda vazia; categoria sem objetos informa ausência de cadastro; consulta não implica autorização de edição.
- **Pós-condição:** agenda consultada sem alteração.

## UC08 — Administrar agendamentos

- **Base:** C para CRUD e formulário único; P para política de conflito. RF12, RF13, RF15, RF16.
- **Ator:** administrador. **Interesse:** organizar uso dos recursos e serviços.
- **Pré-condições:** administrador autenticado, alvo existente e regras de disponibilidade definidas.
- **Fluxo principal:** 1. Admin abre formulário único. 2. Seleciona categoria e objeto. 3. Informa requerente, motivo, data e intervalo. 4. Sistema valida referências, horários e disponibilidade. 5. Grava a reserva com proteção contra concorrência. 6. Atualiza a agenda.
- **Alternativas:** conflito propõe escolher outro horário sem gravar; edição revalida o novo intervalo desconsiderando o próprio registro; exclusão exige confirmação e política Q08; alvo indisponível impede nova reserva segundo RN08; falha não deixa registro parcial.
- **Pós-condição:** reserva criada, editada ou excluída conforme ação. Não há geração automática de tarefa confirmada.

## UC09 — Solicitar agendamento pelo AgroHub

- **Base:** C para integração; P para contrato e idempotência. RF14–RF16, RF22.
- **Ator primário:** solicitante no AgroHub. **Ator de suporte:** sistema AgroHub.
- **Interesse:** solicitar uso do laboratório pelo sistema já utilizado.
- **Pré-condições:** integração autenticada, contrato aprovado e alvo reconhecido no InovaLab. A direção exata da integração depende de Q07; este fluxo assume envio do AgroHub ao InovaLab.
- **Fluxo principal:** 1. Solicitante preenche pedido no AgroHub. 2. AgroHub envia dados e identificador externo. 3. InovaLab valida credencial, requerente e payload. 4. Aplica as mesmas regras de UC08. 5. Persiste a reserva e vínculo externo. 6. Retorna identificador e resultado para o AgroHub apresentar ao solicitante.
- **Alternativas:** credencial inválida é rejeitada; campos inválidos geram erro identificável; conflito não cria reserva; repetição da mesma chave e conteúdo retorna o registro anterior; mesma chave com conteúdo diferente gera conflito; perda de resposta permite reenvio seguro.
- **Pós-condição:** no máximo uma reserva por solicitação externa. Edição/cancelamento bidirecional não está confirmado.

## UC10 — Administrar materiais

- **Base:** C para campos; P para CRUD e permissões. RF17.
- **Ator proposto:** administrador. **Interesse:** consultar os materiais disponíveis.
- **Pré-condição:** permissão de materiais e vocabulários de Q09 definidos.
- **Fluxo principal:** 1. Ator cadastra nome, categoria, quantidade, status e fonte. 2. Sistema valida quantidade e valores. 3. Salva. 4. Disponibiliza para consulta.
- **Alternativas:** edição altera dados; quantidade negativa é rejeitada pela proposta RN10; exclusão segue a política de vínculos e histórico.
- **Pós-condição:** cadastro atualizado. Movimentações, reserva e consumo de estoque não estão confirmados.

## UC11 — Administrar banners

- **Base:** C para campos; P para gestão e programação. RF18, RF19.
- **Ator proposto:** administrador. **Interessados:** equipe de comunicação e visitantes.
- **Pré-condição:** permissão de publicação; agenda de exibição definida caso se use status agendado.
- **Fluxo principal:** 1. Admin informa título, imagem WebP, local e status. 2. Sistema valida a imagem e os campos. 3. Se agendado, recebe período conforme Q10. 4. Salva a configuração.
- **Alternativas:** arquivo inválido é rejeitado; outro formato só é aceito se uma conversão for aprovada; período inválido impede programação; administrador pode editar ou inativar.
- **Pós-condição:** banner cadastrado, ativo, inativo ou programado. A conversão automática de imagens não foi exigida pela fonte.

## UC12 — Visualizar banners publicados

- **Base:** D/P; RF19. **Ator:** visitante.
- **Pré-condição:** página home ou sobre acessível; política de publicação definida.
- **Fluxo principal:** 1. Visitante abre a página. 2. Sistema seleciona banners do local elegíveis no instante atual. 3. Exibe as imagens e alternativas textuais propostas para acessibilidade.
- **Alternativas:** sem banner elegível, página funciona sem essa seção; banner inativo ou fora do período não aparece.
- **Pós-condição:** conteúdo exibido sem revelar banners não publicados.

## Relações entre casos

UC03 e UC04 reutilizam autorização e validação de tarefa; UC08 e UC09 compartilham validação de reserva. Isso é compartilhamento de comportamento, não obrigação de transformar cada validação em um caso de uso separado. A autenticação aparece como pré-condição dos casos internos. A decisão de avaliação integra o ciclo da tarefa, mas seu ator ainda exige validação.
