# Cancelamento administrativo somente de confirmados

Solicitação de 07/10/2026: administradores podem cancelar somente agendamentos confirmados, nas agendas de serviço, equipamento e visita. A condição vale também para agendamentos criados pelo próprio administrador e substitui a permissão administrativa de cancelar qualquer situação.

## Regras e interface

- A política compartilhada exige conta ativa, registro não cancelado e, para administradores, situação `confirmado`.
- Usuários comuns continuam podendo cancelar somente seus próprios agendamentos. Sua regra de cancelamento não foi restringida por esta entrega.
- Detalhes internos e pessoais usam a mesma política para exibir Cancelar. GET e POST de cancelamento administrativo de pendentes/recusados retornam 403, inclusive em Meus agendamentos.
- Em Solicitações, Confirmar e Recusar permanecem nos pendentes; Cancelar aparece apenas nos confirmados. Recusados e cancelados não oferecem ações de cancelamento.
- A API de sessão verifica a permissão no objeto; o serviço verifica novamente a regra ao carregar o registro, antes e depois do bloqueio transacional. URLs diretas e requisições manuais não contornam a restrição.
- Cancelamentos autorizados mantêm CSRF, controle de versão, liberação do horário e histórico. Pendentes e recusados bloqueados permanecem intactos.
- A solicitação seguinte redireciona o administrador após cancelar para `/agenda/solicitacoes/`, inclusive quando cancela pela área pessoal. Usuários comuns continuam retornando para `/agenda/meus/`.

## Verificação

Os testes cobrem administradores cancelando registros próprios/de terceiros em todas as categorias e situações, bloqueios no serviço, GET/POST pessoais e internos, API, ausência de ações indevidas e preservação de versão/histórico. O fluxo de usuários comuns mantém seus testes anteriores.

Resultados: `python manage.py test --noinput` aprovou 569 testes; `python manage.py check` não apontou problemas; `python manage.py makemigrations --check --dry-run` não detectou alterações de modelos. Conferência básica no Chromium com banco isolado aprovada: administrador sem Cancelar nas pendentes, bloqueio de URL direta/POST/API, confirmação e cancelamento pela aba Confirmadas nas três categorias, além do cancelamento pessoal por conta comum. A depuração com contas e provedor reais permanece com o responsável.
