# Tarefas com múltiplos responsáveis e recursos

Solicitação de 08/10/2026: permitir selecionar vários responsáveis, equipamentos e materiais na mesma tarefa. O responsável esclareceu que cada material deve ter sua quantidade própria. A solicitação autoriza implementação; as etapas seguem diretamente no checkout atual, sem alterar outros módulos.

## Contrato

- Uma tarefa continua relacionada a um único agendamento de serviço e usa seu prazo. Status, versão, início, conclusão e histórico são compartilhados pela equipe da tarefa.
- Exigir pelo menos um responsável ativo em novas atribuições. Todos os responsáveis atribuídos consultam a mesma tarefa e podem iniciar/enviar; somente administradores gerenciam dados, aprovam e escolhem livremente os status. Retirar alguém revoga seu acesso.
- Equipamentos são opcionais e múltiplos. Materiais são opcionais e registrados em linhas com material e quantidade textual opcional de até 150 caracteres. Não alterar estoque. Não permitir repetir um material na mesma tarefa nem quantidade sem material.
- Conservar vínculos existentes com cadastros inativos/excluídos em edições de outros dados; impedir novas atribuições desses cadastros. Preservar todas as linhas e eventos anteriores, inclusive tarefas excluídas.
- Formulário: seleção múltipla de responsáveis/equipamentos e linhas adicionáveis/removíveis de materiais; funcionalidade também sem JavaScript. Detalhe, quadro, busca, dashboard e API devem representar a equipe e os recursos completos, sem contagens duplicadas.

## Persistência e compatibilidade

Relações explícitas `TarefaResponsavel`, `TarefaEquipamento` e `TarefaMaterial`, com FK protegida para os recursos e unicidade por tarefa/recurso. `Tarefa.responsaveis` e `Tarefa.equipamentos` são M2M; `Tarefa.materiais_gastos` contém as linhas de material/quantidade. Gravar tarefa, relações e evento na mesma transação com bloqueio de referências e atualização condicional por versão.

A migração adiciona tabelas e copia todos os vínculos únicos existentes, sem modificar linhas antigas. Campos singulares existentes permanecem como compatibilidade para consumidores anteriores e são sincronizados com a primeira associação; nunca são usados para autorização. Novos clientes enviam `responsaveis: [id]`, `equipamentos: [id]`, `materiais_gastos: [{material: id, quantidade: texto}]`. A API conserva entradas/saídas singulares durante a transição e rejeita misturar as representações do mesmo vínculo. Alterações plurais entram no histórico, junto com as diferenças singulares compatíveis.

Edições singulares são aceitas apenas quando o grupo tem no máximo um vínculo. Em tarefas já plurais, exigir a representação plural para alterar aquele grupo, evitando que um cliente antigo descarte recursos/pessoas secundários que desconhece. Edição de descrição/status continua disponível para ambos os contratos.

## Verificação

Testar atribuição a duas pessoas, acesso/executar/revogação, recursos múltiplos, quantidade por material, cadastros inválidos, entradas duplicadas, escopo/busca/contagens, CSRF, versão antiga, rollback, preservação de inativos já associados e migração de legados. Executar suíte Django completa, portabilidade, check/makemigrations e browser em cópia isolada. Atualizar o SQLite local somente após backup e validação da migração em cópia. Commit em português; sem push/deploy remoto.
