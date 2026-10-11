# Planejamento

1. **Relógio persistido**: campos e constraints, migração com reconstrução de eventos, integração em todas as transições/exclusão, exibição HH:MM:SS na topbar e API somente leitura. Testar pausas, retomadas, concorrência e recarga. Commit próprio.
2. **Quadro e lista**: recorte de sete dias coerente com contadores, nova lista com filtros e datas validadas, links entre apresentações e paginação. Testar limite temporal e autorização. Commit próprio.
3. **Equipamentos padrão**: alinhar dados/fotos aos seis itens públicos, armazenar WebP no banco, carga automática via migração sem sobrescrever personalizações, catálogo público dinâmico e restauração administrativa confirmada. Testar instalação nova, idempotência, fotos, restauração e CSRF. Commit próprio.
4. **Exclusão e integração**: explicitar exclusão na edição e identificação de padrões, preservar vínculos e recuperação; verificar Django completo e navegador desktop/móvel em banco isolado; atualizar documentação e orientações. Commit próprio (correções adicionais em commits se necessário).

Executar testes direcionados antes de cada commit e a suíte completa ao final. Verificar `check`, `makemigrations --check --dry-run`, migrações e diff. Não aplicar migrações ao banco de trabalho sem backup e decisão do ambiente.
