# Plano de implementação: serviços, tarefas e infraestrutura

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Substituir o catálogo operacional de serviços por serviços definidos em cada solicitação, exigir vínculo das tarefas com agendamentos de serviço e atualizar equipamentos e navegação.

**Architecture:** `Servico` contém título, descrição e prazo; `AgendaServico` contém o controle da solicitação e referencia um serviço exclusivo. `Tarefa` referencia obrigatoriamente o agendamento e deriva seu serviço desse vínculo. Modelos e campos aposentados permanecem como legado, e a migração só torna o vínculo obrigatório depois de um mapa explícito.

**Tech Stack:** Django e Django REST Framework já instalados, templates Django, JavaScript e CSS locais, SQLite no desenvolvimento e compatibilidade PostgreSQL existente. Python de execução: `.\venv\Scripts\python.exe`.

**Spec:** [Especificação aprovada](../specs/2026-10-08-servicos-tarefas-infraestrutura-design.md).

## Restrições globais

- Equipamentos deixam de ser agendáveis e permanecem na Infraestrutura.
- Prazo significa **data e hora limite**, em `America/Sao_Paulo`; formulários usam data e hora separadas e horário `hh:mm`.
- Toda tarefa pertence a um agendamento de serviço e possui responsável.
- Quantidade de material gasto é um `CharField` opcional; equipamento e material gasto são FKs opcionais.
- O registro do consumo é informativo e não altera estoque automaticamente.
- Preservar IDs, históricos, precisão temporal existente, autorização do hospedeiro, visitas, eventos e contato.
- Mapa local aprovado: **tarefa 2 → agendamento 7** e **tarefa 3 → agendamento 7**. Não aplicar esse mapa automaticamente a outros bancos.
- Fazer backup antes da migração local e validar numa cópia. Não publicar nem atualizar banco remoto nesta entrega.
- Commits em português por mudança importante. Concluir esta entrega e aguardar a depuração antes de iniciar outro trabalho.

## Foco de revisão

1. Prazo exatamente à meia-noite ou no limite do mês: ocorrência aparece no dia correto, uma única vez (tarefa 3).
2. Agendamento cancelado ou equipamento excluído depois da atribuição: editar outra informação conserva o vínculo (tarefas 4 e 5).
3. Tarefa antiga sem mapa ou com destino de outro serviço: migração bloqueia e não associa por coincidência (tarefa 2).
4. Dois pedidos com mesmo título/prazo: permanecem independentes, sem reserva exclusiva ou edição cruzada (tarefa 3).
5. Payload adulterado e página antiga: servidor rejeita ações sem permissão e retorna conflito sem gravação parcial (tarefas 3, 4 e 5).

## Arquivos e responsabilidades

- `inovalab_app/catalogo/models.py`: equipamentos e catálogo antigo renomeado como `ServicoLegado`, mantendo `catalogo_servico`.
- `inovalab_app/agenda/models.py`: novo `Servico` em tabela própria `inovalab_servico_solicitado`; `AgendaServico` com OneToOne obrigatório; propriedades de apresentação para título e prazo; agendamento de equipamento somente como legado.
- `inovalab_app/agenda/service_requests.py`: gravação transacional de solicitações e seus dados de serviço, sem conflitos de equipamento.
- `inovalab_app/tarefas/models.py`: FK obrigatória `agendamento_servico`, propriedades derivadas `servico`/`servico_id`, referências opcionais e quantidade textual; FK antiga retida como `servico_legado` para auditoria.
- `inovalab_app/migrations/0003_prepara_servicos_solicitados.py` e `0004_exige_agendamento_servico.py`: esquema intermediário, conversão individual de serviços e obrigatoriedade final do vínculo.
- `inovalab_app/management/commands/vincular_tarefas_servicos.py`: mapa JSON explícito, validação integral e aplicação atômica, com `--database` e `--dry-run`.
- `inovalab_app/upgrade.py`: validar o estado histórico correspondente às migrações aplicadas, preservando a adoção de bancos anteriores à consolidação; não trocar o esquema histórico pelo novo modelo em memória.
- Serviços, forms, serializers, selectors, views e templates existentes: adaptar contratos e apresentação, conservando as políticas de acesso.
- `inovalab_app/shared/navigation.py`, sidebar, base, `painel.css` e `painel.js`: Infraestrutura, logo institucional, retirada de Páginas e menu sempre expandido no desktop.
- Testes nos pacotes atuais e novos testes de migração/solicitações: validar o novo contrato sem eliminar testes de autorização, concorrência e histórico.

### Tarefa 1: registrar o baseline e preparar a execução

**Arquivos:** ler `AGENTS.md`, especificação e plano; usar diretório privado de evidências já ignorado pelo Git.

**Interfaces:** nenhuma alteração de produto; produzir baseline e identificação do banco local antes das mudanças.

- [x] Conferir checkout limpo e isolamento usando a skill `using-git-worktrees`. Preservar a forma de trabalho escolhida pelo responsável.
- [x] Executar `& .\venv\Scripts\python.exe manage.py test --noinput`; registrar total e resultado. Executar `check` e `makemigrations --check --dry-run`. Baseline de 08/10/2026: **545 testes passaram em 56,831 s**, `check` sem problemas e nenhuma alteração de migração detectada.
- [x] Identificar a configuração efetiva do banco sem exibir credenciais. Operações de migração desta entrega só atingem cópia e SQLite local autorizado.

### Tarefa 2: modelos e migração com mapa explícito

**Arquivos:** modificar models de catálogo/agenda/tarefas, `inovalab_app/models/__init__.py`, `admin.py`, `upgrade.py` e carga inicial; criar as duas migrações, comando de vínculos e `inovalab_app/tests/test_service_upgrade.py`. Adaptar testes de registro, adoção e carga inicial.

**Interfaces:** `Servico(titulo, descricao, prazo)`; `AgendaServico.servico` OneToOne; `Tarefa.agendamento_servico` FK PROTECT; `Equipamento.excluido_em`; `Tarefa.equipamento`, `material_gasto` e `quantidade_material_gasto` (`max_length=150`, `blank=True`, padrão vazio).

- [x] Criar testes com `MigrationExecutor`: dois agendamentos que reutilizam um catálogo produzem dois serviços distintos; IDs/eventos/legado permanecem; tarefas sem mapa bloqueiam a etapa final.
- [x] Rodar `manage.py test inovalab_app.tests.test_service_upgrade --noinput`; confirmar falha por ausência da nova migração/comando.
- [x] Criar `0003`: renomear o modelo antigo para `ServicoLegado`, preservar sua tabela e ContentType histórico; criar o novo serviço; renomear vínculos antigos para `servico_legado`; adicionar o novo vínculo de agenda e o vínculo temporariamente nulo de tarefa.
- [x] Converter cada agendamento existente: título do catálogo, descrição do motivo, prazo do término. Renomear o período e o motivo antigos para `inicio_legado`, `fim_legado` e `motivo_legado`, preservando valores e permitindo ausência em registros novos; retirar as constraints de intervalo que não correspondem ao novo serviço. Conservar material e equipamentos anteriores como legado sem presença nos formulários. Não editar `0001` nem `0002`.
- [x] Implementar `vincular_tarefas_servicos --mapa arquivo.json [--database default] [--dry-run]`, aceitando objeto como `{"2": 7, "3": 7}`. Validar tipos, existência, ausência de reassociação conflitante e compatibilidade com o serviço antigo; validar todos os registros antes de gravar. Ser idempotente e não criar eventos de ação humana retroativos.
- [x] Criar `0004`: verificar todas as tarefas, inclusive excluídas, e rejeitar as sem vínculo com mensagem de IDs e instrução do comando; depois tornar a FK NOT NULL. Instalação nova vazia aplica ambas normalmente.
- [x] Ajustar a validação de esquema para obter os modelos históricos de `0001_initial` na adoção e da última migração aplicada nos bancos consolidados, incluindo o estado intermediário `0003`. Preservar o manifesto de CHECKs da adoção e os bloqueios de esquema divergente; testar atualização de banco antigo sem exigir a tabela nova antes de executar suas migrações.
- [x] Fazer `seed_inovalab` carregar somente equipamentos. `carregar_servicos_iniciais` passa a explicar que serviços são definidos por solicitação, sem fabricar solicitações. Cadastros antigos permanecem disponíveis apenas como legado interno; retirar sua manutenção também do Django Admin.
- [x] Verificar testes de migração, registro, adoção e carga inicial; `makemigrations --check --dry-run` sem diferenças. Commit: `refactor (modelos): define serviços por solicitação e vínculos obrigatórios das tarefas.`

### Tarefa 3: fluxo de solicitação de serviço e agenda

**Arquivos:** criar `agenda/service_requests.py`; modificar services/forms/serializers/selectors/views, modal e templates de agenda, `shared/dashboard.py`; adaptar testes de agenda/dashboard/portabilidade.

**Interfaces:** `save_service_request(*, actor, data, booking_id=None, expected_version=None) -> AgendaServico`; entrada pública: `categoria='servico'`, `titulo`, `descricao`, `prazo`, `observacoes` opcional. A fachada `save_booking` continua atendendo visitas e delega serviço; criação/edição de equipamento retorna erro de validação.

- [x] Criar testes de solicitação isolada, prazo obrigatório e coincidência de título/prazo; payload de equipamento e campos antigos são rejeitados. Testar retorno do modal, formulário sem JavaScript, contas externas, CSRF e conflito de versão; rodar e observar falhas do contrato antigo.
- [x] Implementar gravação atômica de serviço e agendamento, com versão condicional e evento no mesmo bloco. Reutilizar autorização de criação/avaliação/cancelamento; novos pedidos comuns são pendentes e pedidos administrativos confirmados.
- [x] Atualizar formulário de serviço para título, descrição, `prazo_data`, `prazo_hora` e observações. Combinar prazo com fuso e preservar segundos/microssegundos ao editar outros dados mantendo o minuto exibido.
- [x] Retirar equipamento da seleção do modal e bloquear GET/POST de criação/edição dessa categoria. Manter consulta, histórico e cancelamento do legado; não alterar o fluxo de visita.
- [x] Atualizar serialização para campos novos, autor/controle/versão. Retirar manutenção operacional do catálogo de serviços; URLs antigas de cadastro não devem continuar criando serviços sem agendamento.
- [x] Ajustar consultas, buscas, cartões, detalhes e filtros: usar título/descrição/prazo de serviço. Calendários e dashboard tratam serviço como ocorrência pontual; testar meia-noite, primeiro/último dia do mês e igualdade ao horário atual.
- [x] Rodar testes dos pacotes agenda/shared e portabilidade. Commit: `feat (agenda): solicita serviços com título, descrição e prazo.`

### Tarefa 4: tarefas vinculadas e select de status

**Arquivos:** modificar tarefas forms/services/serializers/selectors/views/api e templates; adaptar `tests/tarefas/helpers.py` e testes existentes; adicionar casos para campos novos.

**Interfaces:** `save_task` aceita `agendamento_servico`, `descricao`, `responsavel`, `prazo`, `equipamento`, `material_gasto`, `quantidade_material_gasto`. `set_task_status(*, actor, task_id, status, expected_version) -> Tarefa` resolve o destino para uma transição permitida e reutiliza `transition_task`.

- [x] Criar testes para vínculo obrigatório, responsável obrigatório, rejeição de agenda pendente/cancelada em novas atribuições, campos opcionais independentes, quantidade textual e estoque intacto; rodar e observar falhas.
- [x] Adaptar gravação e snapshots: validar novo agendamento confirmado não cancelado, responsável ativo e recursos válidos não excluídos. Ao manter referências existentes, permitir edição de outros dados mesmo depois de cancelamento/exclusão; novas associações permanecem bloqueadas.
- [x] Atualizar forms e API: seleção de agendamento com título/ID, campos opcionais; `servico` e título derivados na saída, sem segunda FK operacional. Atualizar filtros/busca via `agendamento_servico__servico__titulo`, quadro, detalhe, dashboard e eventos legíveis.
- [x] Implementar select de destinos permitidos com status atual e botão Salvar status. Sem mudança de status, não incrementar versão nem gerar evento; conferir versão e acesso antes de responder.
- [x] Expor atualização por status no endpoint de transições mantendo `acao` para compatibilidade. Rejeitar envio de ambos e status inválido/proibido. Preservar restrição administrativa de aprovação/recusa/reabertura, datas automáticas e conflito 409.
- [x] Rodar testes de tarefas e dashboard com tentativas adulteradas, ator sem permissão, versão antiga, falha ao registrar evento e edição de vínculo preservado. Commit: `feat (tarefas): vincula agendamentos e adiciona recursos e seleção de status.`

### Tarefa 5: infraestrutura e exclusão de equipamentos

**Arquivos:** modificar catálogo services/forms/views/serializers/api/urls e templates; criar confirmação de exclusão; ajustar seeds e testes de catálogo/fotos.

**Interfaces:** `delete_equipment(*, actor, equipment_id) -> Equipamento`; exclusão define `excluido_em` com autorização administrativa e sem apagar fotos/FKs.

- [x] Criar testes de exclusão por admin, rejeição para usuário comum, CSRF, GET sem mutação e API; verificar tarefa/legado/foto e repetição da operação. Rodar e observar falta da operação.
- [x] Implementar confirmação e POST, DELETE na API de equipamento, exclusão lógica atômica e retirada de listagens/opções de nova atribuição. Cadastros excluídos não aceitam edição pela gestão normal; o Django Admin não oferece exclusão física que contorne a retenção.
- [x] Tornar a entrada do catálogo uma listagem apenas de equipamentos com título Infraestrutura. Remover abas e ações de serviços; incluir Excluir nas ações administrativas.
- [x] Preservar a idempotência da carga inicial: equipamento excluído com código inicial não deve reaparecer após seed.
- [x] Rodar testes de catálogo e referências em tarefas. Commit: `feat (infraestrutura): mantém equipamentos e permite exclusão com histórico preservado.`

### Tarefa 6: sidebar completa e navegação

**Arquivos:** modificar shared navigation, base/sidebar, painel CSS/JS e testes de frontend em Accounts e InovaLab.

**Interfaces:** desktop sempre expandido; estado `sidebar-open` exclusivamente móvel; logo resolve `conteudo:inicio`; Infraestrutura resolve `catalogo:equipamentos-list`.

- [x] Adaptar as verificações existentes de navegação para ausência de Páginas, rótulo Infraestrutura e logo de início. Não criar testes que apenas reproduzam declarações de CSS.
- [x] Retirar controle estreito, logo de ícone e leitura/gravação da preferência antiga de largura. Ajustar layout desktop com largura completa, texto e foco visível.
- [x] Preservar no móvel o botão, backdrop, Escape, foco inicial/de retorno e contenção de Tab; menu fechado deve ser inacessível por teclado. Mudança para desktop restaura o conteúdo interativo e sidebar completa.
- [x] Rodar testes frontend e verificar no navegador em desktop e 360 px, incluindo recarga/navegação e localStorage antigo igual a false. Commit: `refactor (sidebar): mantém menu expandido e simplifica navegação.`

### Tarefa 7: migração local, verificação final e documentação

**Arquivos:** criar `docs/modules/25-servicos-tarefas-infraestrutura.md`; atualizar AGENTS.md e documentação afetada; guardar mapas/backups/evidências somente no diretório privado ignorado.

**Interfaces:** entrega integrada validada; banco local migrado com IDs e histórico preservados; nenhum push/deploy implícito.

- [x] Executar suíte completa, `check`, `makemigrations --check --dry-run` e teste de portabilidade no hospedeiro alternativo. Resolver regressões do contrato antigo sem reduzir a cobertura de autorização, concorrência e histórico.
- [x] Identificar processos que escrevem no SQLite local, pausá-los para obter backup consistente e guardar banco/media. Criar o mapa aprovado; validar migração primeiro numa cópia: `migrate inovalab_app 0003`, `vincular_tarefas_servicos --mapa ... --dry-run`, aplicar mapa e executar `migrate` até `0004`.
- [x] Comparar IDs, relações, eventos e arquivos antes/depois; confirmar tarefas 2 e 3 no agendamento 7. Aplicar o mesmo procedimento ao banco local e reiniciar somente processos de desenvolvimento afetados.
- [x] Navegador: serviço pelo modal e sem JS, aprovação, tarefa com/sem opcionais, select de status, cancelamento, exclusão de equipamento, logo, sidebar desktop e móvel, foco/teclado e ausência de overflow. Usar identidade/provedor controlados quando necessário, sem mensagens a terceiros.
- [x] Aplicar skills de verificação e revisão de código; conferir implementação requisito a requisito. Se houver delegação autorizada, revisão independente; caso contrário, registrar revisão inline e essa limitação.
- [x] Documentar novos payloads e passos de atualização para bancos com tarefas antigas, comandos/resultados de testes e cenários de depuração restantes. Commit: `docs (servicos): registra migração e verificações do novo fluxo.`

## Revisão e escolha de execução

Plano preparado a partir da especificação aprovada. Recomenda-se execução nesta sessão pelo agente principal: as mudanças compartilham modelos, migração e contratos de API e devem ser integradas em sequência. A execução com subagentes permanece uma alternativa se o responsável a escolher explicitamente.

Execução inline autorizada com “implemente”. Entrega concluída: 527 testes Django e 6 de portabilidade passaram, check/makemigrations limpos, navegador validado em cópia isolada e SQLite local migrado com mapa aprovado. Revisão independente realizada conforme executing-plans/requesting-code-review; os três achados foram reproduzidos e corrigidos. Para manter commits coerentes no refactor integrado, os passos 2–5 foram reunidos em um commit de negócio; sidebar e documentação têm commits próprios. Branch mantida no checkout compartilhado para depuração, sem push/deploy.
