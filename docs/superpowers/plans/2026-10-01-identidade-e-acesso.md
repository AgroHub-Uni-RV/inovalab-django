# Plano de implementação — Identidade e acesso

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Entregar somente o módulo de identidade, com contas no admin, login/logout, página protegida e consulta da identidade por API; aguardar depuração pelo responsável antes do catálogo.

**Architecture:** Substituir o app vazio `auth` por `accounts`, mantendo a autenticação nativa do Django e um usuário baseado em `AbstractUser`. Views web e API utilizam a mesma classificação de papéis; a API usa sessão e DRF.

**Tech Stack:** Python 3.14, Django 6.1.1, Django REST Framework 3.18.1, SQLite local, templates e CSS.

**Spec:** [Especificação aprovada em 01/10/2026](../specs/2026-10-01-identidade-e-acesso-design.md).

## Global Constraints

- Somente identidade nesta entrega; sem iniciar catálogo, tarefas, agenda, materiais ou banners.
- Contas pelo administrador técnico; sem cadastro público, SSO ou recuperação por e-mail.
- `AUTH_USER_MODEL = 'accounts.User'`; preservar `django.contrib.auth`, sessões, CSRF e validadores de senha.
- Grupo de negócio `Administradores`; `is_staff` isolado não define administração do laboratório.
- Português, `America/Sao_Paulo`, layout responsivo e navegação por teclado.
- Rotas `/entrar/`, `/sair/`, `/`, `/admin/` e `/api/v1/me/`; logout somente por POST com CSRF.
- API somente leitura, sessão/`IsAuthenticated`, sem sessão retorna `403`; escrita autenticada retorna `405`.
- JSON com exatamente `id`, `username`, `first_name`, `last_name`, `is_business_admin`.
- Variáveis `DJANGO_DEBUG`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`; `.env` não carregado automaticamente.
- Sem debug, chave ausente falha explicitamente; hosts locais por padrão; não publicar ou implantar.
- Commits em português, no formato `feat (accounts): implementa identidade e acesso dos usuários.`.
- Concluir testes e roteiro manual; aguardar validação do responsável antes de outro módulo.

## Review Focus

1. Conta desativada depois do login: próxima requisição perde acesso web e API (tarefas 2/3).
2. `next` externo e senha incorreta: destino continua local e mensagem não revela existência da conta (tarefa 2).
3. Logout sem CSRF ou por GET: sessão permanece ativa; POST válido encerra acesso web/API (tarefas 2/3).
4. Grupo de negócio e `is_staff`: não concedem gestão técnica de contas por inferência (tarefas 1/2).
5. Configuração de produção sem chave, espaços nos hosts e valor inválido de debug: erro explícito ou normalização previsível (tarefa 1).

## Arquivos e responsabilidades

| Arquivos | Responsabilidade |
| --- | --- |
| `requirements.txt`, `setup/environment.py`, `setup/settings.py` | Dependências diretas e configuração de ambiente |
| `accounts/__init__.py`, `accounts/apps.py`, `accounts/models.py` | Registro do app e usuário configurável |
| `accounts/admin.py`, `accounts/policies.py` | Gestão técnica de contas e classificação de administrador de negócio |
| `accounts/migrations/__init__.py`, `0001_initial.py`, `0002_administrator_group.py` | Modelo e grupo inicial |
| `accounts/views.py`, `accounts/urls.py`, `setup/urls.py` | Login/logout e página protegida |
| `accounts/templates/accounts/{base,login,home}.html`, `accounts/static/accounts/style.css` | Interface básica acessível |
| `accounts/api.py` | Consulta de identidade autenticada em JSON |
| `accounts/tests/{__init__,test_identity,test_admin,test_web,test_api}.py` | Regras de identidade, gestão e fluxos |
| `setup/tests/{__init__,test_environment}.py` | Configuração testada sem iniciar Django |
| `README.md`, `docs/modules/01-identidade-e-acesso.md` | Execução, contrato entregue e roteiro para depuração |

Remover somente os sete arquivos de scaffold rastreados do app local `auth`, incluindo `auth/migrations/__init__.py`; preservar o pacote nativo Django. Não remover o ambiente virtual ou arquivos de banco. `core` permanece disponível, sem funcionalidade de negócio acrescentada.

## Preparação da execução

- [ ] Ler especificação e plano, verificar `git status`, banco existente e migrações; preservar alterações do responsável. Usar `using-git-worktrees` para decidir a execução isolada sem trocar ou mover seu checkout ativo.
- [ ] Se banco/dados surgiram após a revisão, inspecionar antes de mudar usuário; não apagar ou recriar por conveniência.
- [ ] Executar `& <python-do-venv> manage.py check` e registrar a falha inicial `duplicates: auth`. Em worktree, usar o executável do venv existente por caminho absoluto e executar os comandos no diretório do worktree.

## Tarefa 1 — Inicialização, usuário e administração de contas

**Files:** criar configuração, requisitos, modelo, admin, políticas, migrações e testes de identidade/admin/ambiente da tabela; modificar `setup/settings.py`; retirar scaffold local `auth`.

**Interfaces:**
- Produz `accounts.User(AbstractUser)` sem campos adicionais e `accounts.apps.AccountsConfig`.
- Produz `accounts.policies.is_business_admin(user: User | AnonymousUser) -> bool`: false para anônimo/inativo; true para superusuário ativo ou membro ativo de `Administradores`; `is_staff` isolado retorna false.
- Produz `setup.environment.RuntimeSettings`, dataclass imutável com `debug: bool`, `secret_key: str`, `allowed_hosts: tuple[str, ...]`, e `read_environment(environ: Mapping[str, str]) -> RuntimeSettings`.
- Produz duas migrações; grupo criado por `get_or_create` no alias do schema editor; reversão da migração do grupo usa `RunPython.noop` para preservar o cadastro.
- Produz `TechnicalUserAdmin(UserAdmin)` e `TechnicalGroupAdmin(GroupAdmin)`: métodos `has_module_permission`, `has_view_permission`, `has_add_permission`, `has_change_permission` e `has_delete_permission` exigem superusuário ativo. Registrar modelo de usuário e substituir registro do grupo no admin; não conceder edição de grupos por uma permissão herdada de staff.

Fixtures das tarefas: senha `InovaLab-Teste-2026!`; Ana tem username `ana`, first_name `Ana`, last_name `Silva`, é ativa e sem privilégios; Bruno usa username `bruno`; administrador técnico usa username `admin`, ativo, staff e superusuário. Criar fixtures com `get_user_model()` e `create_user/create_superuser`, sem IDs fixos.

- [ ] **Escrever testes que falham:**

```python
# test_identity.py — papéis, sem depender de IDs fixos
assert not is_business_admin(AnonymousUser())
assert not is_business_admin(User.objects.create_user('ana', password=password))
staff = User.objects.create_user('staff', password=password, is_staff=True)
assert not is_business_admin(staff)
staff.groups.add(Group.objects.get(name='Administradores'))
assert is_business_admin(staff)
staff.is_active = False
assert not is_business_admin(staff)
```

Adicionar testes independentes `test_active_superuser_is_business_admin`, `test_custom_user_and_default_flags`, `test_group_migration_is_idempotent` (invocar função duas vezes com schema editor real) e `test_user_password_is_hashed` (`check_password` true e valor salvo diferente da senha).

Em `test_admin.py`, autenticar superusuário, POST `/admin/accounts/user/add/` com `username='nova'`, `usable_password='true'`, `password1=password2='InovaLab-Teste-2026!'`; esperar redirecionamento, usuário ativo, sem staff/superusuário e senha válida. Testar senha `123` rejeitada sem criação. Edição pelo admin deve persistir nome, e-mail e `is_active=False`.

Em `test_environment.py`, usar `unittest.TestCase`: ambiente vazio retorna debug true e hosts `('localhost', '127.0.0.1')`; valores true/1/yes/on e false/0/no/off são aceitos sem distinguir maiúsculas. `DJANGO_DEBUG='talvez'` e debug false sem chave lançam `ImproperlyConfigured`; chave informada é preservada e hosts separados por vírgula são aparados, ignorando itens vazios.

- [ ] **Executar o ciclo vermelho:** `& <python-do-venv> -m unittest setup.tests.test_environment` e `& <python-do-venv> manage.py test accounts.tests.test_identity accounts.tests.test_admin`. Registrar import ausente/conflito de app antes da implementação.
- [ ] **Implementar as interfaces:** pinar somente `Django==6.1.1` e `djangorestframework==3.18.1` em requisitos, instalar no venv de execução, substituir app e configurar o usuário. `read_environment` usa fallback `django-insecure-inovalab-local-development-only` apenas com debug ativo; com debug false, chave ausente/vazia é erro. Registrar `User` usando `UserAdmin` nativo; cadastro/grupos/privilégios desta entrega ficam exclusivos do superusuário, inclusive se outro staff receber permissões de usuário.
- [ ] **Gerar e revisar migrações:** `makemigrations accounts`, criar a migração de grupo com modelos históricos e alias do schema editor; confirmar `0001` contém usuário configurável. Não atribuir permissões de outros módulos ao grupo.
- [ ] **Executar o ciclo verde:** os comandos de teste anteriores passam; `manage.py check` sem problemas; `manage.py makemigrations --check --dry-run` sem mudanças. Testar staff com permissões `accounts.add_user/change_user/view_user` e `auth.add_group/change_group/view_group`: URLs de usuários e grupos não permitem cadastro/edição e nenhum privilégio é alterado; superusuário continua operando. Incluir esses testes em `test_admin.py` antes da implementação.
- [ ] **Commit:** `feat (accounts): configura usuário e administração de contas.` com somente arquivos da tarefa.

## Tarefa 2 — Login, página protegida e logout

**Files:** criar views, URLs, três templates, CSS e `accounts/tests/test_web.py`; modificar `setup/urls.py` e redirecionamentos em `setup/settings.py`.

**Interfaces:**
- Consome `is_business_admin(request.user)` da tarefa 1 e autenticação nativa.
- Produz `accounts.views.home(request: HttpRequest) -> HttpResponse`, com `login_required` e contexto `is_business_admin`.
- URLs nomeadas `accounts:login`, `accounts:logout`, `accounts:home`; login usa `LoginView(template_name='accounts/login.html')`, logout usa `LogoutView`; `LOGIN_URL` aponta para login, `LOGIN_REDIRECT_URL='/'`, `LOGOUT_REDIRECT_URL` aponta para login.

- [ ] **Escrever testes que falham:**

```python
# test_web.py — sessão e redirecionamento
response = self.client.get('/')
self.assertRedirects(response, '/entrar/?next=/', fetch_redirect_response=False)
response = self.client.post('/entrar/', {'username': 'ana', 'password': password})
self.assertRedirects(response, '/')
self.assertContains(self.client.get('/'), 'ana')
self.assertEqual(self.client.get('/sair/').status_code, 405)
self.assertContains(self.client.get('/'), 'ana')
```

Adicionar `test_wrong_credentials_and_unknown_account_have_same_message`, `test_inactive_account_cannot_login`, `test_local_next_is_honored`, `test_external_next_is_rejected` (incluindo `//externo.example/`), `test_business_admin_cannot_manage_accounts` e `test_superuser_sees_admin_link`.

Com `Client(enforce_csrf_checks=True)`, GET login para obter cookie CSRF; POST login sem token retorna 403; POST com token autentica. Depois ler cookie rotacionado: logout sem token retorna 403 e mantém acesso; POST com token redireciona para login e fecha página privada. Em `test_deactivation_revokes_existing_session`, autenticar, salvar `is_active=False` e confirmar redirecionamento no GET seguinte.

- [ ] **Executar vermelho:** `& <python-do-venv> manage.py test accounts.tests.test_web`; confirmar rotas/templates ainda ausentes.
- [ ] **Implementar o fluxo:** views nativas e política compartilhada; `{% csrf_token %}` em formulários, `next` como campo oculto escapado; botão Sair envia POST. Saudação e papel são dados reais do usuário; link do admin apenas para superusuário desta entrega.
- [ ] **Implementar interface:** labels explícitos, usuário/senha com autocomplete adequado, erros genéricos em português, foco visível e layout funcional a 360 px. CSS por static tag; sem bibliotecas externas de frontend.
- [ ] **Executar verde:** testes web e testes anteriores passam; verificar idioma, URLs nomeadas e logout sem dispensar CSRF.
- [ ] **Commit:** `feat (accounts): adiciona login e logout com interface básica.`.

## Tarefa 3 — API de identidade e entrega para depuração

**Files:** criar `accounts/api.py`, `accounts/tests/test_api.py`, `docs/modules/01-identidade-e-acesso.md`; modificar URLs, configuração DRF, README, arquivo 04, arquivo 05 e este plano.

**Interfaces:**
- Consome `User`, sessão e `is_business_admin` das tarefas anteriores.
- Produz `accounts.api.MeView(APIView)` com `SessionAuthentication`, `IsAuthenticated`, `JSONRenderer`, `get(request) -> Response` e `http_method_names=['get', 'head', 'options']`.
- Produz `GET /api/v1/me/`, sem parametro de ID, com exatamente as cinco chaves da especificação e dados do usuário atual.

- [ ] **Escrever testes que falham:**

```python
# test_api.py — privacidade e contrato
self.assertEqual(self.client.get('/api/v1/me/').status_code, 403)
self.client.force_login(ana)
response = self.client.get('/api/v1/me/')
self.assertEqual(response.status_code, 200)
self.assertEqual(response.json(), {
    'id': ana.pk, 'username': 'ana', 'first_name': 'Ana',
    'last_name': 'Silva', 'is_business_admin': False,
})
```

Criar Bruno e confirmar que a resposta não muda com `?id=<bruno.pk>`. Testar classificação de grupo/staff/superusuário e não exposição de senha/e-mail. Para POST/PUT/PATCH/DELETE autenticados, enviar CSRF válido com cliente que aplica CSRF e esperar 405; sem autenticação, esperar 403. Desativação pós-login retorna 403. Logout válido da tarefa 2 também encerra acesso à API. Corpo anônimo contém `detail`, sem campos de identidade.

- [ ] **Executar vermelho:** `& <python-do-venv> manage.py test accounts.tests.test_api`; confirmar endpoint ausente.
- [ ] **Implementar API:** permissões e autenticação explícitas, política compartilhada, JSON por campos permitidos. Não criar API de listagem de contas ou login externo.
- [ ] **Executar verde e checks finais:** `& <python-do-venv> manage.py test`, `manage.py check`, `manage.py makemigrations --check --dry-run`, `& <python-do-venv> -m pip check` e `git diff --check`, todos sem falhas.
- [ ] **Preparar roteiro:** documentar `pip install -r requirements.txt`, `migrate`, `createsuperuser`, `runserver`, variáveis PowerShell e contrato da API; comandos usando o venv local e sem publicar senha real. Explicar que `.env` não é lido e que configuração de produção não é uma implantação validada.
- [ ] **Verificar migração real local:** aplicar `migrate` somente ao banco local destinado à execução; confirmar que repetição não duplica grupo; não apagar banco existente. Criar conta temporária apenas para verificação, sem adicionar credenciais ao Git.
- [ ] **Verificar no navegador:** ao iniciar dev server, usar as skills de browser/verificação; testar login, senha errada, página privada, API, admin e logout, console e static CSS. Verificar teclado e largura 360 px. Relatar limites reais caso a ferramenta não esteja disponível.
- [ ] **Atualizar estado documental:** README/arquivo 04 deixam de apresentar a colisão como falha atual; arquivo 05 mantém o diagnóstico histórico datado e registra entrega de identidade. Especificação continua vinculada à entrega e plano marca somente passos efetivamente concluídos.
- [ ] **Commit:** `feat (accounts): expõe identidade autenticada e documenta a entrega.`.

## Revisão e encerramento do módulo

- [ ] Conferir cada critério de aceite da especificação contra testes e navegador; revisar vazamento de dados, CSRF e privilégios. Se execução direta for escolhida, fazer a revisão independente prevista em `executing-plans`; se subagentes forem escolhidos, seguir as revisões de `subagent-driven-development`.
- [ ] Informar commits, verificações executadas, caminhos locais e roteiro manual. Respeitar trabalho do usuário ao integrar a entrega de eventual worktree; não descartar mudanças ou mover seu checkout ativo.
- [ ] Encerrar a entrega aguardando depuração do responsável. Não começar catálogo nem planejar sua implementação antes de indicação para avançar.

## Revisão do plano e método de execução

Plano preparado com três tarefas que compartilham modelo, papéis e sessão. Recomenda-se execução direta, por ser um módulo pequeno com interfaces dependentes; execução por subagentes é alternativa se o responsável preferir revisões entre tarefas. Revisar este plano e escolher o método antes de implementar, conforme `writing-plans`.
