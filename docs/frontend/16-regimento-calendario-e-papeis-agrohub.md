# Regimento, calendário de funcionamento e papéis do AgroHub

Entrega autorizada em 07/10/2026: portar as duas páginas públicas restantes do InovaLab do monólito e restringir a área interna, inclusive agendamentos, aos administradores e à equipe do AgroHub.

## Páginas públicas

| Rota | Conteúdo |
| --- | --- |
| `/regimento/` | Regimento original, com dez seções e vinte artigos |
| `/calendario-de-funcionamento/` | Calendário institucional do semestre 2026/2 |

Templates, conteúdo editorial, imagens e datas foram consultados em `apps/inovalab` do repositório `unirv-monolith`, sem alterar esse repositório. O cabeçalho institucional, breadcrumbs Início e controles de acessibilidade usam a base existente. Os atalhos do início e os links do rodapé passam a apontar para estas rotas locais.

O calendário reproduz julho a dezembro de **2026**, com seis feriados e sete dias de recesso definidos no monólito. Domingos e hoje permanecem neutros. É conteúdo institucional estático, separado do calendário de eventos que consulta a API Ecosystem. Alterar o semestre requer atualizar esse conteúdo; esta entrega não oferece cadastro administrativo de datas nem transforma essas marcações em bloqueios de agendamento.

## Autorização pelo Accounts

A fonte de autorização é o campo `roles` retornado por **GET `/api/v1/accounts/me/`**, autenticado com o token da própria conta. O contrato publicado não retorna as flags técnicas Django `is_staff` ou `is_superuser`. `profile.user_type` é editável e não concede acesso.

| `roles` da conta ativa | Papel neste sistema | Área interna e agendamentos | Funções administrativas do laboratório |
| --- | --- | --- | --- |
| Contém `admin` | Administrador | Sim | Sim |
| Contém `staff`, sem `admin` | Usuário interno da equipe | Sim | Não |
| Vazio, ausente ou outros papéis | Usuário do AgroHub | Não | Não |

Permissões específicas continuam em vigor: a equipe consulta o catálogo, agenda visitas e executa suas tarefas; somente administradores mantêm cadastros, avaliam solicitações e gerenciam integrações. `staff` não equivale à flag técnica Django com o mesmo nome.

A migração `accounts.0005_papeis_agrohub` adiciona uma cópia local dos papéis, somente para sincronização. Ela é atualizada no login e antes de cada requisição privada, a partir de `/me/`. Remover o papel no provedor revoga o acesso na próxima requisição sem exigir novo login. Uma falha do provedor impede o acesso privado com 503; resposta inválida nunca autoriza usando os papéis antigos. As seis páginas institucionais continuam disponíveis durante falhas da sessão remota.

Para contas vinculadas ao AgroHub, grupos e flags locais antigos não concedem o papel de administrador ou equipe. Contas técnicas locais existentes conservam o tratamento próprio; a autenticação por senha permanece exclusivamente no AgroHub. A manutenção técnica global de contas/grupos continua exigindo superusuário local ativo e, para uma conta vinculada, também o papel remoto `admin`. A sincronização não promove ninguém automaticamente a superusuário do banco local.

O middleware aplica a restrição às rotas e APIs internas antes de executar suas views. Usuários comuns recebem 403, mesmo acessando diretamente a URL; visitantes são encaminhados ao login. As APIs externas de integrações preservam a autenticação por credencial própria. Páginas e imagens públicas de banners permanecem públicas. O cadastro público e o perfil não permitem editar papéis.

Usuários sem acesso interno voltam ao início institucional após login e conservam o perfil com edição dos próprios dados, foto e saída. O perfil usa o cabeçalho público, sem sidebar ou link para o Dashboard. Administradores e equipe preservam o perfil na estrutura interna.

## Atualização e verificação

Execute `venv/Scripts/python.exe manage.py migrate` ao atualizar outro ambiente. A migração já foi aplicada localmente; o build existente da Vercel também executa as migrações.

- `venv/Scripts/python.exe manage.py test --noinput`: 578 testes aprovados, incluindo páginas públicas, classificação de papéis, promoção/revogação, rotas web/API, indisponibilidade e manutenção das permissões operacionais.
- `venv/Scripts/python.exe manage.py check`: sem problemas.
- `venv/Scripts/python.exe manage.py makemigrations --check --dry-run`: sem alterações pendentes.
- `git diff --check`: sem problemas de whitespace.
- Chrome: páginas em 1896 e 360 px, imagens presentes, breadcrumbs e atalhos locais, sem transbordamento horizontal.
- Fluxo de ponta a ponta no navegador com banco isolado e Accounts HTTP simulado: login → sincronização de `/me/` → acesso de equipe → promoção a administrador e criação de serviço → remoção dos papéis → 403 no Dashboard, cadastro de visita e APIs de catálogo/agenda. Perfil continuou acessível e salvou os próprios dados. Durante falha simulada, a área privada retornou 503 e o regimento permaneceu acessível.
- Revisão independente corrigiu o layout do perfil de usuários comuns e a classificação de administradores na listagem técnica. Os cenários receberam testes de regressão.

Uma repetição da suíte apresentou falha intermitente no cenário de decisões opostas simultâneas da agenda em SQLite: as duas operações retornaram conflito, enquanto o teste exige uma gravação vencedora. A classe de concorrência passou isoladamente (oito testes). O caminho de gravação da agenda não foi alterado nesta entrega; manter esse cenário no roteiro de depuração, inclusive em PostgreSQL.

Capturas: [regimento desktop](screenshots/institucional-regimento-1896.png), [regimento móvel](screenshots/institucional-regimento-360.png), [funcionamento desktop](screenshots/institucional-funcionamento-1896.png), [funcionamento móvel](screenshots/institucional-funcionamento-360.png) e [perfil público](screenshots/institucional-perfil-publico-1200.png).

Uma consulta somente leitura no Accounts real confirmou uma conta ativa com `roles: []`, sem os papéis exigidos para entrar na área interna. Não foram feitos cadastros ou alterações na API real. A depuração com contas reais de equipe/admin e os testes mais profundos continuam com o responsável.
