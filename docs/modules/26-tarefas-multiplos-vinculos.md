# Tarefas com múltiplos responsáveis e recursos

Entrega de 08/10/2026, solicitada pelo responsável. Substitui a seleção unitária descrita no [módulo 25](25-servicos-tarefas-infraestrutura.md). Especificação: [múltiplos vínculos](../superpowers/specs/2026-10-08-tarefas-multiplos-vinculos-design.md).

## Uso

A tarefa exige pelo menos um responsável. O formulário permite selecionar várias pessoas e equipamentos; no computador, usar Ctrl/Command para combinar seleções. Equipamentos são opcionais. Adicionar material cria outra linha com material e quantidade gasta própria; remover material retira somente aquela linha. Sem JavaScript, Adicionar material envia o rascunho para o servidor sem gravar a tarefa, e a opção Remover este material é aplicada ao salvar.

Cada quantidade é texto opcional de até 150 caracteres, como `200 g`, `2 unidades` ou `meia bobina`. Não informar quantidade sem material nem repetir um material. O registro do consumo não altera estoque. O detalhe mostra todos os equipamentos, materiais/quantidades e responsáveis; quadro e dashboard mostram a equipe inteira.

Todos os responsáveis atribuídos, respeitando o acesso interno e os papéis já existentes do hospedeiro, consultam a mesma tarefa e podem iniciar/enviar para avaliação. Administradores gerenciam dados e escolhem qualquer status; os demais conservam as transições anteriores. Remover alguém revoga seu acesso, inclusive na API, histórico e transições. Uma tarefa mantém um único agendamento, prazo herdado do serviço, status, versão e histórico compartilhados. Os papéis/autenticação do sistema não foram alterados.

## API

`POST /api/v1/tarefas/` administrativo, com sessão e CSRF:

```json
{
  "agendamento_servico": 7,
  "descricao": "Produzir protótipo em equipe",
  "responsaveis": [2, 3],
  "equipamentos": [1, 4],
  "materiais_gastos": [
    {"material": 1, "quantidade": "200 g"},
    {"material": 2, "quantidade": "meia bobina"}
  ]
}
```

Listas de equipamentos/materiais podem ser omitidas ou vazias. Responsáveis não podem ser vazios. Novas atribuições exigem pessoa ativa, equipamento não excluído e material disponível. Relações anteriores indisponíveis podem ser mantidas ao editar outros dados. IDs inválidos/duplicados, quantidades inválidas e quantidade sem material retornam 400, sem gravação parcial.

`PATCH /api/v1/tarefas/{id}/` exige `versao`. Omitir uma lista mantém seus vínculos; enviá-la substitui aquele grupo completo. A saída inclui todas as listas. O prazo continua somente leitura. Versão antiga retorna 409 e não modifica tarefa, relações ou eventos.

Os campos anteriores `responsavel`, `equipamento`, `material_gasto` e `quantidade_material_gasto` permanecem na saída como representação da primeira associação, por ordem de ID, para compatibilidade. Entradas singulares funcionam em grupos com no máximo um vínculo, mas não podem ser misturadas com a lista equivalente. **Se o grupo já tiver vários vínculos, sua edição exige a lista plural e retorna 400 ao receber o campo singular.** Isso impede clientes antigos de apagar pessoas/recursos secundários que desconhecem. Descrição/status continuam disponíveis independentemente da representação.

## Persistência e histórico

`TarefaResponsavel` e `TarefaEquipamento` são relações explícitas M2M. `TarefaMaterial` guarda material e quantidade por tarefa. Cada tabela exige unicidade tarefa/recurso e protege a FK do cadastro contra exclusão física. Exclusão lógica de equipamento continua preservando a associação.

O domínio normaliza listas, bloqueia referências e grava a linha de tarefa, as associações e o evento na mesma transação. A atualização condicional por versão conserva a proteção concorrente. Eventos novos registram listas completas de IDs e material/quantidade anteriores e novos; eventos antigos permanecem iguais. A autorização consulta exclusivamente `responsaveis`, e as consultas/buscas usam resultados e contagens distintos.

## Migração

`0006_tarefas_multiplos_vinculos` cria três tabelas e copia os vínculos existentes de todas as tarefas, inclusive excluídas e associadas a cadastros indisponíveis. Preserva colunas, valores, IDs, eventos e arquivos anteriores. Quantidade histórica sem material permanece na coluna anterior, sem inventar uma associação de material.

Em banco existente: pausar escrita, guardar backup de banco/arquivos, validar em cópia e executar:

```powershell
.\venv\Scripts\python.exe manage.py check_inovalab_upgrade
.\venv\Scripts\python.exe manage.py migrate --noinput
.\venv\Scripts\python.exe manage.py check_inovalab_upgrade
```

O SQLite local foi atualizado após a validação em cópia. Todos os valores antigos foram comparados por nome de coluna (SQLite pode reorganizar colunas ao reconstruir a tabela), incluindo eventos, IDs e vínculos de permissões. Associações copiadas foram conferidas individualmente. Novos ContentTypes/permissões das tabelas de vínculo são criados pelo Django, sem conceder privilégios a contas existentes. Arquivos permaneceram iguais.

Backups/evidências privados: `.private/tarefas-multiplos/backup-before.sqlite3` e `media-backup/`. Nenhum banco remoto foi atualizado. Recuperação exige restaurar backup e código compatível; reverter a migração elimina as novas tabelas e não preserva associações múltiplas posteriores.

## Verificação

| Comando/cenário | Resultado |
| --- | --- |
| `.\venv\Scripts\python.exe manage.py test --noinput` | 558 testes passaram |
| `.\venv\Scripts\python.exe manage.py test inovalab_app.tests.portability --settings=inovalab_app.tests.host_settings --noinput` | 6 testes passaram |
| `manage.py check` / `makemigrations --check --dry-run` | Nenhum problema ou mudança pendente |
| `git diff --check` | Sem erros de whitespace |
| Chrome/Playwright em cópia isolada | Criação/edição plural, quantidade por material, execução pelo segundo responsável, revogação de acesso, bloqueio de edição singular perigosa e fluxo sem JavaScript passaram |
| Layout | Formulário/detalhe verificados em 1366, 900 e 360 px, sem overflow; nenhum erro JavaScript |

A revisão independente encontrou risco de descarte de vínculos secundários por edição singular da API. O teste reproduziu o problema antes da correção; o bloqueio por grupo plural passou e a suíte completa foi executada novamente. Testes adicionais cobrem falha ao gravar histórico com rollback de todas as relações, migração com tarefa excluída, cadastros indisponíveis e manutenção de vínculos unitários da API anterior.

O responsável pode depurar os fluxos com identidades reais do provedor. Testes de navegador usaram a cópia com adaptador Django; autenticação/Accounts e banco original não receberam identidades ou materiais de teste.
