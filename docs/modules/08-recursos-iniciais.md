# Máquinas e espaços iniciais — 06/10/2026

As imagens fornecidas nesta solicitação definem a carga de seis equipamentos: Plotter de impressão, Impressora 3D, Corte a laser, Plotter de corte, Óculos de realidade virtual e Scanner 3D manual. As descrições foram transcritas dos cartões. Serviços continuam sendo cadastros independentes.

| Espaço | Capacidade | Agendamento |
| --- | --- | --- |
| Secretaria | Não informada | Somente administradores |
| Sala 01 | 4 | Interno e integração |
| Sala 02 | 4 | Interno e integração |
| Área de convivência | 24 | Interno e integração |
| Sala 03 | 4 | Interno e integração |
| Sala 04 | 4 | Interno e integração |
| Espaço de coworking | 40 | Interno e integração |
| Laboratório maker | Não informada | Somente administradores |
| Laboratório de robótica | Não informada | Somente administradores |

Todos começam disponíveis. A imagem não informa as capacidades dos três espaços restritos, que ficam nulas em vez de receber um número inventado. Administradores podem informar a capacidade e manter a restrição no formulário do catálogo; números preenchidos continuam exigindo inteiros positivos.

O campo `somente_administradores` aparece na API interna de espaços e pode ser mantido apenas por administradores do laboratório. A agenda interna continua exclusiva de administradores ativos; o catálogo permanece consultável pelos usuários internos ativos. Integrações não recebem espaços restritos no catálogo externo e recebem HTTP 403 ao tentar reservar esses IDs diretamente. A verificação fica no núcleo de gravação da agenda, dentro da transação e após carregar o recurso atual. A rejeição não grava reserva, evento ou recibo.

## Carga e validação

Execute `python manage.py migrate` ao atualizar outro ambiente. As migrações `0003` e `0004` criam os campos e carregam os registros; já foram aplicadas no ambiente local desta entrega. O comando `python manage.py carregar_recursos_iniciais` permite repetir a carga, mantendo nomes, descrições, capacidades, status e restrições já editados. O código inicial privado e único identifica cada registro; a carga não associa automaticamente cadastros manuais de mesmo nome. Reverter a migração de dados não apaga registros.

- `python manage.py test --noinput`: 323 testes aprovados, incluindo dados das imagens, carga repetida, preservação das edições, reposição de registros ausentes, catálogo externo e permissões de reserva.
- `python manage.py check`: nenhuma ocorrência.
- `python manage.py makemigrations --check --dry-run`: nenhuma migração pendente.
- `python manage.py carregar_recursos_iniciais`, após migrar: zero registros novos, confirmando a repetição da carga local.
- Chrome: catálogo, indicação dos três espaços restritos e formulário de edição; sidebar expandida em 1201 px sem transbordamento da página.

Depuração restante pelo responsável: confirmar as capacidades ainda não informadas, revisar os textos dos equipamentos e testar com o consumidor externo real.
