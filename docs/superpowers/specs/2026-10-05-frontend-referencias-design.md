# Frontend pelas referências — desenho e entregas

Em 05/10/2026, o responsável pediu frontend fiel às referências e confirmou **funcionalidades atuais; recursos novos em etapas próprias**. A orientação de frontend simples do MVP foi substituída para esta etapa visual. Continua valendo entregar uma parte, aguardar depuração e autorização antes da seguinte. Login de identidade não tem referência substituta e será preservado.

## Fontes examinadas

As dez imagens de `Referencias/` foram abertas integralmente. As seis anteriores continuam fonte F4; as quatro novas foram examinadas em05/10. As referências são imagens, não especificações de novas regras de negócio.

| Referência | Dimensões | Tela/elementos |
| --- | --- | --- |
| ADM - Dashboard.png | 1920×946 | Barra compacta, cabeçalho, tarefas/reservas, seis meses, rodapé |
| barra lateral.png | 440×3912 | Versões expandida/compacta, ícones, divisores, saída |
| ADM - Tarefas.png | 1920×1792 | Contadores, filtros, abas e Kanban |
| Criação de tarefa.png | 1425×1118 | Detalhe/formulário, histórico; comentários/anexos/subtarefas novos |
| ADM - Agendamentos.png | 1920×1893 | Contadores, filtros e calendário |
| Criação de agendamento - Impressão.png | 1425×1331 | Formulário; peças/múltiplas máquinas/consumo ainda ausentes |
| Criação de agendamento - salas.png | 1425×1118 | Formulário/espaços; participantes/CPF/menoridade ausentes |
| ADM - Estoque.png | 1920×1792 | Contadores, abas e tabela; terceiros/devoluções ausentes |
| Banners.png | 1920×1643 | Contadores, abas, thumbnails, ordem e ações |
| Usuarios.png | 1920×1876 | Contadores e cartões; fotos/categorias institucionais/AgroHub ausentes |

Os PNGs não identificam com certeza a fonte. Montserrat é a aproximação visual inicial, hospedada localmente com OFL; confirmar se houver assets originais. Cores medidas do Dashboard: azul `#27348b`, fundo `#f6f9fd`, cartões suaves `#f2f3ff`, verde `#76b82a`, texto `#535353`, branco. A referência é desktop1920; responsividade será adaptação com os mesmos elementos.

## Entrega 1 — base visual e Dashboard

Django templates/CSS/SVG/JS pequeno, sem novo framework ou alteração dos contratos REST. Componentes em `core`: layout, sidebar compacta79px/expandida283px, cabeçalho74px, perfil/logout e rodapé, ícones; painel em `/painel/`. `/`/login continuam como identidade, com link para Dashboard. Não aplicar o novo layout aos conteúdos das outras telas antes das suas entregas.

Dashboard de três painéis segue geometria/card/tab/cores da imagem. Tarefas reais usam `visible_tasks`, três abas: pendentes(demanda), em andamento(criação/avaliação), concluídas. Administrador vê todas; usuário somente próprias. Reservas reais só para administradores, abas semana/próximos/concluídos. Consulta limitada10por painel; links levam às listas completas. Botões de criação exclusivamente administrativos.

Calendário seis meses a partir do mês atual, domingos primeiro; marcar domingos, hoje e dias com reservas autorizadas. Não inventar feriados/recessos/eventos institucionais. Legenda corresponde aos dados existentes. Para comum, calendário não revela reservas, e painel administrativo não aparece.

Menu só oferece rotas existentes conforme papéis: Dashboard, Agenda, Materiais, Tarefas, Usuários(admin técnico), Banners, Páginas públicas, Estrutura(catálogo), Integrações, Perfil. Relatórios e notificações interativas aguardam módulo próprio. Ícone de sino decorativo, sem contador/informação inventada. Perfil abre menu acessível; logout POST/CSRF. Títulos/IDs/fotos da referência são exemplos, substituídos pelos dados reais; avatar inicial se não há foto.

Logotipos presentes nos PNGs podem ser exibidos por recorte visual CSS do arquivo original sem alterar seus bytes; as fontes PNG usadas como asset devem ser copiadas/versionadas, pois Referencias é ignorada pelo Git. Preferir assets originais se informados. Não garantir igualdade pixel a pixel de fonte/ícones nem conteúdo fictício; comparar desktop contra a referência e registrar diferenças reais.

Verificar filtros sem ampliar acesso, HTML escapado, no-store, logout/CSRF, estados vazios, texto150caracteres, 1920/1366/360px, teclado, colapso/menu e fontes/imagens carregadas; suíte Django completa e revisão independente.

## Sequência após depuração

2. Tarefas: painel/contadores/abas/filtros, formulário/detalhe e histórico com dados atuais.
3. Agenda: calendário e formulários, um alvo por reserva; capacidade apenas descritiva.
4. Materiais e catálogo: tabela/cadastros usando campos existentes, sem empréstimos.
5. Banners: cards/abas/previews/ações/ordem com serviços e versão existentes.
6. Usuários/perfil: respeitar autoridade técnica, dados locais; categorias/fotos/AgroHub só com requisitos próprios.

Compartilhar componentes durante essas etapas. Comentários, anexos, subtarefas, editor rico, novos participantes/documentos, alocações compostas, consumo/estoque, notificações, relatórios e calendário institucional permanecem etapas de domínio separadas, conforme resposta do responsável.
