# Solicitações de agendamento e aprovação administrativa

Entrega de 06/10/2026. Especificação aprovada em
`docs/superpowers/specs/2026-10-06-solicitacoes-de-agendamento-design.md`.
Implementação direta na branch `feat/solicitacoes-agendamento`, derivada de `main`.

## Comportamento entregue

Usuários autenticados e ativos acessam Agendamentos na sidebar, solicitam uma
reserva e consultam somente os registros criados pela própria conta. A autoria
é definida no servidor; o texto de Requerente não altera a permissão de acesso.
Detalhes, histórico, fotos e API seguem o mesmo isolamento.

Pedidos de usuários comuns entram como **Pendente**, sem ocupar horários.
A listagem inicialmente mostra todos os períodos e permite filtrar por mês,
categoria, situação e pesquisa. Pedidos **Rejeitados** permanecem visíveis ao
autor. Calendário e indicadores contam somente reservas **Confirmadas**.

Administradores acessam **Solicitações de agendamento** em
`/agenda/solicitacoes/`. A tela inicia com todos os pendentes, sem restrição de
mês, e permite aceitar, rejeitar e consultar os detalhes. Filtros de outras
situações mostram solicitações já avaliadas, sem misturar reservas criadas
diretamente por administradores.

Aceitar e rejeitar exigem POST, CSRF e versão atual do pedido. A decisão
registra administrador, data e histórico. Aceitar revalida disponibilidade dos
recursos e conflitos na mesma transação da confirmação. Um conflito mantém o
pedido pendente e retorna HTTP 409. Uma versão antiga ou uma decisão repetida
também não sobrescreve o registro.

Criações administrativas e integrações existentes continuam confirmadas.
Equipamentos opcionais de serviços não criam reservas adicionais de máquinas;
material próprio e tipo/gramas de material do laboratório mantêm as regras
existentes. Usuários comuns podem criar e consultar, enquanto edição,
cancelamento e avaliação continuam administrativos.

Secretaria, laboratório maker e laboratório de robótica ficam selecionáveis e
sem cadeados para administradores. Para usuários comuns, aparecem com cadeado
e seleção desabilitada. Formulário, serviço e API impedem contornar a restrição
enviando o ID do espaço diretamente.

Os filtros usam a atualização parcial existente. As decisões administrativas e
a criação continuam dependendo do acionamento explícito do botão.

## Migração local

A migração `agenda.0005_agendamento_avaliado_em_agendamento_avaliado_por_and_more`
foi aplicada com `manage.py migrate`. Os dois agendamentos existentes foram
preservados, mantendo autor, versão, cancelamento e período, com estado
Confirmado e sem inventar avaliador. Foi criado um backup SQLite anterior à
migração no diretório temporário do Windows.

## Verificações automatizadas

Comandos executados com o Python do `venv`:

```powershell
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Resultado: **387 testes passaram**; check sem problemas; nenhuma alteração de
modelo sem migração; nenhuma falha de whitespace. A suíte inclui criação por
perfil, aprovação/rejeição, estado protegido, recursos indisponíveis, autoria,
acesso cruzado web/API/foto/histórico, filtros e paginação, CSRF, preservação dos
dados pela migração e disputas simultâneas de aprovação/criação/decisão.

As integrações existentes passaram nos testes de regressão.

## Verificações no navegador

Servidor temporário em `127.0.0.1:8001`, usando cópia em memória do banco local,
contas de teste e diretório temporário de mídia. Nenhuma conta real teve senha
ou permissões alteradas. O servidor temporário e os navegadores foram fechados
ao final.

- Usuário criou um pedido de serviço sem máquinas e o viu como Pendente.
- Administrador rejeitou o pedido; o autor o viu como Rejeitado.
- Usuário solicitou Sala 01; administrador aceitou; o autor viu Confirmado e
  uma única reserva no calendário, enquanto o pedido rejeitado ficou na tabela.
- Listagem do usuário não exibiu pedido de outra conta. Acesso ao detalhe e
  foto do outro pedido retornou 404; a página administrativa retornou 403.
- Seleção dos três espaços exclusivos foi habilitada para administrador, sem
  cadeados; para usuário comum houve três opções restritas e desabilitadas.
- Pesquisa na página administrativa atualizou a lista preservando
  `performance.timeOrigin` e a mesma instância da sidebar, sem recarga completa.
- Conferidas sidebar expandida/recolhida, navegação móvel e telas em 390 px.
  Documento sem transbordamento horizontal; tabelas usam rolagem interna.
- Nenhum erro de JavaScript reportado pelo navegador durante os fluxos.

## Depuração pelo responsável

Conferir as regras com contas reais de usuário comum e do grupo Administradores,
incluindo detalhes de serviços com material do laboratório, todos os estados,
filtros de períodos anteriores e decisões em sessões concorrentes. A concorrência
automatizada desta entrega foi verificada em SQLite; validar também no banco
usado em produção, caso seja PostgreSQL.

Aguardar essa depuração antes de iniciar outro módulo, conforme `AGENTS.md`.
