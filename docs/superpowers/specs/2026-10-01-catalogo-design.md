# Módulo 2 — Catálogo

01/10/2026 • Especificação preparada para revisão. O responsável autorizou avançar para o próximo módulo, preservar o frontend de identidade e simplificar as próximas telas do MVP. Também assumiu a execução dos testes e confirmou Q12 para catálogo: administradores do laboratório mantêm; todos os usuários internos ativos consultam. Esta especificação detalha RF08–RF11, RF23/RF24, RN05/RN12, UC06 e CT20/CT24. Os demais detalhes abaixo são a proposta técnica a revisar antes da implementação.

## Objetivo e limites

Disponibilizar serviços, equipamentos e espaços para consulta e manutenção, preparando as referências que tarefas e agenda utilizarão nas próximas entregas. Entregar uma interface simples e endpoints autenticados, com as mesmas regras de campos e autorização.

Somente catálogo nesta etapa. Tarefas, reservas, conflitos de agenda, integração externa, materiais e banners continuam para módulos posteriores. Preservar as páginas atuais de login e identidade; acrescentar apenas um acesso ao catálogo na página privada.

## Abordagem

Recomendação: app `catalogo` com três modelos explícitos, formulários/templates Django e API DRF. Modelos separados preservam os campos distintos do PDF e permitem referências claras nas etapas de tarefas e agenda.

Alternativas: manter o catálogo somente no Django Admin economiza telas, mas não atende à manutenção por administrador de negócio sem acesso técnico. Um modelo único com tipo e campos opcionais reduz classes, mas mistura capacidade de espaço com serviços/equipamentos e torna as referências futuras menos claras. A interface própria simples e três modelos atendem ao MVP com a base já existente.

## Permissões

**Decisão confirmada pelo responsável em Q12:** todos os usuários internos ativos consultam; somente administradores do laboratório mantêm serviços, equipamentos e espaços. Essa decisão não define automaticamente as permissões futuras de materiais ou banners.

A escrita usa `accounts.policies.is_business_admin`: superusuário ativo ou membro ativo de `Administradores`. `is_staff` isolado não concede manutenção. O administrador do laboratório pode operar pelo frontend/API sem obter gestão técnica de contas. Conta inativa ou sessão encerrada perde acesso nas próximas requisições.

Não ampliar o acesso de usuários/grupos no Django Admin nem expor catálogo publicamente. A autenticação das integrações externas será definida em sua própria etapa.

## Dados e validações

| Modelo | Campos públicos | Valores e validação |
| --- | --- | --- |
| `Servico` | `id`, `nome`, `descricao`, `status` | Nome obrigatório, até 150 caracteres; descrição opcional; status `disponivel` ou `indisponivel` |
| `Equipamento` | `id`, `nome`, `descricao`, `status` | Nome obrigatório, até 150 caracteres; descrição opcional; status `disponivel`, `ocupado` ou `indisponivel` |
| `Espaco` | `id`, `nome`, `capacidade_maxima_de_pessoas`, `status` | Nome obrigatório, até 150 caracteres; capacidade inteira de 1 a 2.147.483.647; mesmos status de equipamento |

IDs gerados pelo banco. Aparar espaços nas extremidades do nome e rejeitar nome vazio. Não tornar nomes únicos por inferência: equipamentos ou espaços diferentes podem ter a mesma denominação; a identidade é o ID. Serviço também utiliza ID, sem assumir unicidade do nome no levantamento.

Descrição ausente é string vazia. Não acrescentar descrição ao espaço: esse campo não consta no PDF. Capacidade positiva é a proposta já identificada nos documentos; exigir validação de mínimo/máximo no modelo e restrição de banco. Status utiliza escolhas fechadas, validado também no servidor. Novo cadastro começa `disponivel`, permitindo escolher outro status no formulário/API.

Os estados ocupado/indisponível são cadastrados manualmente nesta etapa. Eles não calculam ocupação temporal nem criam/cancelam reservas. Q06 sobre agenda e disponibilidade por período permanece para o módulo de agenda.

Não oferecer exclusão física nesta entrega: retirar um cadastro de uso significa alterar seu status para `indisponivel`, preservando ID e dados. API DELETE retorna 405 para usuário autorizado, após a verificação de autenticação/CSRF. Nas etapas futuras, vínculos de tarefas/reservas usarão proteção contra exclusão, conforme RN12; não criar relações fictícias agora.

## Serviços iniciais

Uma migração de dados cria os onze serviços da seção 6 do arquivo 01, mantendo nomes e descrições transcritos do PDF. Linhas sem descrição permanecem vazias. Estado inicial proposto: `disponivel`.

- Identidade Visual
- Impressão Sublimática
- Criação de Banners
- Impressão 3D
- Corte a laser
- Plotter de recorte
- Óculos de realidade virtual
- Scanner 3D manual
- Plotter de Impressão
- Consultoria técnica
- Uso do espaço

Não criar equipamentos/espaços demonstrativos nem reclassificar serviços pelo nome. Cada serviço inicial tem uma chave técnica estável, única e não editável, fora dos formulários e do contrato público. Assim, renomear um serviço ou alterar descrição/status não faz a carga repetida recriá-lo ou sobrescrevê-lo.

Disponibilizar `manage.py carregar_servicos_iniciais` para repetir a carga com segurança. Carga e migração utilizam os mesmos valores iniciais congelados e chave estável; criar somente registros ausentes, sem atualizar cadastros existentes. A reversão da migração de dados não apaga serviços. Toda a carga deve ocorrer em transação.

## Interface simples

Criar uma base própria do catálogo com cabeçalho, links **Serviços**, **Equipamentos**, **Espaços** e **Minha conta**. Usar CSS mínimo para legibilidade, mensagens, formulários e largura móvel. Preservar o estilo atual das páginas de identidade.

Cada categoria tem lista, detalhe, cadastro e edição. Listas exibem nome e status; espaços também mostram capacidade. Detalhe apresenta todos os campos. Somente o ator autorizado vê **Novo** e **Editar**, com a mesma restrição aplicada nas views. Alterar para indisponível ocorre no formulário de edição, sem fluxo adicional de exclusão.

Formulários com labels em português, erros por campo, mensagens de sucesso, CSRF e envio por POST; operações de GET não alteram dados. Paginar listas em 25 registros, ordenadas por nome e ID. Sem busca avançada, cartões decorativos, animações, dashboards ou JavaScript obrigatório nesta etapa. Interface utilizável por teclado e a 360 px, com nomes longos quebrados.

| Categoria | Lista/cadastro | Detalhe/edição |
| --- | --- | --- |
| Serviços | `/catalogo/servicos/`, `/catalogo/servicos/novo/` | `/catalogo/servicos/{id}/`, `/catalogo/servicos/{id}/editar/` |
| Equipamentos | `/catalogo/equipamentos/`, `/catalogo/equipamentos/novo/` | `/catalogo/equipamentos/{id}/`, `/catalogo/equipamentos/{id}/editar/` |
| Espaços | `/catalogo/espacos/`, `/catalogo/espacos/novo/` | `/catalogo/espacos/{id}/`, `/catalogo/espacos/{id}/editar/` |

Sem sessão, páginas redirecionam ao login. Sem permissão de escrita, acesso direto ao cadastro/edição retorna 403. ID inexistente retorna 404. Erro de validação apresenta o formulário sem salvar; sucesso redireciona ao detalhe.

## API

Usar sessão Django, CSRF, permissões explícitas e resposta JSON. As operações de escrita de web/API compartilham validação de modelo e persistência; a política de autorização também é comum. Os contratos são versionados e não incluem a chave técnica dos serviços iniciais.

| Endpoint | Operações |
| --- | --- |
| `/api/v1/servicos/` e `/api/v1/servicos/{id}/` | GET lista/detalhe; POST cadastro; PUT/PATCH edição |
| `/api/v1/equipamentos/` e `/api/v1/equipamentos/{id}/` | Mesmas operações |
| `/api/v1/espacos/` e `/api/v1/espacos/{id}/` | Mesmas operações |

Campos por entidade seguem a tabela de dados. `id` é somente leitura. Não aceitar edição da chave técnica dos serviços iniciais. PUT exige campos obrigatórios do cadastro; PATCH altera somente os campos fornecidos. Falha não aplica alteração parcial.

Listagem paginada: `count`, `next`, `previous`, `results`; 25 itens por página e parâmetro `page`. Detalhe retorna o objeto diretamente. GET retorna 200; POST válido, 201; PUT/PATCH válidos, 200; validação, 400 com erros por campo; sem sessão ou permissão, 403; ID ausente, 404. DELETE não é suportado; CSRF inválido pode produzir 403 antes da verificação do método. HEAD/OPTIONS seguem DRF, também com autenticação.

Não adicionar autenticação por token, login API, CORS público ou consumidores externos nesta etapa.

## Entrega e testes pelo responsável

Preparar testes automatizados relevantes de modelos, carga, permissões e fluxos web/API, sem executá-los. Essa instrução do responsável prevalece sobre os ciclos de execução de testes das skills. Não iniciar navegador para testar. Revisar código e documentação estaticamente e informar claramente que os testes não foram executados pelo agente.

Documentar os comandos de instalação já existentes, `migrate`, `carregar_servicos_iniciais` e servidor. Não apagar o SQLite nem criar contas/pessoas fictícias no banco do responsável. As migrações desta nova etapa serão aplicadas por ele como parte do roteiro.

Roteiro mínimo a fornecer na entrega:

1. Aplicar migrações, confirmar os onze serviços e repetir a carga sem duplicação.
2. Renomear um serviço inicial, editar descrição/status e repetir a carga: preservar ID e edições.
3. Cadastrar e editar as três entidades pela interface/API, com ator autorizado.
4. Conferir listas, detalhes e paginação; confirmar os campos do JSON.
5. Tentar nome vazio, status inválido e capacidade zero/negativa: rejeitar sem alteração parcial.
6. Conferir escrita negada para usuário sem papel autorizado, inclusive por URL/requisição direta; `is_staff` sozinho não libera manutenção.
7. Conferir ausência de sessão, conta inativa, CSRF e logout; nenhum deles permite alterar catálogo.
8. Indisponibilizar cadastro e confirmar preservação do ID; DELETE não apaga dados.
9. Verificar teclado, nomes longos e layout a 360 px, preservando a interface de identidade.

Comandos previstos para execução pelo responsável, após implementação:

```powershell
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py carregar_servicos_iniciais
& .\venv\Scripts\python.exe manage.py test catalogo
& .\venv\Scripts\python.exe manage.py test
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Os comandos de catálogo acima são previstos, ainda não disponíveis no código. Não registrar resultados de testes como aprovados sem a execução pelo responsável. Concluir somente este módulo e aguardar sua depuração antes de tarefas.
