# InovaLab como um único aplicativo Django

Implementação do plano aprovado em 07/10/2026. O pacote instalável chama-se `inovalab-app`; o módulo Python e o label Django são `inovalab_app`.

## Organização e limites

`setup` configura o sistema independente; `accounts` mantém o usuário local e a autenticação atual pela API. Somente `inovalab_app.apps.InovalabConfig` registra o negócio. Seus pacotes internos são shared, catalogo, materiais, tarefas, agenda e conteudo, sem outros AppConfigs.

Shared mantém layout, navegação, dashboard e utilitários de horários. Os demais pacotes conservam models, forms, services, selectors, views e APIs por domínio. O pacote models importa os modelos concretos; as três agendas continuam independentes. Templates/static usam o prefixo `inovalab_app`, inclusive as imagens institucionais e fotos iniciais de equipamentos. Há wrappers dos templates de erro padrão para o hospedeiro independente.

URLs e namespaces anteriores continuam válidos: core, catalogo, tarefas, agenda, materiais e conteudo. Namespaces HTTP não são labels de modelos. A proteção das APIs usa marcações explícitas dos callbacks de rota, sem identificar classes por seu caminho Python. Criação e ações pessoais continuam abertas às contas ativas autenticadas, com proteção adicional nos serviços.

## Fronteira com o hospedeiro

Configure `INOVALAB_HOST_ADAPTER` com o caminho de uma classe sem argumentos. O adaptador deve implementar:

| Método | Contrato |
| --- | --- |
| `can_access_panel(user)` | Booleano: acesso interno |
| `is_business_admin(user)` | Booleano: administração do laboratório |
| `is_technical_admin(user)` | Booleano: administração técnica |
| `identity_context(request)` | Dicionário com login_url, logout_url, profile_url, users_url e photo_url; URLs opcionais podem ser vazias |
| `has_profile_photo(user)` | Booleano; aceitar também usuário ausente |
| `profile_photo_response(user)` | Resposta HTTP da foto ou Http404 |
| `load_events()` | Par `(eventos, indisponivel)` com os campos normalizados usados pelo dashboard/conteúdo |
| `send_contact(payload)` | Resultado com ID inteiro positivo ou HostServiceError com status/errors |

O sistema independente usa `accounts.inovalab_adapter.AgroHubHostAdapter`, que delega às políticas e serviços atuais. Eventos são carregados por `accounts.agrohub.events`; contato continua usando `site_code=inovalab`. O adaptador e os context processors estão configurados em setup. Erros de configuração são identificados por `manage.py check`.

O adaptador opcional `inovalab_app.adapters.django.DjangoHostAdapter` permite hospedar o negócio com um usuário nativo sem campos do AgroHub: conta ativa staff/superuser acessa o painel; superuser administra. Perfil/logout são opcionais, configurados por INOVALAB_PROFILE_URL/INOVALAB_LOGOUT_URL. Eventos ficam vazios e contato retorna indisponibilidade até o hospedeiro implementá-los. Isso não troca a fonte de autorização deste sistema.

As FKs de identidade usam AUTH_USER_MODEL. O negócio não importa o modelo User de Accounts nem consulta agrohub_id/roles. Para um hospedeiro próprio, instalar o pacote, definir o adaptador, incluir `inovalab_app.urls`, configurar seus context processors e `inovalab_app.shared.middleware.InovalabAccessMiddleware`. O hospedeiro fornece autenticação, sessões, media, static, idioma, fuso e login. A montagem sob `/laboratorio/` é coberta por testes.

## Instalação nova

No sistema independente:

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py seed_inovalab
python manage.py check
python manage.py runserver
```

A carga inicial é um comando separado, idempotente e por código estável. Desde 08/10/2026, seed_inovalab carrega somente equipamentos; carregar_servicos_iniciais explica o novo fluxo sem cadastrar serviços. Ver [25-servicos-tarefas-infraestrutura.md](25-servicos-tarefas-infraestrutura.md). carregar_recursos_iniciais continua disponível. Migrações novas não cadastram dados de negócio. O test runner executa explicitamente a carga inicial no banco de testes; o build executa a carga apenas quando não havia tabelas de negócio.

Para gerar o pacote: `python -m pip wheel . --no-deps`. O wheel inclui somente inovalab_app, seus recursos e metadados de validação; Accounts/setup/testes ficam no repositório hospedeiro. As dependências do pacote aceitam Django 5.2 até 6.1 e DRF 3.17/3.18; requirements.txt conserva as versões do sistema independente.

## Atualização de um banco existente

1. Na versão anterior à consolidação, executar todas as migrações pendentes. Os últimos nós exigidos são catalogo.0007_remove_espaco, materiais.0001_initial, tarefas.0001_initial, conteudo.0001_initial e agenda.0017_remove_integracoes.
2. Interromper escrita e workers; fazer backup consistente do banco, media e arquivos privados do legado. Guardar também a revisão anterior do código.
3. Carregar a versão consolidada, usando o mesmo banco, AUTH_USER_MODEL e storage.
4. Executar os comandos abaixo. Se a verificação falhar, corrigir a divergência na versão anterior; não marcar migrações manualmente para contorná-la.

```powershell
python manage.py check_inovalab_upgrade
python manage.py migrate inovalab_app 0002_preserva_contenttypes --fake-initial --noinput
python manage.py check
python manage.py makemigrations --check --dry-run
```

5. Na versão de 08/10/2026, concluir as migrações de serviços/tarefas usando o mapa explícito descrito em [25-servicos-tarefas-infraestrutura.md](25-servicos-tarefas-infraestrutura.md). Somente depois comparar dados e arquivos com o backup, testar acessos e retomar escrita. Não executar seed_inovalab para transportar dados existentes.

Os nomes físicos catalogo_*, materiais_*, tarefas_*, agenda_* e conteudo_banner são explícitos, incluindo agenda_agendaservico_equipamentos. Não há cópia, renumeração ou recriação das tabelas na adoção. A migração inicial representa esse esquema; fake-initial registra somente sua adoção.

O comando migrate do app verifica a primeira atualização inclusive quando chamado diretamente por um build. Verifica últimas migrações anteriores, presença integral das tabelas/colunas, tipos, nulabilidade, precisão quando suportada pelo banco, PKs, FKs, unicidade, índices e os nomes/definições dos 27 CHECKs congelados da versão anterior. SQLite não impõe precisão decimal como PostgreSQL. Tabelas aposentadas e conflitos de ContentType bloqueiam a transição. `--fake` não substitui esse procedimento.

Após o registro da migração inicial, a verificação aceita também as duas representações de CHECK booleano geradas pelo Django 5.2 no SQLite. A adoção de um banco anterior continua exigindo exatamente as definições originais. O retorno após login preserva parâmetros já existentes na URL de autenticação do hospedeiro.

A segunda migração atualiza o app_label dos ContentTypes preservando seus IDs. Permissões, vínculos com grupos/usuários e histórico do Admin continuam apontando para esses mesmos IDs. Os recibos antigos em django_migrations permanecem; o histórico das migrações anteriores continua no Git. Para permissões chamadas diretamente por string, o novo prefixo é `inovalab_app`, por exemplo `inovalab_app.change_servico`.

O build Vercel conserva o lock PostgreSQL e usa a mesma validação antes de fake-initial. A primeira publicação da consolidação exige a preparação/backup/pausa acima; esta entrega não publica nem altera o Neon. Rollback após adoção restaura o backup e a revisão anterior; a migração de ContentTypes é irreversível por comandos de reversão.

## Verificação e futura migração

O baseline anterior passou com 541 testes. Os testes de migrações aposentadas foram substituídos por testes da adoção atual, incluindo igualdade integral dos dados, M2M, microssegundos, permissões e LogEntry. Os testes de fechamento de respostas streaming agora usam o fechamento seguro do cliente Django, preservando transações de teste no PostgreSQL. A captura de SQL identifica a transação pelo estado da conexão, pois PostgreSQL abre BEGIN pelo driver.

Resultados de 07/10/2026:

| Verificação | Comando ou cenário | Resultado |
| --- | --- | --- |
| Sistema independente | `python manage.py check` e `python manage.py makemigrations --check --dry-run` | Sem erros; nenhuma migração pendente de geração |
| Suíte SQLite | `python manage.py test --noinput` | 545 testes passaram |
| Suíte PostgreSQL 16.15 local | Mesmo comando, com DATABASE_URL do ambiente de teste isolado | 545 testes; dois específicos de SQLite ignorados; demais passaram |
| Atualização real | Cópia SQLite atual e PostgreSQL criado pela revisão anterior; comparação integral antes/depois | 21 tabelas preservadas, incluindo IDs, M2M, arquivos, precisão temporal, permissões/grupos e histórico do Admin; somente labels dos ContentTypes e recibos novos mudaram |
| Banco local do desenvolvimento | Backup, adoção com fake-initial e comparação integral | Mesma preservação das 21 tabelas; arquivos media comparados por SHA-256; servidor reiniciado |
| Hospedeiro alternativo | `python manage.py test inovalab_app.tests.portability --settings=inovalab_app.tests.host_settings --noinput` | Seis testes passaram com auth.User, sem Accounts, sob /laboratorio/, no Django 6.1.1 e 5.2.18 |
| Pacote instalável | Wheel instalado em diretório isolado, sem acesso ao código do checkout | Migração nova, carga inicial, validação do esquema, quatro páginas e static passaram no Django 5.2.18 |
| Navegador Chrome | 43 verificações de páginas/fluxos, desktop e largura 360px | Imagens, sidebar/preferência, menu móvel, modal de visita, permissões, perfil, contato simulado e alternativa sem JavaScript passaram; zero erros de JavaScript |

O fluxo de Accounts, eventos e contato foi exercitado com provedores HTTP controlados ou adaptadores de teste. O navegador não enviou mensagens ao provedor real. Backups e evidências locais ficam em `.private/consolidacao/`; downloads e ambientes descartáveis são removidos após a verificação. A depuração do responsável e a validação no ambiente publicado ficam para a próxima etapa, antes da incorporação ao monólito.

A futura incorporação permanece separada: substituir o adaptador/identidade pelo Accounts central, associar autores/responsáveis pelo agrohub_id antigo, e definir a convivência com apps.inovalab/apps.labmaker. Não há transferência de contas nem alteração do monólito nesta consolidação. Ver [diretrizes de migração](../migracao-para-monolito.md).
