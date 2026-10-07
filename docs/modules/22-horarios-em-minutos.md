# Horários em horas e minutos

## Solicitação de 07/10/2026

Exibir e editar horários em `hh:mm`, sem segundos, nos agendamentos, nas tarefas e nos banners.

## Implementação

- Serviços, equipamentos e visitas usam campos `time` com formato `%H:%M` e `step="60"`, inclusive no modal de criação.
- O prazo da tarefa e o início/fim de exibição do banner usam `datetime-local` com formato `%Y-%m-%dT%H:%M` e `step="60"`, no horário de Brasília.
- Detalhes, listas, cancelamento e horários visíveis no histórico da agenda exibem `H:i`. O período do banner segue o mesmo formato.
- `core/form_times.py` centraliza a normalização dos horários enviados pelos formulários. Novos horários ou minutos alterados recebem segundos e microssegundos iguais a zero.
- Se o usuário mantiver o minuto exibido de um registro existente, sua precisão original é preservada. Isso evita modificar o prazo/período e gerar alterações de histórico ao editar somente descrição, observações ou título. Nas visitas, mudar a data também inicia um período em minutos.
- Períodos legados de agendamentos que ultrapassam um dia continuam preservados quando o período exibido não é alterado.

Os modelos `TimeField` e `DateTimeField` já suportam esses valores; não há migração nem alteração em lote dos registros existentes. As APIs e os dados técnicos do histórico continuam preservando a precisão dos timestamps.

## Verificação

- `python manage.py test agenda.tests.test_web agenda.tests.test_visits tarefas.tests.test_web conteudo.tests.test_web --noinput`: 62 testes passaram.
- `python manage.py test --noinput`: 572 testes passaram.
- `python manage.py check`: sem problemas.
- `python manage.py makemigrations --check --dry-run`: nenhuma alteração detectada.
- `node --check core/static/core/auto-apply.js` e `git diff --check`: sem problemas.
- Chromium em banco SQLite e mídia isolados: criação das três categorias no modal com `hh:mm`, validação de intervalo, troca de categoria, gravação, prazo de tarefa e período de banner em edição/criação, ausência de erros JavaScript e conferência visual em desktop/celular.

Os testes automatizados também verificam a conservação dos segundos/microssegundos dos registros legados quando o período é mantido e a normalização dos minutos alterados. Resta ao responsável a depuração mais profunda nos navegadores e dados do seu ambiente.
