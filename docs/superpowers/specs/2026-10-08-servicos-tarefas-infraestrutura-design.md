# Serviços por solicitação, tarefas e infraestrutura

Data: 08/10/2026. Especificação aprovada pelo responsável com a resposta “certo”, incluindo o mapa das tarefas 2 e 3 para o agendamento 7. Implementação autorizada com “implemente” e concluída com testes e migração local; ver docs/modules/25-servicos-tarefas-infraestrutura.md.

Ajuste posterior autorizado em 08/10/2026: o prazo da tarefa passa a ser o mesmo do serviço vinculado, sem edição independente. O select contempla todos os status e administradores podem escolher diretamente qualquer um. Essas decisões substituem abaixo a previsão de prazo próprio opcional e de limitar as opções administrativas às transições anteriores. Ver o contrato atualizado no guia do módulo 25.

## Resultado esperado

Equipamentos deixam de ser agendáveis e permanecem na Infraestrutura. Cada solicitação define seu próprio serviço, com título, descrição e prazo. Toda tarefa pertence a um agendamento de serviço e possui responsável. Equipamento e consumo de material são informados opcionalmente na tarefa.

O responsável esclareceu que prazo significa **data e hora limite**, e que os dados são preenchidos **por solicitação**, substituindo a seleção de um serviço predefinido.

Esta entrega reúne as mudanças solicitadas neste fluxo e na navegação associada. Autenticação, autorização do hospedeiro, visitas, integração de eventos e contato conservam suas regras.

## Abordagem recomendada

Separar os dados solicitados (`Servico`) do controle do agendamento (`AgendaServico`), com vínculo exclusivo entre eles. Uma solicitação não reutiliza o serviço de outra. A tarefa aponta obrigatoriamente para `AgendaServico`; seu serviço é obtido desse vínculo, evitando duas seleções que possam divergir.

Alternativas consideradas:

- Concentrar dados e controle em `AgendaServico`: reduz um modelo, mas elimina a classe de serviço solicitada e mistura seu conteúdo com a aprovação.
- Manter o catálogo de serviços reutilizáveis: conserva mais do esquema atual, mas contradiz a definição de um serviço por solicitação.

A abordagem recomendada conserva a separação existente entre serviço e controle, alterando a relação para corresponder ao novo negócio.

## Serviço e agendamento

- `Servico` possui `titulo`, `descricao` e `prazo`, obrigatórios para novas solicitações. O prazo é armazenado como data/hora com fuso; o formulário apresenta data e hora separadas, com horário `hh:mm`.
- `AgendaServico` referencia exclusivamente um serviço e conserva autoria, criação, aprovação/recusa, cancelamento, versão e histórico.
- O formulário de serviço não pede item do catálogo, motivo, período de início/término, equipamento ou consumo de material. Título e descrição definem o pedido; prazo define sua data limite.
- Solicitações de contas comuns continuam pendentes. Administradores mantêm a confirmação na criação e a avaliação das solicitações. Cancelamento continua seguindo as regras de autoria e de administradores já vigentes.
- Solicitações independentes podem ter o mesmo prazo. Não há reserva de equipamento nem conflito entre serviços por coincidência de data.
- Agenda e dashboard mostram o serviço na data de seu prazo, como uma ocorrência pontual. Os filtros de mês incluem o prazo, sem criar artificialmente um intervalo de execução. Visitas continuam usando seus períodos reais.
- O modal oferece Visita e Serviço, preservando validação, confirmação, retorno após login, CSRF, teclado e a alternativa sem JavaScript.
- A API utiliza os novos campos e rejeita novos pedidos de equipamento e os campos removidos de serviço. Os contratos alterados serão documentados com exemplos e erros.

## Tarefas

- Agendamento de serviço, descrição e responsável são obrigatórios. O formulário apresenta o título e o identificador do agendamento para distinguir solicitações semelhantes; não apresenta o catálogo antigo.
- Novas tarefas só podem apontar para um agendamento de serviço confirmado e não cancelado. Tarefas existentes conservam seu vínculo se o agendamento posteriormente mudar de situação; alterações em outros dados não exigem troca de vínculo.
- Equipamento é uma FK opcional para `Equipamento`.
- Material gasto é uma FK opcional para `Material`.
- Quantidade de material gasto é um `CharField` opcional, permitindo texto como `200 g`, `2 unidades` ou `1,5 m`. Nenhum desses dois campos se torna obrigatório por preencher o outro.
- O registro do consumo é informativo e não altera estoque automaticamente, pois não foi solicitada conversão de unidades nem movimentação de estoque.
- O prazo próprio da tarefa permanece opcional. Início, conclusão, versão, exclusão lógica, escopo por responsável e histórico conservam seu funcionamento.
- A alteração de status passa a um select com o status atual e os destinos permitidos ao usuário, acompanhado de uma ação explícita de salvar. Os botões individuais de transição são removidos.
- O servidor continua validando permissões, transições e versão. O select não permite pular aprovações nem atribui poderes administrativos ao responsável.
- Equipamento, material, quantidade e vínculo do agendamento aparecem no detalhe e no histórico das alterações.

## Infraestrutura e exclusão de equipamentos

- A navegação usa **Infraestrutura**, direcionando à listagem de equipamentos.
- A página apresenta apenas equipamentos, sem aba, coluna ou cadastro operacional de serviços.
- Administradores podem excluir equipamentos mediante confirmação e POST com CSRF. A API oferece a mesma operação autorizada.
- A exclusão é lógica: retira o equipamento da Infraestrutura e das opções de novas tarefas, conservando registros, fotos e referências históricas. Uma tarefa já vinculada continua exibindo seu equipamento e pode ser editada sem perdê-lo.
- A criação de agendamentos de equipamento é bloqueada na interface, rotas, API e serviços de domínio. Retirar apenas o card do modal não é suficiente.
- Agendamentos de equipamento existentes em outros bancos permanecem consultáveis como legado, sem permitir novos agendamentos nem editar a reserva. Ações necessárias de cancelamento conservam as regras vigentes.

## Navegação

- Remover o atalho Páginas da sidebar.
- A logo completa aponta para o início institucional `/`, interpretando o destino vazio solicitado como a raiz do site. A resolução da URL respeita o prefixo do hospedeiro.
- No desktop, a sidebar fica sempre expandida, com ícones e textos. Remover o modo estreito, o controle de recolher e a preferência antiga de largura no `localStorage`.
- No celular, conservar a abertura e o fechamento do menu completo por botão, backdrop e Escape, com foco e teclado. Fechado, o menu fica oculto; não vira uma barra estreita.
- Conferir largura de conteúdo, tabelas, formulários e calendário com a sidebar expandida e em 360 px.

## Migração de dados

- Preservar os IDs de agendamentos, tarefas, equipamentos, materiais e eventos. As relações novas são preenchidas por migração, sem apagar o banco ou carregar dados demonstrativos.
- O catálogo antigo de serviços permanece como dados de legado, sem telas de manutenção ou carga inicial operacional. Seus registros não se transformam automaticamente em novas solicitações.
- Para cada agendamento de serviço existente, criar seu serviço individual usando o nome do catálogo como título, o motivo do agendamento como descrição e seu término como prazo. Conservar as observações e os eventos anteriores.
- Campos antigos de equipamento e consumo do agendamento permanecem retidos como legado, sem atribuí-los arbitrariamente a uma tarefa. Não presumir que todas as tarefas consumiram o mesmo material.
- Tarefas antigas exigem um mapa explícito para agendamentos de serviço. Não escolher por nome, responsável, proximidade temporal ou apenas por um candidato encontrado.
- No SQLite local observado durante a preparação, o mapa proposto é **tarefa 2 → agendamento 7** e **tarefa 3 → agendamento 7**. Ambos compartilham o serviço antigo; a revisão deste documento inclui a decisão de usar esse mapa.
- Outros bancos devem fornecer seu próprio mapa antes da atualização. A verificação bloqueia a migração quando houver tarefas sem vínculo definido ou destinos incompatíveis, indicando os IDs pendentes.
- Fazer backup consistente antes de aplicar a migração ao banco de desenvolvimento. Verificar os vínculos e históricos numa cópia antes de atualizar o banco original. Não atualizar banco remoto nem publicar esta entrega sem autorização específica.

## Verificação prevista

- Testes Django de modelos, serviços, formulários, views e APIs cobrindo obrigatoriedade dos vínculos, campos opcionais, isolamento de solicitações, autorização e rejeição de agendamentos de equipamento.
- Testes de status cobrindo destinos permitidos, tentativa adulterada, CSRF, início/conclusão e conflito de versão.
- Testes de exclusão de equipamento cobrindo retirada das opções e preservação das referências existentes.
- Testes de migração cobrindo IDs, histórico, serviços individualizados, mapa explícito e bloqueio por tarefas sem mapa.
- Suíte completa com `python manage.py test --noinput`, `python manage.py check` e `python manage.py makemigrations --check --dry-run` usando o Python do ambiente virtual.
- Navegador: criar serviço pelo modal, criar tarefa vinculada, preencher campos opcionais, mudar status pelo select, excluir equipamento e conferir desktop/celular, logo e ausência do atalho Páginas.

O plano aprovado foi executado; as evidências da entrega estão documentadas no módulo 25. Commits importantes seguem o formato em português indicado no AGENTS.md.
