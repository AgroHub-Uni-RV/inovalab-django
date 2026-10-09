# Limpar filtros

Entrega de 08/10/2026, com o padrão aprovado pelo responsável. O botão **Limpar filtros** está nas sete telas que possuem filtros: Agendamentos, Solicitações, Meus agendamentos, Tarefas, Materiais, Banners e Usuários.

## Comportamento

A ação remove a busca, seleções, datas, aba de status e paginação. A listagem retorna à primeira página e à aba Todas/Todos, sem mudar suas regras de acesso. Em Meus agendamentos, continuam visíveis somente os registros da conta autenticada.

Na Agenda, o destino inclui `?mes=`: omitir o parâmetro faria o servidor restaurar o mês padrão do administrador. Com mês vazio, a lista mostra todos os agendamentos autorizados; o calendário continua mostrando o mês atual.

As sete telas reutilizam `shared/clear_filters.html`, com o mesmo texto e padrão visual `secondary-button`. O destino é a rota atual, sem os parâmetros anteriores e preservando o prefixo do hospedeiro. É um link real com aparência de botão: continua funcional sem JavaScript e pode ser acionado pelo teclado ou aberto em outra aba.

Nas telas que já usam atualização automática, a limpeza aproveita o mecanismo existente: cancela a busca pendente/debounce, consulta o destino limpo, substitui o formulário e resultados e atualiza o histórico. A ação não combina os antigos valores com o destino limpo. Respostas atrasadas não podem restaurar filtros; falhas conservam os dados atuais e permitem tentar novamente a limpeza. Voltar/Avançar recupera os filtros anteriores. Meus agendamentos mantém sua navegação tradicional.

No celular, o botão usa a largura disponível e quebra para uma linha própria. Em Usuários, o campo e o botão de busca continuam juntos; Limpar filtros fica ao lado no desktop e abaixo no móvel. Nenhum formulário de criação/edição, ação de gravação, endpoint, permissão ou modelo foi alterado.

## Verificação

- `python manage.py test --noinput`: 594 testes passaram, incluindo oito testes novos de limpeza que seguem o link renderizado e verificam resultados, abas, página 2 real, calendário e isolamento pessoal.
- `python manage.py test inovalab_app.tests.portability --settings=inovalab_app.tests.host_settings --noinput`: oito testes passaram, incluindo a limpeza sob `/laboratorio/` com usuário Django nativo.
- `manage.py check`, `makemigrations --check --dry-run`, `node --check` de `auto-apply.js` e do verificador de navegador, `git diff --check`: sem erros ou migrations pendentes.
- Chromium: sete telas verificadas com e sem JavaScript, acionamento por Enter e larguras 1366, 768, 390 e 360 px sem overflow ou botão cortado. A limpeza automática não recarrega o documento. Página 2 retorna à primeira; Voltar/Avançar, debounce, resposta atrasada e nova tentativa após HTTP 500 controlado passaram.

O verificador reutilizável está em `scripts/verificar-limpeza-filtros.cjs`. Requer `playwright-core` disponível ao Node (ou via `NODE_PATH`), `FILTER_TEST_BASE_URL` e `FILTER_TEST_SESSION` de um ambiente de validação isolado; `FILTER_TEST_CHROME` pode informar o executável do Chromium. As fixtures devem incluir ao menos 26 tarefas para testar a página 2 e uma conta administrativa técnica para Usuários.

Os testes desta entrega usaram `.private/task_modal_ux_20261008/clear-filters.sqlite3`, com dados fictícios e contas locais sem vínculo remoto; o banco local do projeto não foi alterado. A depuração restante é com dados reais, outros navegadores e identidades do provedor.
