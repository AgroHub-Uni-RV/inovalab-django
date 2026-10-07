# Criação de agendamentos em modal

A solicitação de 07/10/2026 reúne a criação em um único modal, reutilizado para escolher Visita, Equipamento ou Serviços, preencher o formulário, corrigir erros e confirmar o registro. A página de origem e sua URL permanecem abertas durante o fluxo.

## Interface

Os acessos de criação da agenda, dashboard, Meus agendamentos, início institucional (Agendar visita) e Serviços (Agendar) abrem o mesmo componente `dialog`. Selecionar uma categoria ou usar Alterar tipo de agendamento/Voltar atualiza seu conteúdo. Dados já preenchidos ficam em memória por categoria durante essa abertura; fechar descarta os rascunhos.

Os formulários existentes mantêm campos, escolha de equipamentos, material próprio/do laboratório, validações e autorizações. Campos de material são mostrados e habilitados conforme a opção selecionada. Erros retornam ao mesmo modal com os valores preenchidos. Após salvar, ele mostra confirmação, Ver detalhes e Concluir; páginas internas atualizam a listagem/calendário de origem sem recarregar a página inteira.

O modal utiliza fundo sobreposto, rolagem própria, foco contido e fechamento por botão, Escape ou clique no fundo. O foco retorna ao acesso de origem. A sidebar e sua preferência permanecem preservadas. Na gravação, o fechamento e o novo envio ficam bloqueados até a resposta. Se a conexão falhar sem confirmar o resultado de um POST, não há reenvio automático: a interface orienta consultar Meus agendamentos. Falhas de carregamento permitem tentar novamente.

Os três cards permanecem quadrados e se adaptam à largura do modal, incluindo celular. Tipografia, campos, botões e espaçamentos usam os padrões existentes; as regras de apresentação ficam em `core/static/core/ui.css`. As páginas institucionais carregam os componentes de módulos para contas com acesso interno, permitindo usar os mesmos formulários.

O atalho **Agendamento** da página inicial continua abrindo `/agenda/meus/`, conforme a solicitação anterior. Somente acessos de criação abrem o modal. Usuários anônimos continuam sendo encaminhados ao login com seu destino; acesso direto a uma URL de criação abre o formulário em modal quando há JavaScript e retorna a Meus agendamentos ao fechar. Sem suporte/JavaScript, as páginas e POSTs tradicionais continuam disponíveis. A edição não foi convertida em modal.

## Respostas e persistência

As mesmas views de criação recebem `X-Booking-Modal: 1`. GET e validações inválidas usam os mesmos templates, com uma base de fragmento, sem incluir sidebar ou uma segunda instância do modal. As respostas são `no-store` e variam pelo cabeçalho. Os formulários têm action explícito para enviar ao endpoint correto mesmo quando inseridos em outra página.

POST válido retorna HTTP 201 com `created`, `message` e `detail_url`, exibindo o sucesso sem redirecionar. Sem o cabeçalho, o comportamento de mensagens/redirecionamento continua funcionando. Conflitos retornam HTTP 409 com o formulário. CSRF, sincronização de Accounts, papéis, autoria, histórico e gravação transacional seguem as regras existentes. Administradores criam confirmados; equipe cria pendentes. Não há alterações em modelos, migrations, API interna de agendamentos ou integrações de Accounts/eventos.

## Verificação

`agenda/tests/test_modal.py` cobre fragmentos das etapas sem gravação, três categorias, erros, confirmação sem redirecionamento, pendentes, conflitos, titularidade, CSRF, acesso anônimo/externo, uma única instância do modal e preservação do fluxo de edição.

Comandos:

```powershell
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
node --check agenda/static/agenda/booking-modal.js
git diff --check
```

Resultado: **556 testes Django passaram**, incluindo seis testes do contrato do modal. `check`, verificação de migrations, sintaxe JavaScript e `git diff --check` passaram. Não há nova migration nem dependência de execução.

A verificação no Chromium local utilizou banco SQLite isolado em `.private/`, usuários fictícios e eventos simulados, sem modificar registros reais. Foram verificados criação/sucesso das três categorias, erros e preservação de dados, atualização da lista, URL constante, campos de material, retorno à seleção, celular em 360 px, desktop em 1366 px, entrada institucional, solicitação pendente da equipe, foco/Tab/Escape, retorno do foco, sidebar expandida, falhas de GET/POST, bloqueio de fechamento durante envio e redirecionamento de anônimo ao login. Capturas privadas foram revisadas; ajustes no espaço dos cards do celular e no ciclo de foco foram validados novamente. O servidor temporário foi encerrado após a verificação.

Na depuração, conferir com dados reais, contas sincronizadas e outros navegadores/dispositivos. As integrações reais não foram chamadas na verificação visual.

## Correção do modal após o login

A solicitação seguinte de 07/10/2026 corrige o formulário aberto automaticamente depois de autenticar pelo banner Agendar visita. O script movia somente a ficha para o diálogo, perdendo o ancestral `module-page`: campos ficavam sem bordas e o botão de confirmar perdia o fundo. A ficha agora é movida dentro do mesmo contêiner `module-page detail-page` usado pelos fragmentos carregados por AJAX.

O conteúdo institucional também respeita o bloco `content_class` já usado pelas páginas da agenda, e os módulos institucionais recebem as cores compartilhadas. Assim, os formulários completos mantêm a apresentação quando JavaScript está desativado. O retorno de login e a abertura automática da visita permanecem iguais; a ficha é movida sem recarregar ou substituir seus dados e token CSRF.

No Chromium, o fluxo real de login foi testado contra o servidor controlado de Accounts, com banco isolado, para papéis de usuário comum, equipe e administrador. Foram conferidos contêiner, bordas/cores/tipografia, ausência de transbordamento, equivalência entre abertura automática e pelo banner, desktop de 1366 px, celular de 360 px, rascunhos na troca de categoria, erros, salvamento, fechamento e alternativa sem JavaScript.

Resultado desta correção: **569 testes Django aprovados**. Configuração, ausência de migrations, sintaxe JavaScript e `git diff --check` sem problemas. A criação/cancelamento pessoal das três categorias e o banner responsivo também foram conferidos novamente no navegador. Depuração com o provedor real e outros navegadores permanece com o responsável.
