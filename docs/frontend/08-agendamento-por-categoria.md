# Agendamentos por categoria e identificação do criador — 06/10/2026

**Correção posterior de 06/10/2026:** categorias atuais são Equipamentos, Serviços e Visitas. Espaços não admitem novas reservas; visitas recebem somente dia e horários. As seções abaixo registram a entrega anterior; contrato corrente em [agenda](../modules/04-agenda.md).


Complemento posterior: [seleção visual de espaços e material utilizado](09-selecao-de-espacos-e-material.md). Serviços com material do laboratório agora também exigem selecionar o material cadastrado no formulário.

O formulário adapta os campos à categoria selecionada. Serviço mantém os campos atuais e acrescenta Equipamentos, Tem material próprio? e Material gasto (g). Equipamento e Espaço mantêm os campos atuais, com a seleção do objeto identificada pelo nome da categoria. A troca continua automática por POST, preservando os campos comuns e a versão da edição; nenhum agendamento é salvo pela troca de categoria.

O responsável confirmou que Equipamentos é uma seleção múltipla opcional: serviços como consultoria podem não utilizar máquinas. Esse vínculo descreve o uso no serviço e não cria reservas automáticas de equipamentos. O agendamento continua tendo um único alvo exclusivo. Máquinas indisponíveis não podem ser acrescentadas; vínculos anteriores podem ser mantidos ao editar somente dados descritivos.

No formulário de serviço, é obrigatório escolher Sim ou Não para material próprio. Sim oculta e desabilita o campo de gasto. Não exibe o campo obrigatório e exige uma quantidade positiva em gramas, com até três casas decimais. O gasto é registrado no agendamento, sem alteração do estoque. Ao mudar um agendamento de serviço para outra categoria, seus vínculos de máquinas e campos de material são limpos, com os valores anteriores preservados no histórico.

## Detalhe e foto

O topo de `/agenda/<id>/` mostra foto e nome completo do criador, com fallback para login e avatar com inicial. O requerente permanece como informação própria no corpo do detalhe. Editar com outro administrador não muda quem criou a reserva. Quando não há conta de criador, o nome vem do evento de criação, incluindo integrações externas; registros sem essa informação mostram Não registrado.

A foto usa `/agenda/<id>/criador/foto/`, acessível somente a administradores ativos que possam consultar o agendamento. O acesso geral às fotos em `/usuarios/<id>/foto/` permanece restrito como antes. A resposta de foto não permite cache e usa `nosniff`.

A categoria recebe um destaque lilás somente com texto, usando os rótulos Serviços, Equipamentos e Espaço. A correção posterior de 06/10/2026 removeu a seta e substituiu Salas por Espaço, inclusive no campo Categoria do detalhe. O detalhe de serviço também apresenta máquinas, escolha de material próprio e gasto quando aplicável.

Validação dessa correção: `python manage.py test --noinput` aprovou 355 testes; `python manage.py check`, `python manage.py makemigrations --check --dry-run` e `git diff --check` passaram. Chrome em desktop e celular de 360 px confirmou Espaço sem ícone no destaque e sem transbordamento da página. Sem migrações. Resta ao responsável conferir os dispositivos e navegadores de uso diário.

## Persistência e API

Os novos campos são `equipamentos` (lista de IDs de equipamentos), `material_proprio` (booleano) e `material_gasto_gramas` (decimal). A API interna os aceita e os devolve; o gasto é serializado com três casas decimais. A validação de material e categoria acontece também na camada de gravação, e a regra de material tem restrição no banco. Alterações permanecem transacionais e protegidas pela versão, com registro no histórico.

Agendamentos existentes e consumidores que enviam somente os campos anteriores continuam válidos. Não se presume material próprio ou consumo para dados antigos: os campos ficam nulos e são apresentados como Não informado. Ao editar esses registros pelo formulário de serviço, deve-se escolher Sim ou Não. A API externa mantém seu contrato anterior; os campos adicionais desta entrega não foram incluídos nos pedidos externos.

Execute `python manage.py migrate` ao atualizar outro ambiente. As migrações da agenda `0002` e `0003` já foram aplicadas no banco local.

## Validação

```powershell
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
node --check core/static/core/auto-apply.js
git diff --check
```

345 testes Django aprovados, incluindo 16 testes novos de dados do serviço, equipamentos opcionais/múltiplos, exigência e precisão de gramas, invariantes no banco, troca de categoria, histórico, versões antigas, cancelamento, ausência de reserva implícita de máquinas, API, criador e proteção da foto. Os testes anteriores de concorrência e integração também passaram. Configuração, sintaxe JavaScript e migrações sem pendências.

Chrome com banco de teste em memória: criação de serviço com duas máquinas e material do laboratório; criação de serviço sem máquinas e com material próprio; gasto condicional; troca entre as três categorias preservando requerente; foto e nome do criador distintos do requerente; destaque lilás; desktop, menu expandido em 1201 px e celular em 360 px. O navegador teve uma falha inicial de conexão na sessão de automação; a verificação foi concluída em uma sessão nova.

Depuração restante pelo responsável: validar o fluxo com serviços e consumos reais, nomes extensos e fotos reais; conferir dispositivos e navegadores usados pela equipe. Bloqueio simultâneo das máquinas vinculadas e movimentação de estoque exigiriam etapas próprias.
