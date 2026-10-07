# Usuário e horários do agendamento

> Atualização de 07/10/2026: o módulo de integradores, sua API e seus recibos foram retirados. As referências a esse módulo nesta entrega registram decisões anteriores e não descrevem funções disponíveis. As conexões de Accounts, eventos e contato permanecem.

**Correção posterior de 06/10/2026:** categorias atuais são Equipamentos, Serviços e Visitas. Espaços não admitem novas reservas; visitas recebem somente dia e horários. As seções abaixo registram a entrega anterior; contrato corrente em [agenda](../modules/04-agenda.md).


Entrega de 06/10/2026, restrita ao fluxo existente da agenda.

O campo livre `Agendamento.requerente` foi removido. O usuário autenticado que
cadastra a reserva é registrado em `criado_por`; uma edição administrativa
mantém esse criador e registra o editor no histórico. Listagem, calendário,
detalhe e Dashboard exibem nome/sobrenome ou login do criador. A pesquisa aceita
login, nome, sobrenome e nome completo. Sem conta associada, a identificação
usa o ator do evento de criação, inclusive a origem das integrações.

O formulário oferece `dia`, `hora_inicio` e `hora_termino`, no horário de Brasília.
O término precisa ser posterior ao início no mesmo dia. Esses valores compõem
os campos `inicio` e `fim` já existentes, mantendo validação de conflitos,
controle de versão, aprovação administrativa e conversão de fuso horário.
A troca de categoria conserva o dia e os horários ainda não salvos.

Ao editar sem alterar dia/horários, o período original é preservado integralmente,
inclusive microssegundos e reservas antigas de vários dias. Para estas, o
formulário mostra o período original e informa que alterar dia/horários redefine
a reserva para o dia selecionado.

## API e migração

A API interna deixa de aceitar ou retornar `requerente`; aceita os mesmos
`inicio`/`fim` ISO 8601 com fuso e retorna `criado_por` e `criado_por_nome` somente
para leitura. Tentar definir a identidade pelo cliente é rejeitado.

A API externa de integrações conserva seu contrato e sua idempotência;
`requerente` e `requerente_id` externos não definem um usuário local nem são
passados ao modelo de agendamento. Seus agendamentos continuam sem conta
interna associada e com a origem registrada no histórico.

`agenda.0006_remove_agendamento_requerente` remove a coluna livre, mantendo
criador, período, situação, versão, cancelamento, recursos e eventos existentes.
O histórico anterior pode continuar contendo a chave `requerente` como registro
das alterações antigas. A migração local foi aplicada após backup do SQLite
no diretório temporário do Windows. Em outros ambientes, executar:

```powershell
& .\venv\Scripts\python.exe manage.py migrate
```

## Verificações

Comandos executados:

```powershell
& .\venv\Scripts\python.exe manage.py test --verbosity 1
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\venv\Scripts\python.exe -m pip check
git diff --check
```

424 testes passaram. Check sem problemas, nenhuma migração pendente de geração
e nenhuma incompatibilidade nas dependências. A suíte cobre criação sem
requerente, identidade protegida, edição por administrador sem troca de autor,
horários inválidos, fuso de Brasília, preservação de precisão e de períodos
antigos, migração com histórico e regressões das integrações.

Chrome com banco SQLite e contas temporárias: cadastro de Sala 01 por usuário
comum, rejeição de término anterior ao início, detalhe com criador e estado
Pendente, preservação do dia/horários ao trocar categoria e edição administrativa.
Desktop em 1366 px com sidebar expandida e celular em 390 px sem transbordamento
horizontal; o formulário usa os padrões compartilhados de espaçamento e campos.

O responsável ainda deve depurar com contas reais, conferir os períodos existentes
e validar migração/concorrência no PostgreSQL do ambiente de destino. Nenhum
deploy integra esta entrega. Aguardar essa depuração antes de iniciar outro módulo.

## Complemento: observações opcionais

O agendamento também aceita `observacoes`, um texto opcional disponível para
serviços, equipamentos e espaços. O formulário usa uma área de texto com largura
completa; o detalhe preserva quebras de linha e escapa HTML. Ao omitir o texto,
o campo fica vazio. A edição administrativa permite alterar ou limpar observações
e registra essas alterações no histórico, com o mesmo controle de versão.
A troca de categoria conserva as observações ainda não salvas.

A API interna aceita e retorna `observacoes`; PATCH sem esse campo conserva o
texto anterior. O contrato externo das integrações permanece inalterado.
A migração `agenda.0007_agendamento_observacoes` foi aplicada localmente e
inicializa reservas existentes com texto vazio. Executar `manage.py migrate`
nos outros ambientes.

Os comandos de teste e verificação acima foram repetidos: **430 testes passaram**,
check sem problemas, nenhuma migração pendente de geração e diff sem erros.
Chrome, com contas e banco temporários: cadastro com observações e exibição no
detalhe; campo opcional conferido. Desktop em 1366 px com sidebar expandida e
celular em 390 px sem transbordamento horizontal. A revisão independente foi
aprovada. O responsável deve conferir textos longos e edição com contas reais,
além das verificações de PostgreSQL já indicadas.
