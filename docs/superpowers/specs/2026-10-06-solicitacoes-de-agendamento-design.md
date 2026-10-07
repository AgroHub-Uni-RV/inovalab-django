# Solicitações de agendamento com aprovação administrativa

> Atualização de 07/10/2026: o módulo de integradores, sua API e seus recibos foram retirados. As referências a esse módulo nesta entrega registram decisões anteriores e não descrevem funções disponíveis. As conexões de Accounts, eventos e contato permanecem.

Data: 06/10/2026. Módulo: agenda.

## Objetivo e desenho aprovado

Permitir que usuários comuns solicitem agendamentos e acompanhem somente os
próprios registros. A solicitação reserva o horário somente depois da aprovação
de um administrador do laboratório. Disponibilizar uma página administrativa
para aceitar ou rejeitar solicitações. Na seleção de espaços, mostrar cadeados
e impedir a seleção dos espaços exclusivos somente para usuários comuns.

O responsável aprovou esse fluxo na conversa com a resposta “fechou”. Este
documento registra o desenho para a revisão escrita exigida pela skill
superpowers:brainstorming, antes do plano de implementação.

## Abordagem

Adicionar os estados Pendente, Confirmado e Rejeitado ao modelo `Agendamento`.
Manter os formulários por categoria, as validações de recursos, a versão de
concorrência e o histórico existentes. Essa abordagem evita duplicar os dados e
as validações em um modelo separado de solicitações.

Separar duas responsabilidades: consultar/criar agendamentos como usuário ativo
e administrar/avaliar agendamentos como administrador do laboratório. A
política administrativa continua sendo `accounts.policies.is_business_admin`;
`is_staff` isoladamente não concede esse acesso.

## Permissões e isolamento

- Usuário autenticado e ativo pode criar solicitações e consultar seus próprios
  agendamentos, detalhes, histórico e foto do criador vinculada ao agendamento.
- A propriedade do registro é definida por `criado_por`, preenchido no servidor
  com a conta autenticada. O texto de `requerente` não determina a permissão.
- Usuário comum não pode escolher outro criador, atribuir um estado, avaliar,
  editar nem cancelar agendamentos por formulário ou API.
- Administrador pode consultar e gerenciar os agendamentos e avaliar pedidos.
- Consultas de um usuário comum são filtradas pelo autor antes da pesquisa,
  paginação, contagens e carregamento por ID. URLs de registros de outro usuário
  não revelam seus dados. A mesma regra vale para a API, histórico e fotos.
- Usuário anônimo ou inativo não recebe acesso à agenda.

## Estados, persistência e histórico

O campo `situacao` tem os valores `pendente`, `confirmado` e `rejeitado`.
`avaliado_por` e `avaliado_em` registram o administrador e o instante da decisão
para solicitações avaliadas. O estado é controlado pelos serviços de domínio e
não é um campo editável do formulário de criação ou do payload comum da API.

| Origem/ação | Estado resultante | Ocupa horário |
| --- | --- | --- |
| Criação por usuário comum | Pendente | Não |
| Criação por administrador | Confirmado | Sim |
| Criação pela integração autenticada existente | Confirmado | Sim |
| Aprovação administrativa de pendente | Confirmado | Sim |
| Rejeição administrativa de pendente | Rejeitado | Não |
| Cancelamento administrativo | Mantém estado e registra `cancelado_em` | Não |

A migração preserva todos os agendamentos existentes como confirmados, sem
inventar um avaliador ou uma data de avaliação. Agendamentos cancelados
continuam cancelados. Não há mudança de categoria ou de responsável dos dados
existentes.

Somente pedidos pendentes podem ser aprovados ou rejeitados. A decisão
incrementa `versao` e gera um `EventoAgendamento` com ação de aprovar ou rejeitar,
ator, instante e alteração de estado. Decisões repetidas ou sobre uma versão
antiga retornam conflito sem sobrescrever a decisão anterior. Editar um pedido
como administrador não o aprova implicitamente.

## Disponibilidade e concorrência

Pendentes podem compartilhar o período com outros pedidos ou reservas
confirmadas; a criação ainda valida os campos, o período, os recursos
disponíveis e as restrições administrativas do espaço. A solicitação exibe que
aguarda confirmação e não garante disponibilidade.

Na aprovação, revalidar o alvo, a disponibilidade dos equipamentos e do material
selecionados e a ausência de reserva confirmada e não cancelada do mesmo alvo
no intervalo. Manter a regra atual de intervalos: término igual ao início de
outra reserva não é sobreposição. Os equipamentos opcionais de um serviço
continuam descritivos e não criam reservas automáticas de máquinas.

A validação, a alteração de estado e o histórico acontecem na mesma transação.
Reutilizar o bloqueio de alvos e a atualização condicionada à versão existentes
para impedir dupla aprovação ou conflito entre aprovação e criação
administrativa simultâneas. Um conflito mantém o pedido pendente e informa o
problema ao administrador. Rejeitar não exige um horário livre.

As consultas de ocupação, o calendário e os indicadores de reservas consideram
somente confirmados e não cancelados. Pendentes e rejeitados permanecem
consultáveis na tabela, sem aparecer como horários reservados.

## Telas e navegação

- Mostrar Agendamentos na navegação de usuários ativos. Para usuário comum,
  apresentar seus pedidos com estado visível e a ação Solicitar agendamento.
- A tabela do usuário comum inicialmente inclui seus registros de todos os
  períodos; o filtro de período é opcional. O calendário mostra o mês atual e
  somente suas reservas confirmadas. Aplicar um mês restringe a tabela e o
  calendário àquele período; limpar o filtro volta a todos os pedidos na tabela.
- Permitir filtrar a tabela por estado, categoria e pesquisa. Pendentes e
  rejeitados são acessíveis mesmo quando pertencem a outro mês. A listagem
  administrativa existente mantém inicialmente o mês atual.
- Incluir Solicitações de agendamento na navegação exclusiva de administradores.
  Essa página mostra inicialmente todos os pedidos pendentes, sem limite de
  mês, e oferece filtros e acesso aos detalhes necessários para decidir.
- Aceitar e Rejeitar são ações explícitas por POST com CSRF e versão do pedido.
  Após a decisão, atualizar a listagem e apresentar mensagem de resultado.
- Detalhes mostram o estado e, quando houver avaliação, quem decidiu e quando.
  Os comandos administrativos não aparecem para usuários comuns.
- Filtros continuam usando a atualização parcial existente, sem recarregar a
  página inteira. Criação e avaliação exigem acionamento explícito do botão.

## Seleção de espaços

Passar o perfil do ator ao formulário e ao widget de seleção de espaços.
Secretaria, laboratório maker e laboratório de robótica continuam identificados
no seletor existente. Para administradores, são opções habilitadas e sem
cadeado ou indicação de bloqueio administrativo. Para usuários comuns, são
opções visíveis, desabilitadas, com cadeado e indicação de uso exclusivo por
administradores. A indisponibilidade operacional de um recurso continua sendo
uma restrição distinta da exclusividade administrativa.

Validar novamente a exclusividade no servidor: manipular HTML, enviar IDs por
POST ou usar a API não permite ao usuário comum solicitar esses espaços.

## Componentes afetados

- `agenda/models.py` e migração: estados, avaliação e ações do histórico.
- `agenda/services.py`: criação por perfil, decisões transacionais e conflitos
  considerando somente reservas confirmadas.
- `agenda/selectors.py`: isolamento por autor e calendário confirmado.
- `agenda/views.py`, `agenda/urls.py` e templates: acesso por papel, listagem,
  detalhes e página administrativa de solicitações.
- `agenda/forms.py`, `agenda/widgets.py` e templates do widget: seleção de espaço
  conforme ator e formulário de avaliação estrito.
- `agenda/api.py` e `agenda/serializers.py`: leitura/criação própria, estado de
  saída e manutenção de operações administrativas protegidas.
- `core/navigation.py`, indicadores do dashboard e tag de acesso à agenda:
  entrada para usuários ativos e contagens coerentes com reservas confirmadas.
- Testes de agenda, core e integrações: novo fluxo e regressões de isolamento,
  concorrência e reservas existentes.

## Restrições globais

- Desenvolver somente o módulo de agenda nesta entrega.
- Manter login, perfil e gestão técnica de contas exclusiva de superusuários ativos.
- Manter a política administrativa definida por `accounts.policies.is_business_admin`.
- Manter o padrão visual e a escala definidos em `core/static/core/ui.css`.
- Manter os filtros com atualização parcial, sem recarregar a página inteira.
- Manter equipamentos opcionais nos serviços e as regras atuais de material próprio e gasto.
- Manter integrações autenticadas existentes com criação de reservas confirmadas.
- Não adicionar dependências para implementar este fluxo.
- Fazer commits convencionais em português por alteração importante.
- Executar testes automatizados Django e verificações básicas no navegador na entrega da implementação.

## Critérios de aceitação e verificação

1. Dois usuários comuns não veem registros um do outro na interface, API,
   histórico, fotos, pesquisas, paginação ou contagens.
2. Criação por usuário comum grava Pendente e não ocupa horários. Tentativas de
   atribuir autor, estado ou avaliar por conta própria são rejeitadas.
3. Administrador acessa a página de pedidos e pode aceitar ou rejeitar; usuário
   comum não consegue acessá-la nem executar suas ações.
4. Aprovar reserva o horário e identifica a decisão; rejeitar preserva o pedido
   visível ao seu autor sem ocupar o horário.
5. Reservas conflitantes, recursos indisponíveis e decisões concorrentes não
   geram dupla reserva nem sobrescrevem uma decisão válida.
6. Dados existentes, novas criações administrativas e integrações continuam
   confirmados; pendentes e rejeitados não alteram a ocupação do calendário.
7. Administrador seleciona os três espaços exclusivos sem cadeados. Usuário
   comum vê o bloqueio e não consegue contorná-lo enviando o ID diretamente.
8. Campos de serviço, filtros assíncronos, sidebar expandida/recolhida e layout
   móvel continuam utilizáveis. A revisão no navegador cobre criação, decisão,
   retorno ao usuário e seleção de espaços com ambos os perfis.

Verificar com `manage.py test --noinput`, `manage.py check` e
`manage.py makemigrations --check --dry-run`, usando o Python do `venv`. Aplicar
as migrações em ambiente de teste e conferir a preservação dos registros.
Testes mais profundos pelo responsável permanecem previstos pelo projeto.

## Revisão da especificação

Revisão interna concluída: sem seções pendentes, sem duplicação de subsistemas
e com definição explícita de autor, estados, ocupação de horários, tratamento
de conflitos e filtros de período. O próximo passo, após a revisão do
responsável, é escrever o plano de implementação com a skill writing-plans.
