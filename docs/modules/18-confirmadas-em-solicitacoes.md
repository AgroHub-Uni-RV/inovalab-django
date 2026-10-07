# Confirmadas em Solicitações

A solicitação de 07/10/2026 adiciona Confirmadas à página `/agenda/solicitacoes/` e diferencia a cor de Canceladas. Esta decisão substitui a exclusão de confirmadas definida nas entregas anteriores.

As abas passam a Todas, Pendentes, Confirmadas, Canceladas e Recusadas. O filtro `status=confirmada` consulta registros confirmados não cancelados das agendas de serviços, equipamentos e visitas. Todas inclui as quatro situações. Registros confirmados posteriormente cancelados permanecem somente em Canceladas.

Os contadores incluem Confirmadas e respeitam a pesquisa e o mês antes do filtro de situação. A navegação e a paginação preservam os filtros. Confirmadas tem coluna e ícones verdes; Canceladas passa a cinza no cabeçalho, ícones, contador e etiqueta de situação. Recusadas mantém vermelho. As cores específicas e o grid adaptável ficam em `core/static/core/ui.css`; o limite antigo de três colunas foi removido de `modulos.css`. A disposição considera a largura disponível com a sidebar expandida e em telas menores.

O acesso continua exclusivo de administradores. Os cartões confirmados oferecem o detalhe do agendamento, com as mesmas permissões existentes. Confirmar/Recusar/Cancelar no quadro continuam somente nas pendentes. Agendamentos confirmados permanecem também na agenda e no dashboard. Não há mudanças nos modelos, migrations ou integrações.

## Verificação

Testes em `agenda/tests/test_requests.py` cobrem as três categorias, separação de canceladas, contadores, busca, mês, paginação, aba ativa, situação vazia e ausência de ações de aprovação nas confirmadas. Os testes de aprovação de visitas foram atualizados para consultar a nova aba.

```powershell
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Resultado: **550 testes Django passaram**. `check`, `makemigrations --check --dry-run` e `git diff --check` passaram; não há nova migration.

A ferramenta de navegador retornou inventário vazio de apps e browsers. Renderização de templates, navegação e filtros foram verificados pelo cliente Django. Na depuração, conferir visualmente as novas cores, as cinco abas e a disposição dos quatro contadores/colunas no desktop, com sidebar expandida e no celular.
