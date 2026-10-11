# Dia atual e legenda da Agenda

Solicitação de 11/10/2026: destacar o dia atual no calendário de `/agenda/`, acrescentar Evento, Recesso e Feriado à legenda e registrar a integração pendente com o calendário da UniRV.

## Comportamento entregue

O dia atual recebe contorno neutro, número destacado e o texto Hoje, com `aria-current="date"` para leitores de tela. A data é calculada no servidor pelo fuso local configurado (`America/Sao_Paulo`), uma vez por montagem do calendário. Funciona sem JavaScript e acompanha a atualização dos filtros; a data é recalculada ao atualizar a página. Também marca hoje quando ele aparece nas células de um mês adjacente.

A legenda mantém Serviços e Visitas e acrescenta Evento (vermelho `#eb1b23`), Recesso (verde `#76b82a`) e Feriado (azul `#00a3d8`), usando as cores compartilhadas do painel. O indicador de hoje é independente dessas categorias. A ordem dos elementos, o calendário compacto, as reservas, os filtros e as permissões são preservados.

## Pendência: feriados e recessos oficiais da UniRV

**Pendente de integração.** Identificar e validar uma fonte oficial da UniRV, como API ou calendário institucional estruturado, que informe os feriados e recessos aplicáveis ao campus e ao ano letivo. Nenhuma fonte foi definida ou conectada nesta entrega.

A futura integração deverá fornecer tipo, nome, início e término das datas/períodos, definir o campus abrangido, o fuso horário e a forma de atualização. Planejar cache e comportamento em indisponibilidade para manter a Agenda disponível. Aplicar as marcações somente a partir dos dados oficiais; domingos, hoje e reservas não devem ser classificados automaticamente como feriado ou recesso. A definição de bloqueios para agendamento exige uma decisão própria.

Evento também está representado apenas na legenda da Agenda nesta entrega. O dashboard já tem uma integração de eventos públicos do AgroHub, descrita em [Eventos AgroHub no calendário do index](14-eventos-agrohub-no-calendario.md); eventual reutilização em `/agenda/` fica para uma entrega posterior. A legenda por si não importa nem cadastra eventos, feriados ou recessos.

## Verificação

`venv/Scripts/python.exe manage.py test inovalab_app.tests.agenda inovalab_app.tests.shared.test_clear_filters --noinput`: 208 testes passaram, incluindo a data local na virada do mês em UTC, hoje em uma célula de mês adjacente e ausência de marcação em meses distantes. `venv/Scripts/python.exe manage.py check` e `git diff --check`: aprovados.

Chromium com banco isolado em 1920, 1366, 900, 768, 390 e 320 px: data e destaque de hoje, texto acessível, rótulos e cores da legenda, filtros automáticos e Limpar filtros, mês distante, alternativa sem JavaScript e ausência de transbordamento externo. Revalidados calendário compacto, reservas, ordem dos elementos, criação por modal, acesso da equipe e rolagem do calendário pelo teclado.

Sem novos modelos, migrações, consultas externas ou alterações de banco. A integração institucional descrita acima continua pendente para uma entrega posterior. Sem push ou deploy.
