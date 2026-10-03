# Módulo 6 — Materiais

Entrega local em 02/10/2026, conforme o [plano simples](../superpowers/plans/2026-10-02-materiais.md). F3 confirmou cadastro simples: administradores mantêm, usuários internos ativos consultam, quantidade não negativa com até 3 casas decimais e unidade informada, categoria/fonte em texto e status disponível/indisponível. Aguardar depuração antes de banners.

## Uso e regras

Após entrar, use **Materiais** ou `/materiais/`. Lista e detalhe são acessíveis a todas as contas internas ativas, incluindo materiais indisponíveis. Somente superusuários ativos ou membros ativos do grupo `Administradores` veem as ações de cadastro/edição; `is_staff` sozinho não permite manutenção. A identidade e seu frontend foram preservados, acrescentando apenas o link.

| Campo | Contrato |
| --- | --- |
| nome | Texto obrigatório, até 150 caracteres; nomes repetidos permitidos |
| categoria | Texto obrigatório, até 100 caracteres; vocabulário livre |
| quantidade | De 0 a 999999999.999, até 12 dígitos totais e 3 casas decimais |
| unidade | Texto obrigatório, até 20 caracteres, por exemplo kg, g, m ou unidade |
| status | `disponivel` ou `indisponivel`; criação padrão disponível |
| fonte | Texto obrigatório, até 150 caracteres; descrição livre da origem |
| versao | Inicial 1; incrementa em cada edição aceita, definida pelo servidor |

Tamanhos, obrigatoriedade dos textos, interpretação de fonte como origem, versão e ausência de exclusão são escolhas de implementação para depuração; não são campos adicionais exigidos pelo PDF. Textos são aparados nas bordas. Zero e status são independentes: cadastrar quantidade zero não torna o material indisponível automaticamente. Alterar unidade não converte a quantidade; o administrador deve corrigir os dois valores juntos se necessário.

| Caminho web | Operação |
| --- | --- |
| `/materiais/` | Lista por nome/ID, paginada em 25 itens |
| `/materiais/novo/` | Cadastro administrativo |
| `/materiais/{id}/` | Detalhe |
| `/materiais/{id}/editar/` | Correção administrativa |

O formulário aceita vírgula decimal em português e também ponto. Precisão excedente, valores negativos, booleanos e números não finitos são rejeitados; não há arredondamento silencioso. A tabela permite rolagem horizontal em telas estreitas, dentro de uma região acessível pelo teclado, preservando a leitura das colunas.

Todas as escritas web exigem CSRF. Versão ausente/inválida na edição retorna 400; formulário inválido comum retorna 200 com erros; versão antiga retorna 409 com orientação para atualizar a página. O formulário não troca a versão antiga pela atual silenciosamente, e nenhuma parte da correção rejeitada é gravada.

## API interna

Autenticação por sessão Django, com CSRF nas escritas. Uma credencial Bearer de integrador não substitui a sessão. Não há endpoint externo de materiais nem acesso por credencial AgroHub neste módulo.

| Método/caminho | Operação |
| --- | --- |
| `GET /api/v1/materiais/` | Lista paginada em 25, com `count`, `next`, `previous`, `results` |
| `POST /api/v1/materiais/` | Criar; 201 |
| `GET /api/v1/materiais/{id}/` | Detalhe; 200 |
| `PUT /api/v1/materiais/{id}/` | Informar seis campos do cadastro e versão; 200 |
| `PATCH /api/v1/materiais/{id}/` | Informar campos desejados e versão; 200 |

Corpos exclusivamente JSON, campos desconhecidos/`id` rejeitados. Na criação, `versao` é proibida; `status` pode ser omitido. PUT exige os seis campos, incluindo status; PATCH preserva campos omitidos. HEAD/OPTIONS disponíveis; DELETE retorna 405 e preserva o cadastro. Para retirar um material de disponibilidade, editar o status.

Exemplo de cadastro:

```json
{
  "nome": "Filamento PLA",
  "categoria": "Impressão 3D",
  "quantidade": "1.125",
  "unidade": "kg",
  "status": "disponivel",
  "fonte": "Compra do laboratório"
}
```

A resposta contém os seis campos, `id` e `versao`. Quantidade sempre é uma string com 3 casas, como `"1.125"` ou `"8.000"`. Entrada JSON aceita string decimal com ponto ou número; vírgula decimal é exclusiva do formulário. Preferir string no consumidor evita perda de precisão antes do envio. O parser do servidor mantém os dígitos decimais do número JSON até a validação. [DecimalField do DRF](https://www.django-rest-framework.org/api-guide/fields/#decimalfield).

Exemplo de correção com PATCH:

```json
{"quantidade": "8", "versao": 1}
```

Use a versão obtida na consulta. Ela deve ser um inteiro JSON positivo, não string, booleano ou decimal. Intervalo aceito para edição: 1 a 9223372036854775806. Reenviar depois de editar exige consultar a nova versão.

| Resposta | Situação |
| --- | --- |
| 400 | Campos, quantidade, versão ou JSON inválidos |
| 403 | Sessão ausente/inativa, escrita sem papel ou CSRF inválido |
| 404 | Material inexistente ou página de lista inexistente |
| 409 | `{"detail": "…", "code": "versao_desatualizada"}`; consultar e repetir a decisão |
| 405 | Método não oferecido |
| 415 | Corpo de escrita diferente de JSON |

## Persistência e concorrência

`Material` tem checks de quantidade não negativa/limite superior, status válido e versão positiva. Modelo/serviço validam precisão antes de persistir, preservando `Decimal` antes da conversão do Django. [DecimalField do Django](https://docs.djangoproject.com/en/6.0/ref/models/fields/#decimalfield).

`save_material` verifica administrador e campos públicos, valida o cadastro inteiro e executa um único UPDATE condicionado ao ID/versão esperada. Duas edições da mesma versão produzem um único vencedor, sem misturar nome, unidade ou quantidade. Não depende de `select_for_update()` no SQLite. Versão inicial/ID não são alteráveis por payload; modelo não está registrado no Django Admin para contornar o serviço.

Este é um cadastro com correção direta, sem histórico de movimentações ou valores anteriores. Tarefas/reservas não consomem materiais, não há empréstimos/devoluções nem conversão entre unidades. Essas funcionalidades precisam de requisitos próprios se forem solicitadas posteriormente.

## Verificação executada

Python 3.14.3, Django 6.1.1 e DRF 3.18.1; sem dependências novas. Migração aditiva `materiais.0001_initial` aplicada no banco local.

```powershell
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py test materiais.tests
& .\venv\Scripts\python.exe manage.py test
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\venv\Scripts\python.exe -m pip check
git diff --check
```

40 testes do módulo: 12 serviços, 1 concorrência, 17 API e 10 web. Suíte completa de 234 testes passou. Check, migrações, dependências e diff sem pendências. Experimento removendo a condição de versão fez o teste de conexões reais falhar; proteção restaurada antes da verificação final.

A revisão independente executou 37 testes e encontrou um Important: perda de precisão no parser JSON/conversão de float no domínio. Corrigido em uma passada com três regressões RED/GREEN e suíte completa: `0.10000000000000001` e `999999999.99900001` não são mais aceitos por arredondamento; edição rejeitada preserva todos os dados. Nenhum Critical ou Minor encontrado. Produção, navegador e documentação foram deixados pelo revisor para a validação do executor/ambiente correspondente.

Chrome verificou cadastro com vírgula decimal, correção 10→8, rejeição de negativo, API com CSRF, número JSON de precisão excedente 400, versão antiga web/API 409, zero/indisponibilidade independentes, máximo exato via API, consulta por staff sem papel e escrita negada. Layout de 360 px sem rolagem horizontal da página; tabela rolável por teclado, foco visível. Nenhuma exceção JavaScript da aplicação. Apenas dois materiais, duas contas e suas sessões de teste foram removidos por IDs/prefixos conhecidos; navegador e servidor encerrados.

## Depuração restante

1. Exercitar categorias, fontes e unidades reais; confirmar os limites e a obrigatoriedade dos campos com a operação do laboratório.
2. Abrir duas abas e editar o mesmo material; validar a decisão de consultar novamente após conflito de versão.
3. Verificar os consumidores futuros e a representação decimal, incluindo valores próximos aos limites, nomes repetidos e listas com várias páginas.
4. Validar carga, banco/hospedagem de produção e recuperação de dados no ambiente escolhido. SQLite local foi testado; PostgreSQL não foi executado nesta entrega.
5. Se surgirem necessidades de entradas/saídas, empréstimos, conversão ou auditoria, especificar movimentações antes de alterar o cadastro. Aguardar sua depuração deste módulo antes de banners.
