# Aplicação automática dos formulários — 06/10/2026

Filtros de Agenda, Tarefas, Materiais, Banners e Usuários são aplicados ao mudar as seleções ou após 600 ms sem digitar. A busca preserva o foco e a posição do cursor após recarregar. Filtros ocultos, como status e aba, acompanham a consulta; a paginação volta à primeira página. Na revisão posterior de 06/10/2026, os botões Filtrar de Agenda, Tarefas, Materiais e Banners foram substituídos por um rótulo discreto “Filtros”. A aplicação automática depende de JavaScript.

No formulário da agenda, trocar a categoria atualiza as opções por POST, preservando os outros campos em edição. O botão Atualizar opções foi removido da tela; o script envia `atualizar=1` com um controle temporário invisível que é removido após o envio. Essa operação não valida o preenchimento obrigatório nem grava um agendamento. Salvar, excluir, cancelar, gerar credenciais e sair continuam sendo ações explícitas.

O comportamento fica em `core/static/core/auto-apply.js`: o atributo `data-auto-apply` só atua em consultas GET; `data-auto-refresh` atua exclusivamente no campo de categoria da agenda. Veja a [revisão dos filtros e das ações de banners](07-acoes-de-banners-e-filtros.md) para a validação mais recente.

## Verificação

- `python manage.py test --noinput`: 323 testes aprovados na entrega conjunta com a carga inicial do catálogo.
- `node --check core/static/core/auto-apply.js`: sem erros de sintaxe.
- Chrome com `agent-browser`, usando banco temporário: buscas das cinco páginas, seleção de categoria na agenda, preservação do status em Materiais, foco da busca após recarga e atualização das opções preservando requerente/motivo.
- Editar campos da agenda e do catálogo não grava automaticamente; recarregar a edição do espaço descarta o rascunho, preservando o registro original.
- Sidebar expandida em 1201 px: sem transbordamento da página. Agenda em 360 px: seleção automática funcionando com menu móvel fechado.

Depuração restante pelo responsável: uso prolongado das buscas com seus dados, teclados móveis e execução nos demais navegadores usados pela equipe.
