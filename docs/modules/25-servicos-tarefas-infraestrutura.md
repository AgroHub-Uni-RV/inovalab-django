# Serviços por solicitação, tarefas e infraestrutura

Entrega de 08/10/2026, aprovada na [especificação](../superpowers/specs/2026-10-08-servicos-tarefas-infraestrutura-design.md) e autorizada com “implemente”. Substitui as regras anteriores de catálogo de serviços, reserva de equipamento e sidebar recolhida. Accounts, papéis AgroHub, visitas, eventos e contato continuam com suas regras.

## Serviço e agendamento

Cada solicitação cria um `Servico` próprio com `titulo`, `descricao` e `prazo` obrigatórios. `AgendaServico.servico` é exclusivo (OneToOne) e conserva autoria, situação, avaliação, cancelamento, versão e eventos. O formulário separa `prazo_data` e `prazo_hora`; horários novos/alterados são gravados em minutos, e o minuto inalterado conserva segundos e microssegundos anteriores.

O prazo é uma data limite, sem reservar um intervalo nem um equipamento. Pedidos distintos podem compartilhar título e prazo. Agenda, contadores e dashboard colocam o serviço no dia do prazo, incluindo corretamente meia-noite e limites de mês. Contas comuns criam pendentes; administradores criam confirmados e avaliam pendentes. O cancelamento mantém as regras de autoria e de administração vigentes.

O modal oferece Visita e Serviços, conserva rascunhos, validação, CSRF, retorno e foco. Os formulários também funcionam sem JavaScript. Novos agendamentos e edições de equipamento são bloqueados na interface, views, API e domínio. Reservas antigas continuam consultáveis e canceláveis segundo a política vigente.

Exemplo de criação por `POST /api/v1/agendamentos/` com sessão e CSRF:

```json
{
  "categoria": "servico",
  "titulo": "Produzir protótipo",
  "descricao": "Peça para o projeto",
  "prazo": "2026-11-01T17:00:00-03:00",
  "observacoes": "Detalhes complementares"
}
```

Atualizações usam `PATCH /api/v1/agendamentos/servico/{id}/` com `versao` e os campos alterados. Versão antiga retorna 409. Campos removidos (`objeto`, `motivo`, `inicio`, `fim`, equipamentos e consumo de material) e criação de equipamento retornam 400. Autor/controle não são graváveis pelo cliente. As antigas páginas `/catalogo/servicos/` redirecionam para a agenda; sua API responde 410 à consulta e não aceita escrita.

## Tarefas

Toda tarefa tem FK obrigatória para `AgendaServico`, descrição e responsável. O serviço é derivado do agendamento; não existe uma segunda seleção de catálogo. Novos vínculos exigem agendamento confirmado e não cancelado e responsável ativo. Equipamento excluído e material indisponível não entram em novas atribuições. Vínculos existentes continuam editáveis em outros dados, preservando suas referências.

Campos opcionais: `equipamento` (FK), `material_gasto` (FK para Material), `quantidade_material_gasto` (CharField de 150 caracteres). Material e quantidade são independentes. A quantidade aceita texto como `200 g`, `2 unidades` ou `meia bobina`; o registro não altera o estoque. O prazo próprio da tarefa permanece opcional.

Exemplo de `POST /api/v1/tarefas/`, administrativo:

```json
{
  "agendamento_servico": 7,
  "responsavel": 3,
  "descricao": "Produzir peça",
  "equipamento": 2,
  "material_gasto": 1,
  "quantidade_material_gasto": "200 g"
}
```

Os campos opcionais podem ser omitidos; FKs opcionais também aceitam null. Edições exigem `versao`. A saída conserva `servico` e `servico_nome` derivados, ambos somente leitura. Filtros e consultas de tarefas respeitam o responsável, incluindo os títulos disponíveis no filtro de serviço.

O detalhe apresenta um select com o status atual e os destinos permitidos, acompanhado de **Salvar status**. `POST /api/v1/tarefas/{id}/transicoes/` aceita `{"status":"criacao","versao":1}`. A entrada anterior por `acao` continua disponível; enviar ação e status juntos é inválido. O servidor valida permissão, transição e versão; aprovar, recusar e reabrir continuam administrativos. Manter o status atual não gera evento nem aumenta a versão. Início/conclusão continuam automáticos.

A gravação valida e bloqueia as referências na mesma transação da tarefa e do evento, usando o bloqueio de serviço compartilhado com cancelamento/avaliação e os registros dos recursos. Isso impede criar uma tarefa depois de um cancelamento/exclusão concorrente já confirmado. Conflitos de escrita SQLite são devolvidos como conflito de tarefa. O Django Admin oferece somente consulta das tarefas; a escrita usa o fluxo que registra histórico e versão.

## Infraestrutura e sidebar

Infraestrutura apresenta exclusivamente equipamentos. Administradores excluem por confirmação e POST com CSRF ou `DELETE /api/v1/equipamentos/{id}/`. `excluido_em` retira o equipamento das listagens e novas opções sem apagar linhas, fotos, tarefas ou reservas antigas. Exclusão repetida pelo domínio é idempotente; o seed não restaura equipamento excluído. O Django Admin também exclui logicamente e sua confirmação conserva referências protegidas.

A sidebar desktop permanece expandida, sem botão de recolher ou preferência de largura. A logo completa aponta para `/` por resolução de URL, respeitando o prefixo do hospedeiro. Páginas foi removido. No celular, o menu completo abre por botão e fecha com backdrop/Escape, com contenção de foco e conteúdo inerte quando necessário.

## Atualização de banco existente

Não remover tabelas, executar seed para converter dados ou escolher vínculos automaticamente. Pausar escritas e guardar backup consistente de banco e arquivos. Testar os passos numa cópia antes do banco original. Em um banco ainda não consolidado, seguir primeiro a preparação descrita em [24-consolidacao-inovalab.md](24-consolidacao-inovalab.md), adotando somente até `0002_preserva_contenttypes` com `--fake-initial`; depois seguir esta atualização.

```powershell
.\venv\Scripts\python.exe manage.py check_inovalab_upgrade
.\venv\Scripts\python.exe manage.py migrate inovalab_app 0003 --noinput
.\venv\Scripts\python.exe manage.py vincular_tarefas_servicos --mapa caminho/mapa.json --dry-run
.\venv\Scripts\python.exe manage.py vincular_tarefas_servicos --mapa caminho/mapa.json
.\venv\Scripts\python.exe manage.py migrate --noinput
.\venv\Scripts\python.exe manage.py check_inovalab_upgrade
```

O mapa JSON tem IDs explícitos de tarefa para agendamento, por exemplo `{"2":7,"3":7}`. Esse mapa foi aprovado somente para o SQLite local desta entrega. Outros bancos exigem seus próprios destinos revisados. O comando aceita `--database`, rejeita IDs desconhecidos, chaves duplicadas, reassociação conflitante e serviço legado incompatível, validando todo o mapa antes de gravar. O dry-run não altera registros; aplicar novamente o mesmo mapa não duplica eventos.

`0003_prepara_servicos_solicitados` individualiza cada serviço antigo com título do catálogo, descrição do motivo (fallback para descrição/nome antigos) e prazo do término. O catálogo anterior vira `ServicoLegado` na mesma tabela; período/motivo, equipamentos e material dos agendamentos permanecem como legado, sem distribuí-los arbitrariamente às tarefas. IDs e eventos anteriores permanecem intactos. Os ContentTypes/permissões do modelo renomeado conservam IDs e vínculos; o Django renomeia os codenames para `*_servicolegado` e cria permissões próprias para o novo `Servico`.

`0004_exige_agendamento_servico` bloqueia tarefas sem mapa, inclusive excluídas, exibindo seus IDs, e torna as novas relações NOT NULL. Instalação nova vazia aplica as duas migrações normalmente e carrega somente equipamentos por `seed_inovalab`. `carregar_servicos_iniciais` apenas informa o novo fluxo. O verificador de atualização usa o estado da migração aplicada, incluindo a etapa intermediária, conservando as verificações da adoção anterior.

O SQLite local foi atualizado depois de validar a cópia. Compararam-se 18 tabelas, campos antigos, IDs, eventos, arquivos e vínculos de permissões. Tarefas 2 e 3 apontam para agendamento 7. Backup: `.private/servicos-tarefas/backup-before.sqlite3`; arquivos conservados em `media/` e copiados para `.private/servicos-tarefas/media-copy/`. Esses dados privados não entram no Git. Recuperação exige restaurar banco/arquivos e código compatível do backup; não usar migração reversa para descartar solicitações novas. Nenhum banco remoto foi atualizado nesta entrega.

## Verificação

Os testes cobrem o contrato novo, autorização, escopo, CSRF, histórico, versões, rollback, concorrência, exclusão lógica, precisão dos horários, visitas e migração com mapa explícito. As expectativas antigas de reservas de equipamento, catálogo operacional de serviços e consumo no agendamento foram substituídas pelo contrato aprovado.

| Verificação | Resultado |
| --- | --- |
| `.\venv\Scripts\python.exe manage.py test --noinput` | 527 testes passaram após as correções da revisão |
| `.\venv\Scripts\python.exe manage.py test inovalab_app.tests.portability --settings=inovalab_app.tests.host_settings --noinput` | 6 testes passaram com auth.User, sem Accounts, sob `/laboratorio/` |
| `manage.py check` | Nenhum problema |
| `manage.py makemigrations --check --dry-run` | Nenhuma migração pendente |
| `git diff --check` | Sem erros de whitespace |
| SQLite em cópia e original | `0003`, dry-run/mapa explícito, `0004` e verificação de esquema passaram; comparação de 18 tabelas e arquivos aprovada |
| Chrome/Playwright em cópia isolada | Modal com rascunho, serviço sem JavaScript, aprovação/cancelamento, tarefas com/sem opcionais, select de status, exclusão preservando referência e sidebar/teclado passaram |
| Layout | 1366, 900 e 360 px sem overflow nas telas verificadas; nenhum erro JavaScript |

A revisão independente identificou três problemas, reproduzidos por testes antes da correção: escrita de tarefas fora do domínio pelo Django Admin, coletor de exclusão física bloqueando equipamentos utilizados e janela de concorrência ao validar referências da tarefa. Os quatro testes de regressão passaram após as correções; a suíte completa foi executada novamente. Evidências e capturas ficam em `.private/servicos-tarefas/`, sem dados de teste no banco original.

O responsável ainda deve depurar o uso com identidades reais do provedor, conferir formulários com dados próprios e revisar o mapa específico antes de atualizar qualquer outro banco. A suíte atual substitui cenários obsoletos do contrato anterior; visitas, permissões, concorrência, fotos, histórico e conflitos de versão continuam cobertos.
