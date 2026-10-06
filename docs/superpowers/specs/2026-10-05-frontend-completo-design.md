# Frontend completo — ampliação do desenho existente

O responsável solicitou aplicar as referências a todas as páginas, colocar o login em `/`, redirecionar a entrada para o index e fazer **Administrar contas** abrir a página **Usuários**, exclusiva de administradores. Esta solicitação reúne as entregas visuais restantes em uma etapa. Continua a decisão anterior: funcionalidades existentes, logos vazias e novos recursos de domínio em etapas próprias.

## Referência no Figma

Arquivo indicado pelo responsável: [INOVALAB](https://www.figma.com/design/6PL44EZWM82SdZ9dkcJ4S8/INOVALAB?node-id=0-1). Consultar somente para leitura, sem alterar o projeto no Figma. Desconsiderar qualquer tela que contenha um grupo chamado `Group 17`, inclusive em grupos aninhados; verificar a composição antes de selecionar cada referência.

Após reconexão, as ferramentas do plugin ficaram disponíveis, mas a consulta de metadados de `0:1` foi recusada por falta de acesso ao arquivo na conta conectada. O acesso direto pelo navegador também retornou HTTP 403. Nenhuma tela, fonte, medida ou asset foi extraído do Figma, nem houve escrita lá. O responsável autorizou seguir somente com os PNGs locais se o acesso falhasse. Como PNG não preserva os nomes dos grupos, a exclusão por `Group 17` continua pendente de conferência no arquivo original.

## Rotas e autoridade

- `/`: login atual, preservado visualmente; autenticado segue para `/index/`.
- `/index/`: Dashboard atual. `/painel/` permanece um alias funcional; `/entrar/` mantém compatibilidade para entrada. Login padrão leva ao index; `next` interno seguro continua permitido, externo rejeitado. Logout POST/CSRF retorna ao login.
- `/perfil/`: página atual da conta, com a base compartilhada.
- `/usuarios/`: cartões conforme a referência, busca, abas e contagens reais; fotos inexistentes serão substituídas por avatar neutro. Professores/funcionários/visitantes não existem no modelo: usar total, administradores, ativos e inativos.
- Preservar a autoridade técnica vigente: superusuário ativo acessa e administra usuários; staff isolado, usuário comum e administrador de negócio não recebem gestão técnica. A pergunta opcional sobre ampliação de autoridade não teve resposta; manter a política atual evita conceder privilégios técnicos por uma alteração visual.
- **Administrar contas** e menu **Usuários** apontam para a nova tela. Configuração técnica continua disponível apenas a superusuários. Esta alteração não modifica contratos de API.

## Apresentação

Reutilizar templates/CSS/SVG/JS locais em `core`, Montserrat/OFL provisória, sidebar79/283, cabeçalho74 e footer. Navegação deve existir em todas as telas internas, com indicação correta de módulo e ações conforme a política real. Mover a montagem do menu para um context processor, sem consultas ao Dashboard em outras telas.

Tarefas: quatro contadores, busca e filtro de serviço, cinco abas e quatro colunas Kanban com dados visíveis. Formulário/detalhe usam barra lavanda, conteúdo branco, metadados e histórico à direita; somente ações reais de transição.

Agenda: três contadores por categoria existente (serviço/equipamento/espaço), busca, categoria/mês e calendário mensal de domingo a sábado. Marcas são reservas reais; não inventar eventos/reuniões institucionais. Lista paginada preserva consulta detalhada. Formulário e detalhe seguem o desenho branco/lavanda com datas/horas/objeto e histórico existentes.

Materiais: três contadores reais (total, disponíveis, indisponíveis), busca/categoria/status, abas existentes e tabela com nome/categoria/quantidade/status/fonte/ações. Não criar terceiros/devoluções/exclusão física ausentes do modelo.

Banners: contadores total/ativo/agendado, abas por status, thumbnails protegidos, local/ordem e ações reais de ver/editar/excluir. Ativação continua pela edição validada, sem botão cenográfico.

Catálogo, integrações, perfil, formulários, detalhes, confirmações, histórico e páginas públicas sem imagem própria seguem os componentes, cores, tipografia e espaçamentos compartilhados. Erros de aplicação 403/404/500 terão página coerente; Django Admin técnico permanece a ferramenta de manutenção avançada, fora dos módulos visuais do produto.

Sem comentários, anexos, subtarefas, editor rico, novos participantes/CPF/fotos/cargos ou integrações de usuários AgroHub. Sem controles fictícios. Texto e contagens respeitam os seletores de autorização antes de filtrar/paginar.

## Verificação

TDD para rotas/login/permissões, filtros/contagens/paginação e limites do calendário. Suíte Django completa a cada tarefa importante. Chrome em 1920/1366/820/768/360, ambos os papéis, menu expandido/recolhido, formulários reais com CSRF/versão/validação, links/histórico/erros e nomes longos. Banco temporário separado do real; uma revisão independente final; commits em português. Aguardar depuração após esta entrega, sem iniciar novos recursos de domínio.
