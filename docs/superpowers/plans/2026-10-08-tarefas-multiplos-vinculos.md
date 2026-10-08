# Plano: múltiplos vínculos na tarefa

Execução inline autorizada pela solicitação, no checkout `feat/servicos-tarefas-infraestrutura`. Especificação: `../specs/2026-10-08-tarefas-multiplos-vinculos-design.md`. Ledger privado: `.private/tarefas-multiplos/progress.md`.

## Etapas

1. **Persistência e domínio** — modelos de vínculo explícito, migração de cópia e `save_task(actor, data, task_id=None, expected_version=None)` com campos plurais e aliases singulares. `visible_tasks` usa responsáveis plurais; permissão de execução consulta associação. Snapshot inclui listas de IDs/quantidades ordenadas. Testes primeiro: múltiplos vínculos, acesso/revogação, entrada inválida, referência indisponível, versão e rollback; migração preserva colunas/eventos e copia todas as tarefas.
2. **Formulários e API** — `TaskForm` com responsáveis/equipamentos múltiplos e formset de materiais. `TaskMaterialFormSet` valida quantidade por material e duplicatas. Adicionar/remover linhas funciona em POST sem JavaScript e por JS progressivo. Serializador aceita listas, conserva aliases singulares sem conflito e devolve todas as relações. Testar validação, edição parcial, CSRF, responsáveis secundários e status.
3. **Apresentação e consultas** — exibir todos os responsáveis/recursos no detalhe e quadro; buscar qualquer responsável com resultados únicos. Atualizar dashboard e fixtures que criam tarefas diretamente. Testar busca/contadores e layout no browser desktop/móvel, com e sem JavaScript.
4. **Entrega** — executar `manage.py test --noinput`, portabilidade com host_settings, check, makemigrations e diffcheck; revisão independente final. Backup consistente, validar migração em cópia e aplicar local, preservando linhas/arquivos. Documentar contratos e registrar commits portugueses; manter servidor local disponível.

## Foco da revisão

- Um responsável removido não acessa a tarefa por nenhum endpoint.
- Escrita dos vínculos e evento é atômica e não passa sobre versão antiga.
- Múltiplos responsáveis não duplicam itens/paginação/contadores.
- Materiais têm quantidades independentes, sem duplicação e sem alterar estoque.
- Referências antigas indisponíveis e todas as tarefas excluídas sobrevivem à migração.
