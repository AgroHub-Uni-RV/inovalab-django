# Módulo 1 — Identidade e acesso

01/10/2026 • Especificação para revisão antes do plano de implementação. Base: RF01, RF23/RF24, CT25, arquitetura do arquivo 05 e decisão do responsável sobre Q11. Este módulo será entregue sozinho; após testes automatizados e roteiro manual, aguardar o responsável debugar antes de iniciar outro módulo.

## Objetivo e limites

Permitir que o administrador cadastre contas internas e que usuários ativos entrem por usuário/senha, consultem sua identidade e encerrem a sessão. Corrigir o conflito do app local `auth` e estabelecer o modelo de usuário antes das primeiras migrações.

Esta entrega contém identidade, acesso e a base técnica necessária para executá-los. Catálogo, tarefas, agenda, materiais e banners serão entregas posteriores. Login institucional, cadastro público e recuperação por e-mail não fazem parte deste módulo.

## Escolhas de arquitetura

Usar `accounts.User` baseado em `AbstractUser`, autenticação nativa do Django, templates e DRF para a API. O app local vazio `auth` será substituído por `accounts`; `django.contrib.auth` permanece instalado. O modelo deve ser configurado por `AUTH_USER_MODEL` e suas referências usarão essa configuração.

Alternativas consideradas: manter o usuário padrão simplifica o início, mas torna uma substituição futura mais custosa; SSO exige um provedor e contrato ainda não definidos. `AbstractUser` mantém as operações nativas e permite evolução da identidade sem um mecanismo próprio de senhas.

Verificação de base: não existe `db.sqlite3` e não há migrações de domínio numeradas no checkout em 01/10/2026. Reconfirmar na execução; se surgirem dados, preservá-los e avaliar a migração antes de alterar a identidade.

Runtime desta entrega: Python 3.14, Django 6.1.1 e Django REST Framework 3.18.1. As versões diretas serão registradas em `requirements.txt`. DRF declara suporte às séries Django 6.1 e Python 3.14; o fluxo será testado nessa combinação. [Requisitos oficiais](https://www.django-rest-framework.org/#requirements).

SQLite será usado neste módulo local de identidade. A decisão do banco e os testes concorrentes da agenda pertencem à etapa da agenda.

## Contas e papéis

- O administrador técnico inicial é criado com `createsuperuser` e provisiona contas no Django Admin. O usuário padrão nasce ativo, sem acesso administrativo e sem privilégios extras.
- O formulário de criação de conta no admin utiliza senhas protegidas pelo Django e sua validação. Admin pode editar nome, e-mail e ativação da conta.
- Criar o grupo de negócio `Administradores` por migração de dados idempotente. A classificação de administrador do negócio usa associação ao grupo; superusuário ativo também é considerado administrador. A classificação não depende apenas de `is_staff`.
- Atribuição de grupos e privilégios fica com o administrador técnico neste módulo. O grupo de negócio não concede automaticamente acesso ao Django Admin ou gestão de contas. Permissões dos módulos de negócio serão adicionadas nas respectivas entregas, conforme Q12.
- Não disponibilizar listagem de usuários por API. Nome de usuário é identificador único de login; e-mail e nomes seguem o modelo nativo, sem torná-los obrigatórios ou únicos por suposição.

Essas regras distinguem administração técnica de administração do laboratório. O cadastro pelo administrador e login por usuário/senha foram confirmados pelo responsável; a separação técnica de papéis é a proposta desta especificação.

## Rotas e comportamento

| Rota | Método | Resultado esperado |
| --- | --- | --- |
| `/entrar/` | GET | Formulário em português com usuário, senha e botão Entrar |
| `/entrar/` | POST | Credenciais válidas de conta ativa criam sessão e redirecionam para `/` ou destino local seguro; erro retorna mensagem genérica, sem identificar existência da conta |
| `/` | GET | Exige login; exibe saudação, nome de usuário e papel; oferece Sair e, ao administrador técnico, acesso ao admin |
| `/sair/` | POST | Exige CSRF, encerra sessão e redireciona para `/entrar/`; GET não encerra sessão |
| `/admin/` | GET/POST | Django Admin com o usuário configurável; usuários sem acesso administrativo não gerenciam contas |
| `/api/v1/me/` | GET | Sessão válida retorna JSON da identidade atual; não recebe ID de outra pessoa |

Login/logout usam as views nativas com templates próprios. Parâmetro `next` não aceita redirecionamento para domínio externo. Conta inativa não autentica e deixa de acessar páginas privadas/API mesmo se tiver sessão anterior. Não desabilitar CSRF para resolver erros do navegador. [Autenticação do Django](https://docs.djangoproject.com/en/6.1/topics/auth/default/#all-authentication-views).

Contrato positivo de `GET /api/v1/me/`, sem envelope extra:

```json
{
  "id": 1,
  "username": "ana",
  "first_name": "Ana",
  "last_name": "Silva",
  "is_business_admin": false
}
```

DRF usa `SessionAuthentication`, `IsAuthenticated` e resposta JSON. Sem sessão válida, retornar `403` e o corpo padrão `detail` do DRF; não prometer `401` com autenticação por sessão. A API é somente leitura: POST/PUT/PATCH/DELETE retornam `405` para usuário autenticado. Nenhuma resposta contém senha, hash, e-mail de terceiros, lista de contas ou credencial. A autenticação de integrações externas será tratada em seu próprio módulo.

## Interface e configuração

Interface básica em português, com layout responsivo, campos rotulados, mensagens legíveis e navegação por teclado. A página inicial apresenta apenas identidade e ações disponíveis neste módulo, sem indicadores de negócio fictícios.

Configuração por variáveis de ambiente padrão da biblioteca Python: `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`. Desenvolvimento local inicia com debug ativo e hosts localhost/127.0.0.1; chave de fallback é exclusivamente de desenvolvimento. Com debug desativado, a chave deve ser informada e a aplicação deve falhar claramente se estiver ausente. Não usar hosts irrestritos por padrão. `.env` não é carregado automaticamente: o README deve mostrar como definir variáveis em PowerShell.

Preservar pt-br, `America/Sao_Paulo`, middleware de sessão/autenticação/CSRF e validações de senha. Não implantar nem alterar serviços externos nesta entrega.

## Critérios de aceite e verificação

1. `manage.py check` passa; primeira migração registra o usuário customizado; `makemigrations --check --dry-run` não detecta mudanças pendentes.
2. Admin cria conta e a senha não fica em texto puro; conta ativa autentica, credencial inválida e conta inativa não autenticam.
3. Usuário anônimo é redirecionado da página privada; usuário ativo vê sua identidade. Usuário comum não gerencia contas no admin.
4. `/api/v1/me/` retorna somente o usuário autenticado e as cinco chaves do contrato. Grupo de negócio e superusuário produzem classificação correta; `is_staff` isolado não torna usuário administrador do laboratório.
5. Logout por POST com CSRF encerra o acesso à página e API; POST sem CSRF falha, GET não encerra sessão. `next` externo não redireciona para outro domínio.
6. Desativar conta invalida acesso autenticado em requisições posteriores. API de identidade não aceita escrita e usuário autenticado recebe `405`.
7. Testes de configuração verificam hosts locais e rejeição de chave ausente quando debug está desativado.
8. Instalação, migração, criação do administrador, execução local e roteiro de teste manual ficam documentados. Verificação visual confirma login, erro, página privada e logout no navegador, com interface utilizável por teclado.

O teste automatizado deve cobrir regras de acesso, sessão, CSRF e configuração, não apenas a existência das classes. A entrega deve informar quais verificações passaram e qualquer limitação encontrada.

## Entrega e passagem ao próximo módulo

Fazer commits em português no formato solicitado, por alteração importante, por exemplo `feat (accounts): implementa identidade e acesso dos usuários.`. A especificação e o plano recebem commits próprios de documentação.

Após concluir somente este módulo, fornecer comandos de execução e roteiro para o responsável debugar login, contas, papéis, endpoint e logout. Corrigir problemas desse módulo conforme o feedback. Iniciar catálogo ou qualquer outro módulo apenas quando o responsável indicar que terminou a validação e autorizar o avanço.
