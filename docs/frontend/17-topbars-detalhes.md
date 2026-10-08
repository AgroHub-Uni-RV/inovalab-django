# Topbars dos detalhes de tarefas e agendamentos

Entrega visual de 08/10/2026, com escopo explícito aprovado após a reversão do modal de detalhes. As páginas permanecem páginas; os modais anteriores de criação e edição de tarefas não mudam.

A topbar do agendamento conserva edição, avatar/autoria, data, categoria e retorno. O status do agendamento de serviço passa a aparecer somente nela. O restante de `sheet-layout` permanece, inclusive o aviso de confirmação pendente. Visitas e equipamentos mantêm o status no conteúdo, como antes; os detalhes pessoais não foram alterados.

A tarefa conserva seletor e botão Salvar status, responsáveis, prazo, etiqueta de status e retorno. Os controles ficam alinhados, com mesma altura e espaços da escala compartilhada. O retorno ganha área de interação maior e foco visível. No celular, o retorno reserva espaço apenas na primeira linha; seletor e botão ficam empilhados quando a largura disponível é até 450 px. Nomes longos podem quebrar sem truncar informações.

Os novos estilos são limitados a `sheet-detail-topbar` e seus filhos nos dois templates de detalhe. Nenhuma mudança de `sheet-layout`, regra de negócio, autorização, CSRF, versão, histórico, URL, modelo, migração ou API.

## Verificação

- `venv/Scripts/python.exe manage.py test --noinput`: 565 testes passaram.
- `venv/Scripts/python.exe manage.py test inovalab_app.tests.portability --settings=inovalab_app.tests.host_settings --noinput`: 7 testes passaram.
- `manage.py check`, `makemigrations --check --dry-run` e `git diff --check`: sem problemas ou migrações pendentes.
- Chromium, SQLite isolado: detalhes em 1366, 1100, 900, 768, 390 e 360 px sem overflow; área de retorno, legibilidade do seletor, alinhamento/empilhamento dos controles e posição única do status conferidos. O teste considera a largura disponível com a sidebar, não só a largura da janela.

Banco real preservado. Conferir nomes reais extensos e outros navegadores na depuração do responsável; usar Ctrl+F5 se o navegador mantiver os estilos anteriores em cache.
