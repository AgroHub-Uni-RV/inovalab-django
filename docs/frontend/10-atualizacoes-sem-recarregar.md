# Filtros e opções sem recarregar a página — 06/10/2026

Os filtros de Agenda, Tarefas, Materiais, Banners e Usuários agora atualizam o conteúdo por requisição assíncrona. A página permanece aberta: sidebar, cabeçalho, fonte e demais elementos da estrutura não são recriados. A busca mantém a espera de 600 ms após digitar; selects e mês aplicam a consulta ao mudar.

A consulta atualiza listas, cartões, contadores, calendário e links conforme a resposta do servidor. O campo de busca mantém seu elemento, foco e posição do cursor. A rolagem é preservada dentro dos limites disponíveis após a mudança do conteúdo. Respostas de consultas canceladas não sobrescrevem o filtro mais recente.

Filtros GET atualizam a URL para permitir copiar a consulta e usar Voltar/Avançar. Abas e paginação das cinco listas também usam atualização assíncrona. Texto digitado antes do fim da espera não é descartado ao clicar nesses links. Uma consulta nova começa na primeira página. Links de detalhe, criação e navegação geral continuam com navegação normal.

## Categoria do agendamento

Mudar a categoria envia o POST existente com CSRF e `atualizar=1`. Só os campos dependentes — objeto, equipamentos e material — são substituídos. Requerente, motivo, datas e versão mantêm seus elementos e valores, inclusive alterações digitadas enquanto a resposta está chegando. Os cartões de espaços e os campos condicionais de material continuam funcionando após a atualização.

Os campos dependentes e Salvar aguardam a atualização; os campos comuns permanecem editáveis. A troca não valida os campos obrigatórios nem grava agendamento. Salvar continua sendo um envio explícito, com as validações e o controle de versão anteriores.

## Retorno e falhas

O estado de atualização usa `aria-busy` e uma mensagem com `role=status`. Falhas preservam o conteúdo atual e oferecem Tentar novamente. Na troca de categoria, uma falha recupera a categoria correspondente aos campos que permanecem na tela, preservando o rascunho. Uma nova digitação remove a tentativa anterior e agenda a consulta com os valores mais recentes.

Não foram criados endpoints ou dependências. O servidor continua respondendo com o HTML das views atuais; o navegador aplica a parte necessária. Sessão, CSRF, permissões e respostas de erro continuam sendo controlados pelo Django. Scripts recebidos não são executados durante a atualização. Não há mudanças de banco ou migrações nesta entrega.

## Validação

```powershell
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
node --check core/static/core/auto-apply.js
git diff --check
```

355 testes Django aprovados; configuração, migrações, sintaxe JavaScript e diff sem pendências. A lógica no navegador foi conferida no Chrome com banco de teste em memória:

- Busca nas cinco páginas, com a mesma instância de página e cabeçalho após a resposta; foco, cursor e rolagem preservados.
- Categoria e mês na Agenda, atualizando contagem, calendário e tabela juntos.
- Abas, paginação, reinício da página ao mudar a consulta e Voltar/Avançar.
- Respostas atrasadas de busca e categoria ignoradas após uma escolha mais recente.
- Falha de conexão simulada, preservação do conteúdo/rascunho e nova tentativa bem-sucedida.
- Troca entre Serviço, Espaço e Equipamento, preservando texto digitado durante a espera, sem gravação implícita; Salvar desabilitado somente durante a troca.
- Material condicional após inserir novamente os campos de serviço; salvamento explícito de equipamento concluído.
- Desktop de 1201 px com sidebar expandida e celular de 360 px, sem transbordamento da página e sem erros JavaScript.

Depuração restante pelo responsável: conferir o fluxo com volume e dados reais, leitores de tela, outros navegadores e expiração de sessão durante uma consulta. Ao testar uma tela que já estava aberta antes desta alteração, reabra a tela para carregar o script atualizado.
