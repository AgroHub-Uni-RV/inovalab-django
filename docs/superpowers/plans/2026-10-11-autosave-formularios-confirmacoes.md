# Autosave, formulários e confirmações

Entrega autorizada em 11/10/2026, preservando regras de negócio, acesso, versão, CSRF e alternativas sem JavaScript.

1. Salvar status da tarefa ao alterar o seletor, reutilizando API/transações. Bloquear envio duplicado, anunciar resultado, reconsultar detalhes/relógio após sucesso ou conflito, não repetir POST após falha. Sem JavaScript, manter botão de envio. Commit próprio.
2. Corrigir Equipamentos em Serviços públicos para usar nome, descrição e foto do catálogo ativo, com vazio/fallback. Commit próprio.
3. Melhorar formulários de banners, equipamentos e materiais com seções, orientação, prévia de imagem e modais acessíveis. Preservar uploads, valores, validação, conflitos e páginas de fallback. Atualizar a origem sem perder filtros/paginação válida. Commit próprio.
4. Converter confirmações existentes em modais compartilhados: excluir tarefa/banner/equipamento, restaurar padrões e cancelar agendamento interno/pessoal. Ações de aprovação, recusa e realização usam diálogo de confirmação antes do POST existente. Não alterar autenticação/recuperação de senha nem a interface técnica nativa do Django Admin. Testar teclado, móvel, erro/conflito, permissões e sem JavaScript; atualizar documentação e orientações. Commit próprio.

Não inclui migrações, deploy ou push. Verificação automatizada Django e Chromium em banco isolado.

Concluído em 11/10/2026: quatro commits de implementação, 658 testes Django aprovados, verificações básicas sem problemas e cenários de Chromium concluídos. Regras e resultados em [documentação do módulo](../../modules/32-autosave-formularios-confirmacoes.md).
