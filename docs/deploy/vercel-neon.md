# Deploy Django na Vercel com Neon

## Projeto e fluxo

Projeto existente: `inovalab-test`, equipe `henrickevieiraperes-4602s-projects`,
repositório `yRicke/inovalab-django`, branch de produção `main`.
O vínculo Git foi confirmado pelo deployment do commit `7d295a6`.
A pasta local `.vercel/` identifica esse projeto e fica fora do Git.

O preset Django reconhece `manage.py` e `setup.wsgi.application`.
`vercel.json` define `python scripts/vercel_build.py` como Build Command.
Cada push aceito pela integração Git inicia um build:

1. A Vercel instala `requirements.txt`.
2. O script valida as duas URLs e executa `check --deploy --fail-level WARNING`.
3. Uma conexão PostgreSQL direta obtém um advisory lock exclusivo por banco.
4. Django executa `migrate --noinput`, incluindo cargas iniciais das migrações.
5. A Vercel executa `collectstatic` e serve os estáticos pela CDN.
6. O deployment é publicado quando o build inteiro termina com sucesso.

Migrações não rodam em cada requisição. O lock serializa builds que usam o
mesmo banco, com espera máxima de 120 segundos. Uma falha interrompe o build;
as migrações já concluídas permanecem no banco. O deployment anterior continua
ativo, mas seu código precisa ser compatível com o esquema migrado. Use
migrações compatíveis com a versão anterior e faça remoções em uma entrega
posterior. Rollback de código na Vercel não reverte o banco.

## Variáveis na Vercel

Configure as variáveis em **Settings → Environment Variables**, separadamente
em Production e Preview. Nunca envie senhas pelo chat nem comite URLs reais.

| Variável | Valor/uso |
| --- | --- |
| `DJANGO_DEBUG` | `false` |
| `DJANGO_SECRET_KEY` | Chave aleatória de pelo menos 50 caracteres; armazenar como segredo |
| `DJANGO_ALLOWED_HOSTS` | `inovalab-test.vercel.app` e eventuais domínios próprios, separados por vírgula |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Opcional: origens HTTPS completas para acessos entre origens; acesso no mesmo domínio não precisa disso |
| `DATABASE_URL` | URL PostgreSQL Neon com hostname `-pooler`, usando `sslmode=require` |
| `DATABASE_URL_UNPOOLED` | URL direta do mesmo banco, branch e usuário, sem `-pooler`, usando `sslmode=require` |

A integração Neon da Vercel pode preencher as URLs ao conectar o recurso ao
projeto. Confirme que ambas existem no ambiente do deployment. Ative a
exposição das variáveis de sistema da Vercel se ela estiver desativada:
`VERCEL_URL`, `VERCEL_BRANCH_URL` e `VERCEL_PROJECT_PRODUCTION_URL` acrescentam
somente os hosts exatos do deployment aos hosts permitidos. Não é necessário
liberar `*` nem `.vercel.app`.

Production e Preview devem usar bancos/branches próprios. Para um projeto
exclusivamente de teste, compartilhar o banco pode ser uma escolha consciente,
mas o push de uma branch de Preview também mudará o esquema compartilhado.
Não aponte previews de código não confiável para um banco real de produção.

Na Vercel, a aplicação exige PostgreSQL com TLS, chave secreta e `DEBUG=false`.
Cookies de sessão/CSRF usam Secure; Django redireciona HTTP para HTTPS, ativa
HSTS e conserva as proteções nativas de CSRF, MIME e iframe. O cabeçalho
`X-Forwarded-Proto` só é confiado quando o processo está na Vercel.

O console de e-mail fica restrito ao desenvolvimento. Fora de `DEBUG`, o
backend nativo SMTP usa STARTTLS. Antes de habilitar qualquer envio, configure
`DJANGO_EMAIL_HOST`, `DJANGO_EMAIL_PORT` (587 por padrão), `DJANGO_EMAIL_USER`,
`DJANGO_EMAIL_PASSWORD` e `DJANGO_DEFAULT_FROM_EMAIL`. Esta entrega não
contrata um serviço de e-mail nem testa entrega de mensagens.

## Desenvolvimento local

```powershell
Copy-Item .env.example .env
& .\venv\Scripts\python.exe -m pip install -r requirements.txt
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py runserver
```

`.env.local` é carregado antes de `.env`; variáveis já definidas no processo
sempre prevalecem. Na Vercel, arquivos dotenv não são carregados.
Sem `DATABASE_URL`, a execução local conserva SQLite; na Vercel isso é erro.
`.env*`, `media/`, SQLite e ambientes virtuais ficam fora do upload de deploy.

Com o CLI autenticado, para confirmar ou recriar o vínculo local:

```powershell
npx vercel link --yes --project inovalab-test --scope henrickevieiraperes-4602s-projects
npx vercel env ls --scope henrickevieiraperes-4602s-projects
```

Após a configuração, faça o push normalmente. Não é necessário GitHub Actions
nem guardar um token Vercel no GitHub. O Build Command no dashboard não deve
substituir o definido no repositório. Não configure Ignored Build Step que
ignore pushes que precisam de migrações.

O superusuário deve ser criado explicitamente no Neon por uma execução
administrativa confiável de `manage.py createsuperuser`, com o ambiente certo.
O deploy não cria usuários ou senhas padrão. A troca de SQLite por Neon não
transfere os dados locais automaticamente.

## Limitação de uploads

Fotos de perfil e banners usam armazenamento de arquivos local. O disco da
Vercel não oferece armazenamento persistente para esses uploads. Arquivos
incluídos no código, como logos e fotos iniciais dos equipamentos, continuam
disponíveis. Antes de usar uploads no ambiente hospedado, configure um backend
persistente e adapte também `EquipmentPhotoStorage`; só definir `MEDIA_ROOT`
ou enviar a pasta `media/` no deploy não resolve. Esta entrega concentra-se
em banco, segurança e automação do deploy.

## Verificação e estado da entrega

```powershell
& .\venv\Scripts\python.exe manage.py test
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\venv\Scripts\python.exe manage.py collectstatic --noinput
& .\venv\Scripts\python.exe -m pip check
```

Os testes de `setup.tests` cobrem hosts exatos, segredo obrigatório, recusa de
debug, URL/TLS do PostgreSQL, falha do build antes de conexão em configuração
inválida, HTTPS, headers, cookie Secure e CSRF. Testes locais usam SQLite;
isso não equivale a validar migrações e concorrência no PostgreSQL.

Resultado local em 06/10/2026: **410 testes passaram**, incluindo 21 testes
de configuração/deploy. `check`, `check --deploy --fail-level WARNING` com
configuração de produção, `makemigrations --check --dry-run` e `pip check`
passaram. `collectstatic --noinput` coletou 177 arquivos. No navegador,
o login abriu com CSS e logo sem imagens quebradas; `/index/` redirecionou
visitantes ao login, e `/publico/` renderizou corretamente.

Após autorização do responsável, em 06/10/2026 foi criado o recurso Neon
`inovalab-test`, projeto `spring-art-33956581`, banco `neondb`, na região
`aws-us-east-1` (`iad1`), plano Free. O recurso Vercel
`store_PLN2O27WKc42JoGq` está conectado ao projeto em Production e Preview.
Esses dois ambientes compartilham **este banco de teste**, portanto qualquer
push de Preview também aplica migrações nele. A autenticação Neon foi
desativada no provisionamento; as contas continuam geridas pelo Django.

As duas URLs PostgreSQL com TLS foram configuradas pela integração. Chaves
Django distintas foram geradas para Production e Preview e armazenadas como
Secret, sem valores em logs ou Git. `DJANGO_DEBUG=false`, hosts permitidos e
exposição das variáveis de sistema foram configurados no projeto.
O CLI Vercel foi autenticado pelo responsável; `.env.production.local` é um
arquivo privado e ignorado, separado do ambiente de desenvolvimento local.

O script de build executou a verificação de segurança e todas as migrações
com sucesso no Neon recém-criado: 36 migrações registradas, 11 serviços,
6 equipamentos e 9 espaços. Nenhum usuário ou senha padrão foi criado.
Os **36 testes básicos PostgreSQL** (`setup.tests`,
`accounts.tests.test_identity`, `catalogo.tests.test_models`) passaram em
`test_inovalab_deploy_20261006`, removido automaticamente pelo test runner.
A suíte SQLite foi repetida após o ajuste de compatibilidade de overflow:
**410 testes passaram**. As verificações de modelos e dependências passaram.

O bloqueio de build foi verificado no PostgreSQL: mantendo o advisory lock
em outra conexão, o build aguardou; depois da liberação, concluiu com sucesso.
A publicação pelo push para `main` foi concluída: deployment
`dpl_Fi7vf9rAiSN2WbaQNU4hGn9n4Zqe`, commit `2a55f48`, estado **READY**,
em [inovalab-test.vercel.app](https://inovalab-test.vercel.app).
Os logs confirmaram a execução de `python scripts/vercel_build.py`,
verificação de segurança, `migrate` sem pendências e `collectstatic` antes
da publicação. Login, CSS, logo, página pública e
`/api/v1/publico/banners/?local=home` responderam HTTP 200; `/index/`
redirecionou visitantes para o login. Os headers HTTPS/MIME/iframe foram
verificados. As requisições usaram `vercel curl` autenticado; a proteção
de acesso da Vercel foi preservada. No navegador local, login e página
pública foram novamente verificados, sem imagens quebradas.

Testes de todos os módulos no PostgreSQL, uploads persistentes e fluxos
autenticados completos ainda precisam de validação posterior pelo responsável.
O banco hospedado começa sem contas: criar o superusuário explicitamente,
com um ambiente administrativo conectado ao Neon, antes de usar a área interna.
Após essa entrega, aguardar a depuração do responsável antes de outro módulo.

Fontes: [Django na Vercel](https://vercel.com/docs/frameworks/full-stack/django)
e [conexões Neon](https://neon.com/docs/connect/connection-pooling).
