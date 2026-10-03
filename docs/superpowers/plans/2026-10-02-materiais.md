# Plano simples — Materiais

> Execução direta com `executing-plans`, conforme fluxo autorizado pelo responsável. Somente módulo 6; aguardar depuração antes de banners.

**Objetivo:** consultar e corrigir o cadastro de materiais do laboratório pela interface e API, sem presumir movimentações ou consumo automático.

**Fontes:** RF17/RF23/RF24, UC10, CT21 e RN10. F3 confirmou Q09/Q12: cadastro simples, administradores mantêm e usuários internos ativos consultam; quantidade não negativa até 3 casas e unidade informada; categoria/fonte em texto e status disponível/indisponível, sem movimentações. Limites de tamanho, obrigatoriedade, versão e exclusão abaixo são escolhas técnicas para depuração.

**Arquitetura:** app `materiais`, dependente da política de `accounts`. Modelo `Material`, serviço `save_material`, telas simples e API interna por sessão/CSRF. Sem novas dependências; SQLite e checkout ativo `feat/materiais`, base `6ab0ac0`.

## Contrato

- Usuários internos ativos consultam lista/detalhe, incluindo indisponíveis; administradores de negócio/superusuários ativos criam/editam. `is_staff` sozinho não permite escrita. API externa de integração não autentica este módulo.
- `nome` até 150, `categoria` até 100, `fonte` até 150 e `unidade` até 20: textos obrigatórios aparados nas bordas. Fonte é descrição livre da origem; categoria/unidade livres, sem conversão implícita. Nomes repetidos permitidos.
- `quantidade`: decimal não negativo de até 12 dígitos totais/3 casas, máximo `999999999.999`; rejeitar precisão extra sem arredondar, booleanos e valores não finitos. API usa ponto e devolve string com 3 casas; formulário aceita vírgula decimal em português.
- `status`: `disponivel` (padrão) ou `indisponivel`, independente da quantidade. Zero não muda status. `versao` inicial 1; todas as edições exigem inteiro positivo, atualizado por UPDATE condicionado para evitar sobrescrita. Versão antiga 409 `versao_desatualizada`; nenhum dado parcialmente salvo.
- Web `/materiais/`, `novo/`, `{id}/`, `{id}/editar/`; lista por nome/ID, paginada 25. Formulários estritos/CSRF e versão oculta. API `/api/v1/materiais/` e `/{id}/`: GET, POST, PUT, PATCH, HEAD, OPTIONS; JSON estrito, 400/403/404/409/415, sem DELETE.
- Criação não aceita `id`/`versao` nem campos desconhecidos. PUT exige os seis campos do cadastro; PATCH exige versão e campos desejados. Sem registro no Django Admin que contorne o serviço.
- Sem exclusão física, movimentações, empréstimos/devoluções, auditoria de estoque, vínculo com tarefas/agenda, unidades padronizadas ou autenticação externa neste módulo. Preservar identidade e navegação existentes, acrescentando link Materiais.

## 1. Cadastro e correção segura

**Arquivos:** `materiais/{__init__,apps,models,services,selectors}.py`, migração inicial, settings; `materiais/tests/{test_services,test_concurrency}.py`.

**Interface:** `save_material(*, actor, data, material_id=None, expected_version=None) -> Material`; `MaterialConflict` para 409; `visible_materials(actor) -> QuerySet`. Campos públicos: nome, categoria, quantidade, unidade, status, fonte.

- [x] RED: criação normalizada/fração/zero; quantidade negativa/não finita/bool/extra precisão/limites; obrigatórios/status; papéis/inativo; quantidade corrigida 10→8; versão antiga/inválida/campos desconhecidos preservam todos os dados.
- [x] Implementar modelo/checks e serviço de validação/autorização; edição usa UPDATE onde versão = esperada, incrementa exatamente uma vez.
- [x] Duas conexões reais editam a mesma versão: exatamente um sucesso, outro conflito; nenhum sobrescreve vencedor. GREEN `manage.py test materiais.tests.test_services materiais.tests.test_concurrency`; suíte completa/check/drift.
- [x] Commit `feat (materiais): adiciona cadastro e correção com controle de versão.`.

## 2. Interface e API interna

**Arquivos:** `materiais/{forms,serializers,api,api_urls,views,urls}.py`, templates, testes web/API; URLs, menu e página inicial.

- [x] RED: web/API anônimo/inativo, leitura interna, staff sem escrita, admin sem staff escreve; sessão/CSRF, contrato decimal/paginação/JSON estrito, 405 DELETE/415, PUT/PATCH/version/conflito; formulário vírgula decimal/obrigatórios/status/versão antiga e links corretos.
- [x] Implementar telas simples reutilizando CSS existente, sem alterar identidade; API JSON por sessão. Form/API chamam somente `save_material`.
- [x] GREEN testes do módulo e suíte completa/check/drift; commit `feat (materiais): disponibiliza telas e API do cadastro.`.

## 3. Entrega

- [ ] Migração aditiva e Chrome com fixtures próprias: cadastro, correção 10→8, quantidade negativa, indisponibilidade/zero, consulta comum/escrita negada, API e versão antiga; teclado/360 px. Remover somente fixtures identificadas; encerrar navegador/servidor.
- [ ] Revisão independente única de toda a branch; corrigir Important/Critical com RED/GREEN, menores registrados.
- [ ] Suíte completa, check, drift, pip check, diff check; `docs/modules/06-materiais.md`, README e docs 01–05 atualizadas com fontes/decisões/cenários restantes.
- [ ] Commit de documentação, registrar decisões/resultados e limpar scratch próprio; manter branch local, aguardar depuração antes de banners. Sem push/merge automático.

## Foco de revisão

1. Quantidade decimal com precisão excedente, limite superior, booleanos ou valor não finito nunca é arredondada/salva silenciosamente.
2. Duas edições da mesma versão, inclusive nome/unidade diferentes, produzem somente um vencedor sem sobrescrita parcial.
3. Formulário português aceita vírgula decimal; API exige ponto e preserva 3 casas na resposta.
4. Usuário comum/staff/inativo e token externo não podem manter materiais; campos desconhecidos/ID/versão inicial não passam pelas entradas.
5. Zero e indisponibilidade permanecem independentes; origem/categoria/unidade livres são escolhas provisórias, sem movimentação implícita.

Referências: [DecimalField Django](https://docs.djangoproject.com/en/6.0/ref/models/fields/#decimalfield), [DecimalField DRF](https://www.django-rest-framework.org/api-guide/fields/#decimalfield).
