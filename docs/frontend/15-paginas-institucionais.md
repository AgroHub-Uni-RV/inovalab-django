# Páginas institucionais do InovaLab

A solicitação de 06/10/2026 autoriza transferir as páginas públicas do InovaLab do monólito para este sistema, usando as imagens de referência. O responsável aprovou início institucional em `/` e login em `/entrar/`.

| Rota | Página |
| --- | --- |
| `/` | Início institucional |
| `/sobre/` | História, missão, visão, valores e equipe |
| `/servicos/` | Apresentação institucional dos serviços e equipamentos |
| `/contato/` | Formulário, contatos e mapa estático com link ao OpenStreetMap |
| `/entrar/` | Login exclusivo pelo Accounts do AgroHub |
| `/index/` | Dashboard interno, após autenticação |

Início, Sobre, Serviços e Contato usam cabeçalho institucional também para usuários autenticados. O menu da conta oferece área interna, perfil e saída por POST/CSRF. A navbar segue Início → Sobre → Serviços → Contato; os breadcrumbs usam Início. A sidebar interna mantém sua apresentação e preferência.

As prévias de banners em `/publico/` e `/publico/sobre/` continuam disponíveis com a apresentação anterior. O item Páginas da sidebar abre agora o início institucional. Início e Sobre usam o primeiro banner publicado para seu local e período; sem banner, usam a imagem institucional original. Administração de banners, catálogo e serviços continua nos módulos existentes.

## Origem e adaptação

Foram copiados os templates `home.html`, `about.html`, `programs.html` e `contact.html`, o conteúdo editorial necessário e os assets utilizados, do repositório `unirv-monolith`. Esse repositório foi somente consultado.

`conteudo/static/conteudo/institucional/monolito.css` é o CSS compilado original, carregado exclusivamente nesta base institucional. `site.css` adapta o cabeçalho, a responsividade e a escala compartilhada de `core/ui.css`; as medidas de fonte equivalentes usam rem para permitir A-/A+. Montserrat e logos utilizam os assets existentes daqui. O JavaScript dos carrosséis e dos controles de contraste/fonte funciona sem Alpine ou dependências novas.

Agendar visita abre `/agenda/novo/?categoria=visita`, passando pelo login quando necessário e preservando o retorno. Serviços aponta ao agendamento existente. Regimento e Calendário de funcionamento continuam apontando às páginas públicas correspondentes do monólito. Não foram importados cadastros, fluxos de produção ou dependências do LabMaker.

## Calendário público de eventos

A seção da página `/` apresenta o calendário mensal e os cards do monólito. A primeira adaptação havia substituído essa seção por um botão para o Dashboard; a correção restaura o calendário, as imagens e a navegação na própria página institucional.

No monólito, os eventos pertencem a `apps.ecosystem.models.Event`. O InovaLab usa `get_home_events_context()` em `apps/inovalab/selectors.py`, que consulta o seletor compartilhado `apps/ecosystem/events.py`. O calendário compartilha o catálogo de eventos do ecossistema, sem filtro específico de InovaLab ou LabMaker. No código consultado, a consulta pública seleciona eventos ativos e aprovados.

Neste sistema, a fonte é [GET /api/v1/agrohub/eventos/](https://agrohub.unirv.edu.br/api/v1/agrohub/eventos/), com o mesmo catálogo. Não há tabela local de eventos. `core/agrohub_events.py` mantém o transporte público sem Authorization, paginação com origem fixa, limites e cache de cinco minutos, compartilhado com `/index/`. A resposta agora preserva imagem, categoria, descrição/resumo, local e link, além das datas já utilizadas internamente. URLs são validadas antes de renderizar e os textos permanecem escapados.

`conteudo/public_events.py` reproduz a seleção do monólito: até 24 eventos próximos, de hoje ou em andamento, ordenados pela data; quando há menos de dois, completa com eventos recentes. Por isso um evento de setembro pode aparecer junto de um de outubro. O calendário marca a data inicial de cada card, no horário local de Brasília. As setas mudam mês e ano; clicar em uma data filtra os cards, clicar novamente limpa o filtro. Os cards usam duas posições por página; ao mudar o mês, o filtro é limpo. Domingos e a data atual permanecem neutros.

O HTML inicial já apresenta calendário e os dois primeiros cards. A navegação é feita pelo JavaScript existente, sem Alpine. Resposta vazia e indisponibilidade da API possuem mensagens distintas e não impedem a consulta da página institucional. Sem JavaScript, a página informa a limitação de navegação.

## Contato pela API

O servidor valida nome, e-mail, telefone opcional, mensagem e consentimento. O campo oculto `website` atua como honeypot. O formulário exige CSRF e não cria outra tabela local de contato.

O envio utiliza o cliente existente e `AGROHUB_API_BASE_URL`, exclusivamente em `POST /api/v1/contact/`. O payload envia `nome`, `email`, `telefone`, `mensagem`, assunto fixo e `site_code=inovalab`. Consentimento, honeypot e credenciais não são enviados. O contrato foi conferido no código do monólito e no [schema publicado](https://agrohub.unirv.edu.br/api/v1/schema/redoc/#tag/Contact).

Somente uma resposta com ID positivo confirma o recebimento e redireciona ao formulário limpo. Erros de validação preservam os dados e mostram mensagens junto aos campos. Falhas de comunicação ou respostas sem comprovante não apresentam sucesso nem fazem reenvio automático; a página informa que não foi possível confirmar o recebimento. A confirmação de recebimento não afirma que o e-mail já foi entregue.

As quatro páginas institucionais dispensam a sincronização obrigatória da sessão remota, permitindo consulta durante indisponibilidade do AgroHub. As rotas internas continuam exigindo a validação existente. O endpoint de contato mantém o limite de requisições da API do monólito.

## Verificação

- `venv/Scripts/python.exe manage.py test --noinput`: **559 testes aprovados**, incluindo dez testes do calendário público.
- `venv/Scripts/python.exe manage.py check`: sem problemas.
- `venv/Scripts/python.exe manage.py makemigrations --check --dry-run`: sem alterações.
- `git diff --check`: sem problemas de whitespace.
- Chrome em 1896, 1200 e 360 px: navegação, imagens, ausência de transbordamento e acesso ao login.
- Fluxo no navegador com banco isolado e API HTTP simulada: formulário → POST remoto sem Authorization, com `site_code=inovalab` → confirmação e formulário limpo.
- Login pela API simulada preservou o retorno ao cadastro de visita; o formulário abriu com categoria visita, quantidade de pessoas e sidebar. O início permaneceu institucional após autenticação.
- Revisão de código verificou disponibilidade pública durante falha da API e controles de fonte; regressões de consentimento e validação remota receberam testes.
- Calendário público no Chrome em 1896, 1200 e 360 px: GET real dos eventos do AgroHub, imagens carregadas, filtros, limpeza de seleção e navegação entre meses e anos, sem transbordamento ou erros de JavaScript. Paginação foi conferida com API HTTP local simulada e três eventos próximos. A revisão da correção não encontrou problemas pendentes.

A suíte completa encontrou dois dados antigos de testes de visitas que cruzavam a meia-noite dependendo do horário de execução. Esses dados passaram a iniciar em horário fixo; nenhuma regra de agenda foi alterada.

Capturas em `docs/frontend/screenshots/institucional-*.png`, incluindo `institucional-calendario-1896.png` e `institucional-calendario-360.png`. Não houve POST no AgroHub real. Ficam para a depuração do responsável o recebimento real da mensagem/e-mail, conferência editorial dos textos e links institucionais e validação visual mais profunda. Não há migrations ou novas variáveis de ambiente nesta entrega.
