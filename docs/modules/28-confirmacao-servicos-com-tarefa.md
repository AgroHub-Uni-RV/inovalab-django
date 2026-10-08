# Confirmação de serviços com tarefa obrigatória

Entrega de 08/10/2026. O responsável exige criar uma tarefa vinculada antes de confirmar um agendamento de serviço, inclusive quando o próprio administrador faz a solicitação. Esta decisão substitui a confirmação automática de serviços na criação administrativa. Visitas e registros históricos não são alterados.

## Fluxo e UX

Todas as novas solicitações de serviço são pendentes. Para o administrador, o formulário explica a etapa obrigatória e usa **Continuar para tarefa**. Depois da gravação da solicitação, abre a criação da tarefa; não confirma o serviço nesse momento. Solicitações feitas por outras contas continuam aguardando a avaliação administrativa.

**Confirmar**, em Solicitações ou no detalhe do serviço pendente, abre o modal existente de criação de tarefas, mantendo a página de origem. O serviço está fixo e o prazo é herdado, somente leitura. A descrição do pedido é sugerida para a tarefa e pode ser ajustada. Responsáveis, equipamentos e materiais reutilizam o formulário completo, incluindo seleções múltiplas e quantidade textual por material. Pelo menos um responsável é obrigatório. O botão é **Criar tarefa e confirmar agendamento**.

Cancelar, fechar, Escape ou formulário inválido não confirmam o serviço. Uma solicitação administrativa interrompida permanece em Pendentes para retomada. No acesso direto ao formulário, fechar retorna a Solicitações. Erros preservam o preenchimento; conflitos de versão exigem consultar os dados atualizados antes de confirmar.

Sem JavaScript, os mesmos links abrem `/tarefas/confirmar-servico/{id}/` como página completa. O POST antigo de aprovação administrativa redireciona para esse formulário, sem confirmar. O salvamento tradicional retorna ao detalhe do agendamento; o modal apresenta a confirmação, Ver tarefa e Concluir, atualizando a origem. Não há alterações no `sheet-layout` nem modal de detalhes de tarefas.

## Garantia no servidor

`review_booking` exige dados de uma tarefa para aprovar serviços. A solicitação deve estar pendente, não cancelada e na versão enviada. O vínculo é definido no servidor e não pode ser substituído pelo formulário ou pela API.

A confirmação, criação da tarefa, responsáveis, equipamentos, materiais e os dois históricos compartilham uma transação. A validação existente da tarefa continua exigindo um serviço confirmado; esse estado intermediário só existe dentro da transação. Qualquer falha desfaz todas as gravações, mantendo a solicitação pendente. A tarefa começa em Demanda, versão 1; a aprovação avança a versão do agendamento e registra avaliador/data sem mudar o solicitante. Locks e versão impedem tarefas duplicadas em reenvios ou confirmações simultâneas da mesma solicitação.

As rotas de confirmação exigem administração ativa e CSRF. A criação direta de `AgendaServico` no Django Admin técnico foi desabilitada, pois seu formulário genérico não executa esse fluxo; situação e metadados já são não editáveis ali. Nenhum modelo ou migration foi alterado. Agendamentos anteriormente confirmados e tarefas existentes permanecem intactos; esta regra não impede posteriormente excluir ou alterar tarefas pelas ações já autorizadas.

## API

Criar serviço em `POST /api/v1/agendamentos/` agora retorna `situacao: "pendente"` também para administradores. Para confirmar, o administrador envia:

```http
POST /api/v1/agendamentos/servico/{id}/confirmar/
Content-Type: application/json
```

```json
{
  "versao": 1,
  "tarefa": {
    "descricao": "Executar o serviço solicitado",
    "responsaveis": [2, 3],
    "equipamentos": [1],
    "materiais_gastos": [{"material": 1, "quantidade": "2 peças"}]
  }
}
```

O conteúdo de `tarefa` reutiliza os campos graváveis da API de tarefas, exceto `agendamento_servico`, definido pelo endpoint. Status, prazo, IDs, versão inicial e metadados não podem ser impostos pelo cliente. Os campos singulares continuam compatíveis para vínculos unitários. Sucesso retorna HTTP 200 com o agendamento confirmado; validação retorna 400, falta de permissão/CSRF 403 e conflito 409. Reenviar a mesma versão não cria outra tarefa.

O modal de criação administrativa recebe `next_url` no JSON para continuar ao formulário da tarefa. O modal de confirmação usa `X-Task-Modal: 1`: fragmentos sem cache, erro de validação 400, conflito 409 e sucesso 201 com `saved`, `message` e `detail_url` da tarefa.

## Verificação

- `python manage.py test --noinput`: 586 testes passaram, incluindo rollback, permissões, CSRF, campos protegidos, pluralidade de vínculos, solicitação cancelada/alterada, reenvio e confirmações concorrentes.
- `python manage.py test inovalab_app.tests.portability --settings=inovalab_app.tests.host_settings --noinput`: 7 testes passaram, com integração ao usuário Django nativo e app montado por prefixo.
- `manage.py check`, `makemigrations --check --dry-run`, `node --check` dos modais e `git diff --check`: sem erros ou migrations pendentes.
- Chromium com banco SQLite isolado: confirmação a partir de Solicitações, cancelamento, validação, retenção do preenchimento, conflito após edição em outra tela, confirmação válida, criação administrativa seguida de tarefa, cancelamento dessa etapa e conclusão sem JavaScript. Prefixo `/laboratorio/` preservado.
- Modal conferido em 1366, 768, 390 e 360 px sem overflow após o ajuste de viewport; ações Confirmar/Recusar com alturas equivalentes. Auditoria WCAG 2 A/AA do modal sem violações.

Os dados fictícios do navegador ficam em `.private/task-modal-ux-20261008/browser-2.sqlite3`; o banco local do projeto não foi alterado. Restam a depuração pelo responsável com dados reais, outros navegadores e a concorrência em PostgreSQL.
