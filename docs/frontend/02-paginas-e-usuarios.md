# Frontend dos módulos e página Usuários

Entrega visual iniciada em 05/10/2026, na branch `feat/frontend-completo`. Aplica os PNGs de `Referencias/` às páginas existentes: Usuários, Tarefas, Agenda, Materiais, Banners, Catálogo, Integrações, perfil, formulários, detalhes, confirmações, históricos e páginas públicas. Os sete módulos de domínio mantêm seus contratos de API, modelos e regras de escrita.

## Entrada e contas

- `/` apresenta o login existente. Entrada padrão e acesso à raiz autenticado seguem para `/index/`. `/entrar/` continua como alias de login e `/painel/` como alias do Dashboard. Um `next` local válido permanece permitido; endereços externos são rejeitados.
- `/perfil/` conserva o conteúdo da conta, dentro da navegação compartilhada. **Administrar contas** e o menu **Usuários** abrem `/usuarios/`.
- `/usuarios/` é exclusiva de superusuários ativos, preservando a política de administração técnica já existente. Staff isolado e administrador do laboratório sem superusuário recebem 403. **Configurar Usuários** e os nomes dos cartões levam à manutenção autorizada no Django Admin, que continua sendo a ferramenta técnica avançada.
- A tela usa cartões, busca por nome/usuário/e-mail, abas e paginação de 15 contas. Total/administradores/ativos/inativos são dados reais. Professores, cargos, fotos e usuários AgroHub não são campos do modelo atual: seus equivalentes ilustrativos não foram inventados. Avatares são neutros.
- Logout permanece POST com CSRF; contas desativadas perdem o acesso.

## Telas e ações

Tarefas têm quatro contadores, busca, filtro de serviço, abas e Kanban paginado. Filtros e contadores respeitam a visibilidade: o responsável vê suas próprias tarefas, administradores veem todas as tarefas permitidas. Transições continuam na página de detalhes, com versão e CSRF, e o histórico real aparece à direita. Não há comentários, anexos ou subtarefas novos.

Agenda usa calendário mensal de domingo a sábado, busca, categoria/mês e contadores por serviço/equipamento/espaço. Mostra até três reservas por dia, com link para a lista; a lista é paginada em 25 registros. A contagem diária considera toda a consulta, incluindo reservas fora da página da tabela, intervalos de múltiplos dias e exclusão do dia seguinte quando o término é exatamente à meia-noite. Reservas canceladas não aparecem. Não foram criados eventos, reuniões institucionais ou feriados a partir dos exemplos visuais.

Materiais têm contadores, busca por nome/categoria/fonte, seleção de categoria e abas disponível/indisponível. A tabela mostra nome, categoria, quantidade/unidade, status, fonte e ações autorizadas. Não há exclusão, fotos, devolução, terceiros ou movimentações de estoque no domínio atual.

Banners têm contadores, busca, abas por status, imagens pela rota protegida e ações de visualizar/editar/excluir. Ativação, agendamento e ordem continuam pela edição validada. A tela não apresenta um toggle ou arraste sem operação correspondente. Páginas públicas mostram somente publicações elegíveis; nenhum URL direto de `media/` foi acrescentado.

Catálogo, Integrações e as demais telas usam as mesmas cores, tipografia, sidebar, tabelas, campos, barras lavanda e ações básicas. Os formulários preservam erros, campos ocultos, versão e CSRF. Páginas 403/404/500 em `DEBUG=False` têm mensagens próprias sem detalhes técnicos; o modo de desenvolvimento mantém o comportamento de diagnóstico do Django.

## Referências e pendências visuais

Tentativa de consulta somente de leitura ao [INOVALAB no Figma](https://www.figma.com/design/6PL44EZWM82SdZ9dkcJ4S8/INOVALAB?node-id=0-1): o plugin recusou acesso ao arquivo na conta conectada. Seguir com as imagens locais foi autorizado pelo responsável. Nenhum conteúdo foi extraído ou alterado no Figma. A regra de ignorar telas com `Group 17` permanece para uma futura consulta: PNGs não revelam os nomes das camadas.

Logos continuam **vazias** por decisão do responsável, inclusive após aparecer `Referencias/logo.png`. **Tarefa futura do responsável: incluir as logos oficiais** nos espaços da sidebar/cabeçalho/rodapé. Montserrat/OFL local e os SVGs existentes são aproximações; não foi possível confirmar a fonte ou extrair os ícones originais do Figma. Por isso esta entrega não declara fidelidade absoluta de todos os pixels. Não há dependência de CDN ou da pasta `Referencias/` em execução.

## Verificação e depuração

Comandos da entrega em PowerShell:

```powershell
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\venv\Scripts\python.exe -m pip check
git diff --check
```

Os resultados finais, capturas e revisão serão registrados ao encerrar a verificação. O navegador utiliza banco SQLite e mídia temporários próprios; nenhum registro do banco de trabalho é necessário para essas verificações.

Para aprofundar depois da entrega:

1. Entrar com superusuário, administrador do laboratório, staff e usuário comum; conferir rotas, menus, busca e contadores de cada papel.
2. Conferir cartões com nomes reais, categorias livres longas, estados vazios e paginação com mais de 25 registros; seguir links de detalhes e manutenção técnica de contas.
3. Executar fluxo completo de tarefa e reserva, com dois navegadores editando versões diferentes; conferir erro de conflito e histórico.
4. Conferir calendário na virada de mês/ano, reservas atravessando dias, término à meia-noite e mais de três reservas no mesmo dia.
5. Enviar banners WebP reais com proporções variadas; conferir ativo/inativo/agendado, texto alternativo, publicação e exclusão.
6. Depurar login/aliases/`next`, gaveta móvel pelo teclado, formulários inválidos, mensagens de confirmação e retorno ao login após sair.
