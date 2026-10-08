# Detalhes de tarefas em modal

Entrega de 08/10/2026. Complementa a criação e edição descritas no [módulo 27](27-tarefas-modal-ux.md). Conforme o escopo aprovado, esta entrega conclui Tarefas; melhorias de formulários, edição e detalhes da Agenda permanecem para a próxima etapa, após depuração e autorização do responsável.

## Experiência

Ver tarefa no quadro e dashboard abre o mesmo diálogo usado pelos formulários, sem alterar a URL de origem. O detalhe organiza identificação e status, prazo herdado, agendamento e autoria, descrição, início/conclusão, todos os responsáveis, equipamentos, materiais com quantidades individuais e os cinco eventos recentes.

Administradores podem abrir Editar dados no mesmo diálogo. Salvar retorna automaticamente ao detalhe atualizado; Cancelar retorna ao detalhe sem gravar. A criação mantém sua confirmação, cujo Ver tarefa também abre o detalhe no diálogo.

Salvar status atualiza o detalhe e o conteúdo de origem. A atualização conserva filtros e ignora respostas antigas quando outra gravação começa. Escape, fechamento pelo fundo e pelo botão devolvem foco ao acionador, inclusive quando o cartão é substituído por uma atualização tardia. Fechamento e reenvio ficam bloqueados durante a gravação.

O layout adapta resumo, recursos e histórico para telas estreitas. Feedback de sucesso é anunciado como status; validação e conflito como alerta. O status Concluído usa texto verde com contraste reforçado no detalhe.

## Compatibilidade e segurança

`GET /tarefas/{id}/` com `X-Task-Modal: 1` retorna somente o fragmento `data-task-modal-content`. A edição válida e a mudança válida de status retornam detalhe HTML em HTTP 200; conflitos de status retornam detalhe atualizado em HTTP 409 e validação de status em HTTP 400. Fragmentos usam `Cache-Control: no-store` e `Vary: X-Task-Modal`.

Responsáveis visualizam apenas suas tarefas e mantêm as transições existentes. Administração de dados continua exclusiva de administradores. CSRF, versão, status compartilhado, prazo herdado, eventos e vínculos não mudaram. Em conflito por remoção ou reatribuição, a consulta de visibilidade é repetida antes de devolver qualquer detalhe.

Se a sessão expirar no POST de status, o retorno após login aponta para o detalhe, nunca para a rota que aceita somente POST. Prefixos e parâmetros do login definidos pelo hospedeiro são preservados. O cliente não reenvia automaticamente POSTs de resposta incerta.

URLs diretas mantêm páginas completas. Detalhe e alteração de status funcionam sem JavaScript com redirecionamento tradicional. Histórico completo e exclusão continuam nas telas existentes. Nenhuma alteração de modelo, migração, API ou provedor de autenticação.

## Verificação

- `venv/Scripts/python.exe manage.py test --noinput`: 570 testes passaram.
- `venv/Scripts/python.exe manage.py test inovalab_app.tests.portability --settings=inovalab_app.tests.host_settings --noinput`: 7 testes passaram.
- `manage.py check`, `makemigrations --check --dry-run`, `node --check inovalab_app/static/inovalab_app/tarefas/task-modal.js` e `git diff --check`: sem problemas ou migrações pendentes.
- Chromium em banco SQLite isolado: detalhe, edição/cancelamento/gravação, status, responsável sem administração, fechamento/foco e fluxo sem JavaScript.
- Respostas reais atrasadas e entregues fora de ordem: foco preservado e quadro conserva o status mais recente.
- Sessão expirada: login configurado retorna ao detalhe, inclusive com prefixo `/laboratorio/`.
- Layout em 1366, 900 e 360 px sem overflow; auditoria automatizada WCAG A/AA do detalhe sem violações ou itens incompletos no cenário testado.

O banco local do projeto não foi alterado. Ainda cabe ao responsável depurar os registros e identidades reais, a autenticação com AgroHub e outros navegadores. A auditoria automatizada não substitui avaliação manual completa de acessibilidade.
