# InovaLab

Sistema Django para demandas do laboratório, tarefas, agenda, materiais e banners, com frontend básico e API para futuras integrações.

O deploy no projeto **inovalab-test** usa o preset Django da Vercel e executa
as migrações do Neon no build de cada push. O banco Neon dedicado e as
variáveis de Production/Preview já estão configurados. Consulte o [guia de deploy,
segurança, ambientes e limitações de uploads](docs/deploy/vercel-neon.md).

Os sete módulos planejados estão implementados localmente: **Identidade e acesso**, **Catálogo**, **Tarefas**, **Agenda interna**, **Recebimento de reservas externas**, **Materiais** e **Conteúdo/Banners**. Banners oferece gestão administrativa, upload WebP, publicação por local/período e consulta pública por páginas/API. A conexão a um AgroHub real ainda depende do consumidor e ambiente. Aguardar depuração desta entrega antes de novas etapas.

## Documentação

| Arquivo | Conteúdo |
| --- | --- |
| [01 — Escopo e requisitos](01-InovaLab-Escopo-e-Requisitos.md) | Fontes, requisitos, permissões, perguntas e decisões |
| [02 — Casos de uso](02-InovaLab-Casos-de-Uso.md) | Fluxos internos e integração AgroHub |
| [03 — Cenários e rastreabilidade](03-InovaLab-Cenarios-e-Rastreabilidade.md) | Critérios para testes futuros e vínculo com requisitos |
| [04 — Diretrizes Django](04-InovaLab-Diretrizes-Django.md) | Modelagem, autorização, integridade e concorrência |
| [05 — Revisão e arquitetura](05-InovaLab-Revisao-e-Arquitetura.md) | Telas, diagnóstico, alternativas, API proposta e etapas |
| [06 — Conferência do PDF](06-InovaLab-Conferencia-do-PDF.md) | Comparação por página, cobertura dos requisitos e distinção entre PDF, decisões e propostas |
| [Módulo 1 — Identidade e acesso](docs/modules/01-identidade-e-acesso.md) | Instalação, contas, contrato da API e roteiro para depuração |
| [Módulo 2 — Catálogo](docs/modules/02-catalogo.md) | Cadastros, carga inicial, endpoints e testes para aprofundar |
| [Módulo 3 — Tarefas](docs/modules/03-tarefas.md) | Quadro, permissões, fluxo de avaliação, histórico, API e depuração |
| [Módulo 4 — Agenda](docs/modules/04-agenda.md) | Calendário, exclusividade, cancelamento, concorrência, API e depuração |
| [Módulo 5 — Integrações](docs/modules/05-integracoes.md) | Credenciais, recebimento, idempotência, contrato e depuração |
| [Módulo 6 — Materiais](docs/modules/06-materiais.md) | Cadastro, quantidade decimal, versão, API e depuração |
| [Módulo 7 — Conteúdo](docs/modules/07-conteudo.md) | Banners WebP, publicação, imagem protegida, API e depuração |
| [Frontend — Base e Dashboard](docs/frontend/01-base-e-dashboard.md) | Primeira entrega visual pelas referências e roteiro de depuração |
| [Frontend — Páginas e Usuários](docs/frontend/02-paginas-e-usuarios.md) | Telas dos módulos, login raiz/index, contas protegidas, capturas e roteiro de depuração |

Leia as classificações **C** (confirmado pela fonte), **D** (derivado) e **P** (proposta) no arquivo 01. Propostas não são decisões aprovadas. As seis telas e as três páginas de `Referencias/InovaLab - Modelagem.pdf` foram examinadas. A pasta permanece ignorada pelo Git e pode faltar em outro clone.

## Decisões confirmadas em 01–02/10/2026

- Django com frontend básico e endpoints para futuras integrações.
- Somente administradores aprovam, recusam e reabrem tarefas; o responsável executa e envia para avaliação.
- Cada reserva do MVP tem um único serviço, equipamento ou espaço, sem bloquear automaticamente recursos associados.
- Uma reserva por objeto/horário nas três categorias; exclusividade dos serviços confirmada em 02/10/2026.
- Preparar primeiro a API de recebimento no InovaLab, com credencial própria e proteção contra duplicação, conforme resposta em 02/10/2026.
- Contas internas cadastradas pelo administrador técnico, com login por usuário e senha.
- Administradores do laboratório mantêm o catálogo; todos os usuários internos ativos consultam.
- Materiais: cadastro simples mantido pelos administradores, consulta interna ativa, quantidade não negativa até 3 casas/unidade informada, categoria/fonte livres, status disponível/indisponível; sem movimentações.
- Em 05/10/2026, iniciar frontend pelas imagens de referência, em entregas fracionadas, com funcionalidades atuais e áreas das logos vazias para inclusão futura pelo responsável. Login e página de identidade preservados. Testes automatizados e básicos no navegador executados; testes profundos pelo responsável.

O sistema usa Django, templates e Django REST Framework, com política de papéis compartilhada entre interface e API. SQLite atende à execução local, com escrita/bloqueio do alvo antes de consultar conflitos da agenda. `DATABASE_URL` seleciona PostgreSQL; a Vercel exige banco Neon configurado e não utiliza SQLite.

## Estado do ambiente local

Em 05/10/2026, a entrega foi verificada com Python 3.14.3, Django 6.1.1, DRF 3.18.1 e Pillow 12.3.0 para validar WebP. As dependências diretas estão em `requirements.txt`. A colisão do app local `auth` foi corrigida com `accounts`; a autenticação nativa do Django foi preservada.

Execução em PowerShell (crie `venv` com `python -m venv venv` se necessário):

```powershell
& .\venv\Scripts\python.exe -m pip install -r requirements.txt
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py createsuperuser
& .\venv\Scripts\python.exe manage.py runserver
```

Abra [o login local](http://127.0.0.1:8000/), entre com o superusuário e use **Administrar contas** no perfil para abrir `/usuarios/`. **Configurar usuários** abre a manutenção técnica no Django Admin. Não há credenciais padrão. O grupo `Administradores` identifica o papel de negócio e não concede gestão técnica de contas.

Verificação automatizada:

```powershell
& .\venv\Scripts\python.exe manage.py test
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\venv\Scripts\python.exe -m pip check
```

309 testes passaram na entrega do frontend de 05/10/2026 (27 acrescentados, além dos 282 anteriores); checks, migrações e dependências sem pendências. Chrome: 45 rotas renderizadas, 155 combinações de layout/papel/menu, cadastro de material, execução/envio de tarefa, restrições de acesso e teclado. A revisão final teve duas correções, verificadas por testes de regressão: retorno circular ao login e intervalo de reservas de vários dias. Consulte os guias dos módulos para contratos, limitações e roteiros, inclusive os ajustes menores conhecidos de banners e horário de verão histórico da agenda. A configuração de deploy de 06/10/2026 passa a carregar `.env.local` e `.env` automaticamente apenas em execução local. As variáveis do processo prevalecem.

O login fica em `/` e redireciona por padrão para `/index/`. `/painel/` e `/entrar/` permanecem como aliases; o perfil fica em `/perfil/`. **Administrar contas** abre a página **Usuários**, protegida para superusuários ativos. Todas as telas dos módulos usam a apresentação baseada nos PNGs locais; o Figma recusou acesso ao arquivo na conta conectada e o responsável autorizou esse fallback. Logos vazias conforme solicitado. [Guia, capturas, limitações e depuração do frontend](docs/frontend/02-paginas-e-usuarios.md).

Após entrar, use **Catálogo** ou abra `/catalogo/servicos/`. A migração cria os onze serviços do PDF; `manage.py carregar_servicos_iniciais` repete a carga preservando alterações. APIs disponíveis: `/api/v1/servicos/`, `/api/v1/equipamentos/`, `/api/v1/espacos/`, com detalhes por ID. Indisponibilização preserva registros; exclusão física não é oferecida.

Use **Tarefas** ou abra `/tarefas/`. Administradores criam demandas e avaliam entregas; cada responsável vê somente suas tarefas e pode iniciar/enviar. `/api/v1/tarefas/` oferece consulta e administração; `/{id}/transicoes/` controla o fluxo e `/{id}/historico/` registra alterações. Escritas em tarefas existentes exigem `versao`; exclusão é lógica. Datas e demais escolhas do MVP estão no guia do módulo 3.

Administradores usam **Agenda** ou `/agenda/`. API: `/api/v1/agendamentos/`, detalhes e `/{id}/historico/`. Escritas existentes exigem `versao`; sobreposição/versão antiga retornam 409. Cancelamento preserva o histórico e libera o horário. O [guia da agenda](docs/modules/04-agenda.md) registra regras provisórias e a limitação conhecida em intervalos históricos na transição de horário de verão de 2019.

Administradores usam **Integrações** ou `/integracoes/` para cadastrar integradores, gerar/renovar/revogar credenciais e consultar pedidos. API externa: `POST /api/v1/integracoes/agendamentos/` e `GET /api/v1/integracoes/catalogo/?categoria=servico`. Autenticação por credencial Bearer própria; não usa sessão interna nem concede acesso à agenda privada. [Contrato do módulo5](docs/modules/05-integracoes.md).

Use **Materiais** ou `/materiais/` para consultar; administradores cadastram/corrigem. API interna por sessão/CSRF: `/api/v1/materiais/`, com detalhes por ID e versão obrigatória em PUT/PATCH. Quantidade decimal é devolvida como string com 3 casas; versão antiga retorna 409. [Contrato e roteiro](docs/modules/06-materiais.md).

Administradores usam **Banners** ou `/banners/`. API interna por sessão/CSRF: `/api/v1/banners/`, versão em edição/exclusão e upload multipart WebP. Visitantes consultam `/publico/`, `/publico/sobre/` ou `/api/v1/publico/banners/?local=home|sobre`; imagens passam por `/banners/{id}/imagem/`, sem acesso direto ao diretório `media/`. [Contrato, escolhas provisórias e retenção](docs/modules/07-conteudo.md). Administração exclusiva, leitura pública, vários banners ordenados e período obrigatório são escolhas iniciais para Q10/Q12/Q15, ainda sujeitas à validação do responsável.

Os [padrões visuais compartilhados](docs/frontend/03-padroes-visuais.md) centralizam Montserrat, tipografia, margens, gaps e arredondamentos em `core/static/core/ui.css`. Banners usa o mesmo alinhamento dos módulos; filtros, contadores e componentes equivalentes seguem a mesma escala. A revisão do Dashboard incluiu 1201 px com menu expandido. O guia registra comandos, resultados, capturas e a verificação reutilizável no navegador.

## Processo

A entrega de [usuário e horários do agendamento](docs/frontend/12-usuario-e-horarios-do-agendamento.md) remove o requerente livre e usa o usuário que cadastrou a reserva. O formulário escolhe um dia, hora de início e hora de término; períodos antigos e histórico são preservados. A API interna não aceita mais `requerente`, enquanto o contrato externo de integrações permanece. Execute `python manage.py migrate` ao atualizar outro ambiente; a migração local já foi aplicada. Validação: 424 testes Django aprovados e verificações básicas no Chrome.

A entrega de [atualizações sem recarregar](docs/frontend/10-atualizacoes-sem-recarregar.md) aplica filtros, abas, paginação e troca de categoria da agenda por requisições assíncronas, preservando foco e rascunhos. Foram aprovados 355 testes Django e verificações no Chrome em desktop e celular, incluindo respostas atrasadas e falha de conexão. Sem migrações nesta entrega.

A entrega de [seleção de espaços e material](docs/frontend/09-selecao-de-espacos-e-material.md) acrescenta cartões de espaços conforme a referência e um select para identificar o material utilizado nos serviços. Foram aprovados 355 testes Django e verificações no Chrome em desktop e celular. A migração local já foi aplicada; execute `python manage.py migrate` ao atualizar outro ambiente.

A entrega de [agendamentos por categoria](docs/frontend/08-agendamento-por-categoria.md) acrescenta seleção opcional de máquinas e material próprio/gasto em gramas ao formulário de serviço, além da foto/nome do criador e do destaque de categoria no detalhe. Foram aprovados 345 testes Django e verificações básicas no Chrome. Execute `python manage.py migrate` ao atualizar; as migrações locais já foram aplicadas.

A revisão seguinte adiciona [ativação/desativação de banners na coluna Ações](docs/frontend/07-acoes-de-banners-e-filtros.md), substitui Filtrar pelo rótulo Filtros e remove Atualizar opções da agenda. Validação: 329 testes Django aprovados e verificações básicas no Chrome; nenhuma migração nova.

Em 06/10/2026, filtros e atualização de opções passaram a ter [aplicação automática](docs/frontend/06-aplicacao-automatica.md), preservando as ações explícitas de salvar. A carga inicial inclui [seis máquinas e nove espaços das imagens fornecidas](docs/modules/08-recursos-iniciais.md), com Secretaria, Laboratório maker e Laboratório de robótica reserváveis somente por administradores. Execute `python manage.py migrate` ao atualizar; no ambiente local as migrações já foram aplicadas. Validação desta entrega: 323 testes Django aprovados e verificações básicas no Chrome.

Revisar requisitos e decisões de cada etapa, validar seu desenho, preparar o plano, implementar o fluxo web/API e verificar cenários relevantes. A coleção de skills [Superpowers](https://github.com/obra/superpowers) foi instalada neste ambiente do Codex; não é dependência da aplicação e não acompanha um clone do projeto.

Por decisão do responsável, entregar um módulo por vez e aguardar sua depuração antes do próximo. Identidade e catálogo seguem suas especificações e planos autorizados. Tarefas, agenda, integrações, materiais e conteúdo seguem execução direta com planos simples ([tarefas](docs/superpowers/plans/2026-10-01-tarefas.md), [agenda](docs/superpowers/plans/2026-10-02-agenda.md), [integrações](docs/superpowers/plans/2026-10-02-integracoes.md), [materiais](docs/superpowers/plans/2026-10-02-materiais.md), [conteúdo](docs/superpowers/plans/2026-10-04-conteudo.md)), mantendo testes e revisão independente. Após [base e Dashboard](docs/superpowers/plans/2026-10-05-frontend-painel.md), a solicitação de todas as páginas reúne as telas restantes no [plano do frontend completo](docs/superpowers/plans/2026-10-05-frontend-completo.md). Escolhas para lacunas dos requisitos estão identificadas nos guias. Aguardar depuração desta entrega visual antes de iniciar outra etapa.

Para as próximas entregas visuais, seguir as referências com as funcionalidades atuais. A logo do InovaLab fornecida em `Referencias/logo.png` está incorporada; logos institucionais restantes aguardam os arquivos do responsável. A sidebar guarda a preferência de aberto/fechado no navegador, e Páginas mantém a estrutura interna após login. Veja [ajustes da sidebar, calendário e logo](docs/frontend/04-sidebar-calendario-e-logo.md). Executar os testes automatizados do Django e os testes básicos no navegador; o responsável realizará os testes mais profundos posteriormente. Essas orientações estão em [AGENTS.md](AGENTS.md).

O perfil permite editar login, nome, sobrenome e foto da própria conta. A logo de texto branco é usada nos fundos azuis. Veja [entrega e validações do perfil](docs/frontend/05-perfil-e-logo-branca.md). Ao atualizar outro ambiente, executar `python manage.py migrate` antes de iniciar o servidor.

Commits importantes seguem o formato em português, por exemplo `feat (docs): adiciona documentação da arquitetura do sistema.`.
