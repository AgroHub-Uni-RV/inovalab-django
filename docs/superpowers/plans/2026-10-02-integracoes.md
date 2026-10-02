# Plano simples — Recebimento de reservas externas

> Execução direta com `executing-plans`, conforme fluxo autorizado. Somente módulo5; aguardar depuração antes de materiais.

**Objetivo:** preparar o InovaLab para receber reservas do AgroHub/futuros sistemas, com credencial própria, identidade externa e reenvio sem duplicação. O responsável confirmou preparar primeiro a API; conexão a um AgroHub real ainda não está disponível.

**Arquitetura:** app `integracoes`, `ClienteIntegracao` e `PedidoIntegracao`; autenticação Bearer por token aleatório cujo SHA-256 é armazenado. Integrador não vira conta interna. Adaptador autenticado chama o núcleo de persistência da agenda, preservando conflitos, transação e eventos. Sem dependências novas, SQLite local e checkout ativo `feat/integracoes`, derivado de `926b925`.

**Fontes:** UC09, RF14–RF16/RF21–RF24, CT16–CT18/CT28–CT29, Q07. API de recebimento/credencial própria/idempotência escolhidas em F3; payload e limites abaixo são contrato de implementação para depuração.

## Contrato e limites

- Somente administradores de negócio/superusuários ativos gerenciam clientes por sessão/CSRF em `/integracoes/`, `novo/`, `{id}/`, `{id}/editar/`, `{id}/credencial/`, `{id}/pedidos/`; listas paginadas25. `is_staff` sozinho403. A página inicial/menu recebe link apenas para administradores.
- Cliente: nome único até100, UUID público imutável, ativo, digest da credencial, versão positiva, criador/data. Criação gera token uma vez; renovação invalida anterior. Desativação apaga digest: reativar exige gerar credencial nova. Token nunca é persistido em texto, URL, mensagens/sessão ou listagem; resposta única com `Cache-Control: no-store, private` e `Referrer-Policy: no-referrer`.
- Cadastro/edição/renovação de cliente verifica autorização; operações existentes exigem versão, stale409. Não há exclusão física de cliente/pedido/reserva externa pelo módulo.
- `Authorization: Bearer inovalab_<uuidhex>.<segredo>`; segredo com32bytes via `secrets.token_urlsafe(32)`, comparação constante do SHA-256. Cabeçalho ausente/inválido/revogado401 com WWW-Authenticate. Sessão interna não autentica essa API, nem token externo autentica APIs internas.
- `POST /api/v1/integracoes/agendamentos/` aceita apenas JSON: seis campos públicos da agenda, mais `id_externo` e `requerente_id` (strings obrigatórias até150). IDs externos são opacos, case-sensitive e sem espaços nas bordas. Alvo usa ID interno na categoria, objeto estritamente inteiro; timestamps ISO8601 com fuso. Não aceitar origem/cliente/autor/versão/FKs internas.
- Criação201; repetição idêntica200, com `{id, id_externo, repetido, cancelado, versao}`. Reenvio após edição/cancelamento local retorna mesmoID e estado/versão atuais; não restaura nem recria. Mesma chave com conteúdo diferente409 `idempotencia_conflitante`; mesmoID em clientes diferentes é independente.
- Canonicalizar textos trim, datetimes UTC e ordem JSON antes de SHA-256. Pedido guarda cliente, chave, requerente externo, digest, FK OneToOne PROTECT e data; unicidade(cliente,id_externo). Não duplicar nome/motivo em JSON de auditoria do pedido.
- Primeira consulta dentro da transação é UPDATE sem mudança do cliente: bloqueia escritor SQLite/linha no PostgreSQL antes de consultar chave. Revalidar ativo/digest após bloqueio; chamar núcleo da agenda e salvar pedido na mesma transação. Reenvio já persistido não depende da disponibilidade atual do objeto. Busy/locked409 recuperável; nunca deixar reserva/evento sem pedido em falha. Ordem cliente→alvo, todas as entradas de integração seguem isso.
- `GET /api/v1/integracoes/catalogo/?categoria=servico|equipamento|espaco` fornece apenas `id,categoria,nome` de objetos reserváveis, paginados25; indisponíveis excluídos, ocupado manual permitido. Sem lista/detalhe/histórico de reservas privadas ou credenciais.
- Origem e ID do requerente/pedido aparecem no detalhe administrativo da agenda; evento tem ator nome `Integração: <nome>`, sem conta local/criador falso. Manter política administrativa existente nas consultas.
- Fora desta etapa: edição/cancelamento externos, webhooks, sincronização bidirecional, migração histórica, OAuth/JWT/SSO, validade automática/limitação de taxa, implantação e verificação em AgroHub real/PostgreSQL. TLS e gestão do segredo precisam ser configurados antes de usar fora do ambiente local.

## 1. Domínio, credenciais e idempotência

**Arquivos:** `integracoes/{apps,models,credentials,services,selectors}.py`, migração inicial; `agenda/services.py`, settings; `integracoes/tests/{test_services,test_concurrency}.py`.

**Interfaces:** `create_client(*, actor, name) -> (client, token)`; `update_client(*, actor, client_id, data, expected_version)`; `rotate_credential(*, actor, client_id, expected_version) -> (client,token)`; `authenticate_token(token) -> IntegrationPrincipal`; `receive_booking(*, principal, data) -> (booking,pedido,repeated)`; `visible_clients(actor)`. Núcleo `_save_booking(*,actor,actor_name,data,booking_id=None,expected_version=None)` continua privado; `save_booking` administrativo mantém autorização. Evento aceita actorNone com nome explícito, apenas no adaptador autenticado.

- [x] RED: digest/rotação/desativação/reativação, sem conta interna; autorização/version; três alvos; chave por cliente, normalização/fuso, reenvio após alterações, protegido/indisponível/conflito; falha ao salvar pedido reverte reserva/evento.
- [x] Implementar e GREEN `manage.py test integracoes.tests.test_services agenda.tests`.
- [x] Conexões reais: mesma chave/mesmo alvo e mesma chave/alvos diferentes não duplicam; chave diferente/mesmo intervalo conflita; primeiroSQLbloqueia cliente. RED de retirada da proteção e GREEN `test integracoes.tests.test_concurrency`.
- [x] Suíte completa/check/drift; commit `feat (integracoes): adiciona credenciais e recebimento idempotente de reservas.`.

## 2. API e administração simples

**Arquivos:** `integracoes/{authentication,serializers,api,api_urls,forms,views,urls}.py`, templates/testes web/API; URLs, navegação, detalhe da agenda.

- [x] RED: autenticação real por header, 401/revogação/CSRF por sessão, não aceitar sessão na API externa/token na interna; JSON estrito,201/200/409, campo ausente/fuso, privacidade/métodos405, catálogo paginado; telas403/CSRF/version, segredo uma vez/no-store, histórico do pedido/origem.
- [x] Implementar e GREEN; suíte completa; commit `feat (integracoes): disponibiliza API externa e gestão de integradores.`.

## 3. Entrega

- [x] Migração aditiva e Chrome com fixtures identificadas: cadastro/token único, envio/reenvio/conflito por fetch, origem na agenda, catálogo, renovação/revogação e usuário negado; teclado/360px; limpar somente fixtures conhecidas.
- [x] Revisão independente única; Important/Critical uma passada RED/GREEN e suíte; menores registrados.
- [x] `test`, `check`, drift, `pip check`, `git diff --check`; guia `docs/modules/05-integracoes.md`, README e docs01/02/03/04/05. Não alegar integração real implantada; comandos/limites/depuração explícitos.
- [x] Commit de documentação e limpeza do scratch deste plano; manter branch local e aguardar responsável antes de materiais. Sem push/merge automático.

## Foco de revisão

1. Rotação/desativação entre autenticação e gravação não aceita identidade revogada; histórico/idempotência não atravessam clientes.
2. Transação completa: falha no pedido reverte reserva/evento; dois alvos na mesma chave não causam duas reservas.
3. Reenvio retorna reserva cancelada/modificada sem reabrir e sem depender de objeto atualmente disponível; UTC equivalente versus instante distinto na hora histórica repetida.
4. Token nunca aparece em páginas posteriores, dados armazenados ou URLs; erro/auth não vaza detalhes privados. APIs internas permanecem por sessão.
5. Cliente antigo/rascunho não sobrescreve ativo/digest ao renovar/editar; catálogo só leitura, consulta de pedidos só administrador.

Referências primárias: [autenticação customizada DRF](https://www.django-rest-framework.org/api-guide/authentication/#custom-authentication), [segredos Python](https://docs.python.org/3/library/secrets.html), [transações SQLite](https://www.sqlite.org/lang_transaction.html).

## Registro final de decisões e verificação

- Plano direto e contrato próprio seguem o fluxo autorizado e a escolha F3 de recebimento/credencial/idempotência. Custo: validar campos, IDs e semântica do reenvio com o consumidor real.
- SQLite e checkout ativo `feat/integracoes`, derivados da agenda entregue. Custo: implantação, PostgreSQL e instalação real do AgroHub ainda não verificados.
- Núcleo privado da agenda compartilhado pela fachada administrativa e pelo adaptador autenticado; ator externo nulo com nome de origem explícito. Custo: manter autorização nas entradas que chamam esse núcleo.
- Registros de execução em PowerShell substituem os auxiliares Bash. Custo: registro manual das decisões e resultados.

Verificação final: 35 testes de integrações (13 serviços, 4 concorrência, 10 API, 8 web); suíte completa de 194 testes passou em 14,737 s. `check`, migrações pendentes, dependências e espaços no diff sem problemas. Experimento retirando o bloqueio provocou falha no teste correspondente; implementação restaurada antes dos testes finais.

Revisão independente de `926b925..35092e8`: nenhum achado Critical/Important/Minor; mais 14 testes de API/concorrência passaram. Nenhum achado menor adiado neste módulo. A limitação histórica de horário de verão da API interna da agenda permanece documentada no módulo 4.

Chrome verificou cadastro, segredo único, envio/reenvio/conflitos, catálogo, origem/pedidos, renovação/revogação, cancelamento sem recriação, usuário negado, teclado e 360 px. Removidas apenas as fixtures próprias por IDs/prefixos conhecidos; servidor e navegadores encerrados. Guia do módulo 5 contém comandos, cenários restantes e limites. Aguardar depuração antes de materiais.
