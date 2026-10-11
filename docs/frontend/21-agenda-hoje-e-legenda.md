# Dia atual e legenda da Agenda

Solicitação de 11/10/2026: destacar o dia atual no calendário de `/agenda/`, acrescentar Evento, Recesso e Feriado à legenda e registrar a integração pendente com o calendário da UniRV.

## Comportamento entregue

Após a depuração, o dia atual recebe somente fundo amarelo suave (`#fff5df`) e o texto Hoje, com `aria-current="date"` para leitores de tela. Removidos o contorno adicional e o fundo do número. A data é calculada no servidor pelo fuso local configurado (`America/Sao_Paulo`), uma vez por montagem do calendário. Funciona sem JavaScript e acompanha a atualização dos filtros; a data é recalculada ao atualizar a página. Também marca hoje quando ele aparece nas células de um mês adjacente.

A legenda mantém Serviços e Visitas e acrescenta Evento (vermelho `#eb1b23`), Recesso (verde `#76b82a`) e Feriado (azul `#00a3d8`), usando as cores compartilhadas do painel. O indicador de hoje é independente dessas categorias. A ordem dos elementos, o calendário compacto, as reservas, os filtros e as permissões são preservados.

## Pendência: feriados e recessos oficiais da UniRV

**Pendente de integração.** Identificar e validar uma fonte oficial da UniRV, como API ou calendário institucional estruturado, que informe os feriados e recessos aplicáveis ao campus e ao ano letivo. Nenhuma fonte foi definida ou conectada nesta entrega.

A futura integração deverá fornecer tipo, nome, início e término das datas/períodos, definir o campus abrangido, o fuso horário e a forma de atualização. Planejar cache e comportamento em indisponibilidade para manter a Agenda disponível. Aplicar as marcações somente a partir dos dados oficiais; domingos, hoje e reservas não devem ser classificados automaticamente como feriado ou recesso. A definição de bloqueios para agendamento exige uma decisão própria.

## Eventos do AgroHub na Agenda

A solicitação seguinte do responsável integra `/agenda/` aos mesmos eventos públicos de Ecosystem já usados no dashboard, descritos em [Eventos AgroHub no calendário do index](14-eventos-agrohub-no-calendario.md). Reutiliza `load_events()` pelo adaptador do hospedeiro e o mesmo cache de cinco minutos, sem uma segunda integração ou gravações locais.

Títulos ativos aparecem em cartões vermelhos nos dias correspondentes. Dashboard e Agenda compartilham o cálculo dos períodos no fuso local: evento sem término ou instantâneo ocupa o dia de início, períodos atravessam dias/meses e término à meia-noite não ocupa o dia seguinte. A Agenda aplica o intervalo do mês consultado, inclusive fora dos seis meses do dashboard. Os títulos são escapados e têm identificação acessível; não abrem URLs externas.

Filtros de busca, categoria, situação e execução continuam filtrando somente as reservas; os eventos públicos permanecem visíveis no mês escolhido. Eventos não geram reservas, não alteram contadores/paginação, não classificam feriados/recessos e coexistem com Hoje e com os agendamentos. Falha do provedor mantém a Agenda disponível, com reservas e aviso de indisponibilidade dos eventos, seguindo o comportamento do dashboard.

## Verificação

`venv/Scripts/python.exe manage.py test inovalab_app.tests.agenda inovalab_app.tests.shared.test_clear_filters --noinput`: 208 testes passaram, incluindo a data local na virada do mês em UTC, hoje em uma célula de mês adjacente e ausência de marcação em meses distantes. `venv/Scripts/python.exe manage.py check` e `git diff --check`: aprovados.

Chromium com banco isolado em 1920, 1366, 900, 768, 390 e 320 px: data e destaque de hoje, texto acessível, rótulos e cores da legenda, filtros automáticos e Limpar filtros, mês distante, alternativa sem JavaScript e ausência de transbordamento externo. Revalidados calendário compacto, reservas, ordem dos elementos, criação por modal, acesso da equipe e rolagem do calendário pelo teclado.

Na entrega seguinte, `manage.py test inovalab_app.tests.agenda inovalab_app.tests.shared --noinput` aprovou 244 testes. Os cenários novos usam servidor HTTP local controlado para verificar feed/cache compartilhado, títulos escapados, eventos inativos/inválidos, múltiplos eventos, intervalos/fuso/meia-noite, reservas simultâneas, Hoje, filtros e recuperação após falha. As consultas externas dos demais testes são isoladas pela variável de processo `AGROHUB_API_BASE_URL=https://127.0.0.1:9/api/v1/`; os cenários da integração sobrescrevem essa configuração para o servidor local controlado.

A suíte completa `venv/Scripts/python.exe manage.py test --noinput`, com o mesmo isolamento, aprovou 666 testes em 136,215 segundos. `manage.py check` e `git diff --check`: aprovados.

Chromium com banco isolado e consulta somente leitura à API real: eventos da Agenda coincidem com os do dashboard, incluindo Batalha de Robôs, em desktop/celular e sem JavaScript. Verificados o fundo suave de Hoje, ausência de contorno/fundo no número e o layout/filtros/calendário compacto em seis larguras.

Sem novos modelos, migrações ou gravações de dados externos. A integração de feriados e recessos oficiais da UniRV continua pendente para uma entrega posterior. Sem push ou deploy.
