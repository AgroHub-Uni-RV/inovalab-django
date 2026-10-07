# Módulo 5 — Recebimento de reservas externas

**Atualização de 07/10/2026:** espaços foram removidos do catálogo/modelos. Reenvios idempotentes anteriores continuam funcionando com os recibos originais; novos pedidos de espaços continuam rejeitados. Ver [remoção de espaços](11-remocao-espacos.md).

Entrega local em 02/10/2026, com [plano simples](../superpowers/plans/2026-10-02-integracoes.md). O responsável escolheu preparar a API no InovaLab com credencial própria e proteção contra pedidos duplicados. Este módulo prepara o recebimento; não conecta nem modifica uma instalação real do AgroHub. Aguardar depuração antes de materiais.

## Administração

Entre com superusuário ativo ou conta ativa do grupo `Administradores` e abra **Integrações** (`/integracoes/`). Não exige `is_staff`. Usuários comuns e staff sem o papel recebem 403; sem sessão, as telas redirecionam ao login. Todas as escritas web exigem CSRF.

1. Use **Novo integrador** e informe o nome do sistema, único e com até 100 caracteres.
2. Copie a credencial da tela de criação. Ela é exibida somente nessa resposta; depois não pode ser recuperada. As respostas que exibem segredo usam `Cache-Control: no-store, private` e `Referrer-Policy: no-referrer`.
3. Entregue a credencial ao responsável pelo consumidor, que a enviará no cabeçalho `Authorization`.
4. **Gerar nova credencial** invalida a anterior, preservando a identidade do integrador e os pedidos recebidos. A confirmação GET não altera dados; somente POST executa a renovação.
5. Em **Editar integrador**, desmarcar **Integrador ativo** revoga a credencial. Reativar não recupera o segredo anterior: é necessário gerar uma credencial nova.

As telas mostram lista/detalhe, formulário, confirmação e pedidos recebidos, com paginação de 25. Edição e renovação exigem a versão do integrador; versão antiga recebe 409 e não sobrescreve o estado atual. Não há exclusão física de integrador/pedido pela interface.

| Caminho | Uso |
| --- | --- |
| `/integracoes/` | Lista administrativa |
| `/integracoes/novo/` | Criação e credencial inicial |
| `/integracoes/{id}/` | Estado e ações |
| `/integracoes/{id}/editar/` | Nome/ativo |
| `/integracoes/{id}/credencial/` | Renovação confirmada |
| `/integracoes/{id}/pedidos/` | Chave externa, requerente externo e reserva; canceladas indicadas sem link operacional |

O detalhe da reserva na agenda mostra integrador, pedido e requerente externos. Eventos da criação usam `Integração: <nome>` como ator, sem criar conta interna ou atribuir falsamente a criação a um administrador.

## Autenticação externa

Formato: `Authorization: Bearer inovalab_<uuidhex>.<segredo>`. O segredo é gerado com 32 bytes aleatórios (`secrets.token_urlsafe(32)`); o banco guarda somente SHA-256 do token completo, comparado com `secrets.compare_digest`. O UUID identifica o cliente e permanece estável na renovação. Não é JWT/OAuth, e não representa o login de uma pessoa.

Referências: [autenticação customizada no DRF](https://www.django-rest-framework.org/api-guide/authentication/#custom-authentication), [segredos Python](https://docs.python.org/3/library/secrets.html).

Sem cabeçalho válido ou com credencial revogada/inativa, a API externa retorna 401 com `WWW-Authenticate: Bearer realm="integracoes"`. Uma sessão interna não substitui a credencial externa; uma credencial externa não autentica as APIs internas por sessão. Credenciais não são aceitas por parâmetros da URL. Chamadas autenticadas pelo cabeçalho não exigem CSRF; a administração por sessão continua exigindo.

## Catálogo para mapear alvos

`GET /api/v1/integracoes/catalogo/?categoria=servico|equipamento`, autenticado pelo mesmo token.

A categoria é obrigatória; a lista paginada em 25 itens devolve apenas `id`, `categoria`, `nome` de objetos reserváveis. Indisponíveis são excluídos; `ocupado` manual não bloqueia reservas futuras. IDs são internos ao InovaLab e interpretados na categoria. IDs numéricos iguais em tabelas diferentes não representam o mesmo objeto. O endpoint só permite leitura e não expõe reservas, credenciais, histórico ou dados de contas internas.

## Recebimento

`POST /api/v1/integracoes/agendamentos/` aceita exclusivamente JSON e estes oito campos:

```json
{
  "id_externo": "pedido-123",
  "requerente_id": "pessoa-45",
  "requerente": "Nome do solicitante",
  "motivo": "Produzir protótipo",
  "categoria": "servico",
  "objeto": 1,
  "inicio": "2026-11-01T14:00:00-03:00",
  "fim": "2026-11-01T15:00:00-03:00"
}
```

Use um `objeto` real obtido no catálogo. `id_externo` identifica o pedido no sistema consumidor; `requerente_id` identifica a pessoa nesse sistema. São strings opacas, obrigatórias, case-sensitive, até 150 caracteres. O nome do requerente também tem limite de 150; motivo é obrigatório para serviços/equipamentos. Textos são aparados nas bordas. O ID de objeto é inteiro JSON positivo, dentro do intervalo de 64 bits; strings, booleanos e decimais são rejeitados.

Início/fim exigem ISO8601 com fuso, fim posterior ao início. UTC é aceito; horários são normalizados em UTC antes da operação de agenda e da comparação de conteúdo. Serviços/equipamentos mantêm exclusividade por recurso; visitas usam exclusividade provisória por intervalo e devem ocorrer no mesmo dia de Brasília. Preservam-se intervalos adjacentes permitidos, indisponibilidade, datas passadas e virada de dia do módulo 4. Origem/cliente são determinados pela credencial; não aceitar esses campos, versão inicial, autor, FKs internas ou outros desconhecidos.

Primeiro recebimento bem-sucedido retorna 201:

```json
{
  "id": 1,
  "id_externo": "pedido-123",
  "repetido": false,
  "cancelado": false,
  "versao": 1
}
```

Mesmo cliente/chave/conteúdo retorna 200 com o mesmo `id` e `repetido: true`. O conteúdo comparado inclui requerente externo, nome, motivo, categoria/objeto e intervalo; textos aparados, ordem de propriedades JSON e fusos que representam o mesmo instante não geram diferenças.

Mesma chave com conteúdo diferente retorna 409 `idempotencia_conflitante`; a chave é independente por cliente. Uma renovação de credencial conserva essa identidade e a idempotência. Pedidos que falham na validação/conflito não consomem a chave nem deixam reserva/pedido parcial.

Após edição ou cancelamento pelo administrador, reenviar o pedido original retorna o mesmo ID com `versao` e `cancelado` atuais. Não altera/restaura/recria a reserva, nem depende da disponibilidade atual do objeto. Para solicitar outro período como nova reserva, o consumidor deve usar um novo identificador de pedido. Reenvio não é um mecanismo de edição.

| Resposta | Situação |
| --- | --- |
| 201 | Nova reserva e vínculo externo |
| 200 | Reenvio idêntico; mesmo ID, estado atual |
| 400 | Campo/fuso/intervalo/filtro inválido ou objeto indisponível/inexistente |
| 401 | Credencial ausente, inválida ou revogada |
| 409 `idempotencia_conflitante` | Chave persistida com outro conteúdo |
| 409 `horario_ocupado` | Outro pedido/reserva no mesmo objeto/período |
| 409 `agenda_ocupada` | SQLite ocupado; tentar novamente com mesma chave/conteúdo |
| 405 | Método não oferecido; reservas externas só POST, catálogo só GET |
| 415 | Corpo diferente de JSON |

Conflitos 409 têm `detail` e `code`. Não há lista/detalhe/histórico/edição/cancelamento externo de reservas, nem acesso externo ao cadastro administrativo de integradores.

## Persistência e concorrência

`ClienteIntegracao` guarda identidade/estado/digest/versão; `PedidoIntegracao` guarda cliente, `id_externo`, `requerente_id`, digest do conteúdo, reserva e instante. Unicidade `(cliente,id_externo)` e OneToOne protegido com a reserva; referências não podem ser apagadas em cascata. O pedido não duplica nome/motivo num JSON adicional.

Na transação de recebimento, o primeiro SQL é UPDATE sem mudança de estado do cliente. Depois são revalidados ativo e digest da credencial; assim renovação/desativação ocorrida desde a autenticação é detectada. Só então é consultada a chave. Se for nova, o núcleo compartilhado da agenda bloqueia o alvo e verifica os mesmos conflitos antes de gravar reserva, evento e pedido juntos. Falha em gravar pedido reverte os três. Ordem de bloqueio: cliente→alvo.

O núcleo privado da agenda é chamado exclusivamente pela fachada administrativa ou adaptador autenticado. A fachada `save_booking` verifica conta ativa e aplica papel administrativo nas alterações; não existe conta técnica com privilégios internos criada para simular o integrador. Chamadas internas e futuras entradas devem preservar essa autorização antes de usar o núcleo.

SQLite e conexões reais foram verificados; a proteção por UPDATE da linha também foi exercitada com experimento de regressão retirando o bloqueio, que fez o teste falhar. O SQLite serializa escritores, portanto conflitos transitórios podem exigir reenvio. PostgreSQL/carga/produção não foram validados nesta etapa. [Transações SQLite](https://www.sqlite.org/lang_transaction.html).

## Verificação

Python 3.14.3, Django 6.1.1 e DRF 3.18.1; sem dependências novas. Migração local aplicada de forma aditiva.

```powershell
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py test integracoes.tests
& .\venv\Scripts\python.exe manage.py test
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\venv\Scripts\python.exe -m pip check
git diff --check
```

**35 testes do módulo passaram:** 13 serviços, 4 concorrência, 10 API, 8 web. **Suíte completa de 194 passou**, sem falhas. Check, drift, dependências e diff sem pendências. A revisão independente única não encontrou Critical/Important/Minor; executou adicionalmente 14 testes de API/concorrência com sucesso.

Chrome: cadastro e cópia única de credencial, envio 201/reenvio 200/conflitos 409, catálogo, sessão sem token 401, origem na agenda, pedidos recebidos, renovação com token anterior 401 e reenvio preservado, cancelamento local/reenvio sem recriação, revogação 401, usuário staff 403, teclado e 360 px sem rolagem horizontal da página. Nenhuma exceção JavaScript da aplicação. Dados/segredos de teste ficaram em scratch ignorado; removidos somente um pedido/uma reserva/dois eventos/um cliente/um serviço/duas contas e suas sessões por IDs/prefixo conhecidos. Navegadores e servidor de teste encerrados.

## Limites e depuração restante

1. Validar o payload, mapeamento de IDs e semântica do reenvio com o responsável pelo AgroHub e implementar o consumidor nesse sistema; não foi usado contrato/servidor externo real nesta entrega.
2. Exercitar carga e reenvios simultâneos no ambiente/banco que vier a ser escolhido, incluindo renovação/desativação simultânea, diferentes clientes e perda de resposta.
3. Testar credencial perdida, reativação seguida de geração nova, pedidos cancelados/editados localmente e comportamento do consumidor diante dos códigos de conflito.
4. Confirmar hospedagem e HTTPS, gestão/entrega do segredo, retenção dos dados externos e eventuais validade automática/limitação de taxa antes de publicação. Essas políticas ainda não estão implementadas/aprovadas.
5. Confirmar separadamente edição/cancelamento externos, notificações/webhooks, sincronização e migração histórica. Esta entrega cobre recebimento de novas reservas e reenvio, preservando os módulos anteriores.

## Correção de categorias — 06/10/2026

Categorias novas: `servico`, `equipamento`, `visita`. Para visita, envie `id_externo`, `requerente_id`, `requerente`, `categoria`, `inicio`, `fim`; omita `objeto` e `motivo`. Esses identificadores são metadados do adaptador e não campos preenchidos no formulário interno. Visitas não têm entrada no catálogo externo. Motivo/objeto são rejeitados para visita, mesmo vazios. Observações continuam fora do contrato externo.

`espaco` retorna 400 para novos pedidos, independentemente da restrição administrativa do catálogo. Reenvios idênticos de pedidos antigos de espaços conservam idempotência, retornando 200 com o ID original e sem renovar a reserva. A representação histórica da categoria só é aceita para esse reenvio. Resultados de verificações anteriores acima são registros históricos.
