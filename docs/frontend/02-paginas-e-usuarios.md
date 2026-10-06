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

309 testes passaram, incluindo 27 novos nesta entrega: rotas/login, autorização e busca de usuários, filtros/contadores/paginação/escape, calendário e páginas de erro. `check`, verificação de migrações, `pip check` e `git diff --check` passaram. Sem novos modelos, migrações, dependências ou contratos de API.

Chrome: 45 páginas administrativas/públicas renderizaram com sucesso; 122 combinações de página/largura/menu como administrador e 33 como usuário comum passaram, com nomes longos e sem transbordamento externo ou imagens quebradas. Larguras: 1920/1366/820/768/360 px; tabelas e calendário permitem rolagem dentro de sua região acessível. Também foram verificados: entrada padrão no index, bloqueios administrativos, cadastro de material com `1,125` armazenado como `1.125`, início/envio de tarefa e histórico, logout, gaveta móvel/Escape/retorno de foco. Não houve erros JavaScript da aplicação. Os dados nas capturas são fixtures de banco e mídia temporários próprios; seus registros reais não foram alterados.

Uma revisão final independente identificou dois problemas importantes, corrigidos numa única passada com casos RED→GREEN e suíte309/309: retorno `next` destinado à própria entrada agora segue ao index sem erro/loop, preservando destinos internos válidos e a validação do Django para destinos externos; reservas de vários dias exibem o intervalo completo em cada dia ocupado, preservando o término à meia-noite. Ambos também foram conferidos no Chrome após a correção. Não houve segunda revisão.

Ajuste menor identificado nesta entrega: rótulos longos dos contadores podiam quebrar dentro da palavra quando o cartão tinha pouca largura. Essa pendência foi tratada na [padronização visual posterior](03-padroes-visuais.md), com reorganização responsiva dos cartões e verificação do espaço dos rótulos.

Capturas: [Usuários](screenshots/usuarios-1920.png), [Materiais](screenshots/materiais-1920.png), [Banners](screenshots/banners-1920.png), [Agenda](screenshots/agenda-1920.png), [Detalhe da tarefa](screenshots/tarefa-detalhe-1920.png) e [Formulário em 360 px](screenshots/material-form-360.png).

## Decisões da execução

- Reunir as telas restantes nesta entrega visual atende à solicitação de todas as páginas, sem abrir novos módulos de domínio. Custo: um conjunto maior de telas para depurar de uma vez.
- Usar o checkout local da IDE e registro manual em PowerShell preservou a execução existente, sem alterar framework ou dependências. Custo: registros manuais e fonte original ainda não confirmada; Montserrat e logos vazias continuam como decidido.
- A verificação exata do Figma e da exclusão por `Group 17` não foi declarada: o responsável autorizou os PNGs após a recusa de acesso. Custo: diferenças visuais e composição das telas excluídas continuam sem conferência no arquivo original.
- A manutenção técnica de contas fica no Django Admin, explicitamente fora das telas visuais do produto. Custo: a edição técnica mantém uma apresentação diferente.
- README, rotas e resultados ainda estavam pendentes durante a revisão; foram concluídos nesta tarefa documental. Custo: alterações posteriores exigem manter esses guias sincronizados.

Entrega local na branch `feat/frontend-completo`, aguardando depuração. A orientação de entregar por etapas permanece para trabalhos futuros.

Navegador e servidor temporário foram encerrados. A aprovação automática da ferramenta rejeitou a remoção de `.superpowers/sdd/2026-10-05-frontend-completo/`, com o motivo `blocked by policy`. A pasta de banco, mídia e registros da verificação permanece ignorada pelo Git.

Para aprofundar depois da entrega:

1. Entrar com superusuário, administrador do laboratório, staff e usuário comum; conferir rotas, menus, busca e contadores de cada papel.
2. Conferir cartões com nomes reais, categorias livres longas, estados vazios e paginação com mais de 25 registros; seguir links de detalhes e manutenção técnica de contas.
3. Executar fluxo completo de tarefa e reserva, com dois navegadores editando versões diferentes; conferir erro de conflito e histórico.
4. Conferir calendário na virada de mês/ano, reservas atravessando dias, término à meia-noite e mais de três reservas no mesmo dia.
5. Enviar banners WebP reais com proporções variadas; conferir ativo/inativo/agendado, texto alternativo, publicação e exclusão.
6. Depurar login/aliases/`next`, gaveta móvel pelo teclado, formulários inválidos, mensagens de confirmação e retorno ao login após sair.
