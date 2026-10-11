# Brainstorm: tempo das tarefas e infraestrutura

## Decisões

- Persistir duração acumulada e início do intervalo atual. Contar exclusivamente em Criação, pausando nos demais estados e na exclusão. Reentrada em Criação retoma o acumulado; uma tarefa nova em Demanda exibe zero. Não usar jobs, polling nem gravações por segundo. Reconstruir intervalos antigos a partir dos eventos; sem evidência de início, contar a partir da migração.
- O quadro contém apenas tarefas concluídas nas últimas 168 horas, inclusive o limite. Contadores e filtros refletem o mesmo recorte. A lista completa mantém todas as tarefas não excluídas autorizadas, com paginação e filtros de busca, serviço, responsável, status e período. Período usa conclusão para concluídas e início para as demais; tarefas nunca iniciadas usam criação.
- Infraestrutura pública usa o catálogo ativo do banco. Imagens são WebP com conteúdo binário persistido no banco, mantendo o campo/URL de foto compatível. Os seis padrões públicos acompanham o pacote e são carregados por migração numa instalação nova. Carga normal é idempotente e preserva edições/exclusões.
- Restaurar padrões é uma ação administrativa com confirmação e CSRF, mantendo IDs e vínculos históricos. O responsável confirmou explicitamente: recuperar padrões excluídos e restaurar seus campos, sem modificar personalizados.
- A exclusão existente é lógica. Torná-la clara também na edição, testar padrões e vínculos, e manter confirmação discreta. Nenhuma remoção física de equipamentos referenciados.

## Limites

Preservar papéis, versões, transações, históricos, múltiplos vínculos, login e fluxos de agendamentos. A autorização atual cobre esta entrega conjunta. Não inclui push, deploy ou alteração do banco publicado. Verificação usa banco isolado.
