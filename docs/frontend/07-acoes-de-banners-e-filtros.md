# Ações de banners e filtros — 06/10/2026

A coluna Ações da listagem de banners oferece um controle com a aparência da referência: chave verde e texto Desativar para ativos/agendados; chave cinza e texto Ativar para inativos. O controle pode ser acionado por clique ou teclado e identifica o banner no nome acessível. A alteração é enviada por POST, com CSRF e versão obrigatória, e mantém imagem, título, local, ordem e demais dados de conteúdo. Administradores ativos continuam sendo os únicos autorizados.

Desativar interrompe a publicação sem excluir o banner. Para um agendado, também limpa início/fim, seguindo a regra existente que não permite período em banners inativos. Ativar publica imediatamente como ativo; para configurar um novo período, use Editar. A ação retorna à lista preservando busca e aba, mas reinicia a paginação. Uma versão antiga retorna 409 e um link para atualizar a listagem; dados inválidos retornam 400 sem alterações.

Os quatro botões Filtrar de Agenda, Tarefas, Materiais e Banners foram substituídos pelo rótulo cinza claro Filtros, com estilo compartilhado. O botão Atualizar opções saiu do formulário da agenda; mudar a categoria continua atualizando o objeto automaticamente, sem salvar, validar os campos obrigatórios ou perder os outros campos em edição. Os botões de salvar permanecem explícitos.

## Validação

```powershell
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
node --check core/static/core/auto-apply.js
git diff --check
```

329 testes Django aprovados. As verificações de configuração, migrações, sintaxe JavaScript e diff passaram. Os seis novos testes cobrem desativação/reativação e publicação, desativação de agendados, permissões, POST obrigatório, CSRF, dados inválidos/duplicados, versões antigas e registros excluídos/inexistentes.

Chrome com banco de teste em memória: desativação e reativação na coluna Ações; desativação de agendado; busca sem botão; rótulo Filtros sem botão de envio nas quatro páginas; troca de categoria na agenda com requerente/motivo preservados, nenhuma validação obrigatória e apenas Salvar agendamento disponível. Layout verificado em 1366 px, 1201 px com sidebar expandida e 360 px, com rolagem interna da tabela e sem transbordamento da página. Nenhum erro de JavaScript registrado.

Depuração restante pelo responsável: comparar o controle com a referência usando banners e títulos reais e conferir os demais navegadores e dispositivos usados pela equipe. Ao testar desativação de agendados, conferir a limpeza do período e a necessidade de usar Editar para reagendar.
