# Criação e edição de tarefas em modal

Entrega de 08/10/2026, solicitada pelo responsável. Esta etapa trata somente o módulo de Tarefas. A melhoria dos formulários e da edição em modal da Agenda permanece para a etapa seguinte, depois da depuração e autorização desta entrega.

## Fluxo do modal

Adicionar Tarefa no quadro e Nova tarefa no dashboard abrem um `dialog` sem mudar a URL de origem. Editar dados no detalhe reutiliza o mesmo componente. A criação e a edição exibem carregamento, bloqueiam fechamento e reenvio durante a gravação, mantêm os valores em erros de validação ou conflito e apresentam a confirmação com Ver tarefa e Concluir. Depois de salvar, o quadro, dashboard ou detalhe de origem é atualizado sem recarregar toda a página.

O modal fecha pelo botão, Cancelar, Escape ou clique no fundo e devolve o foco ao acionador. O foco permanece contido enquanto o diálogo está aberto. Enquanto um POST está em andamento, todas essas saídas ficam bloqueadas, inclusive Cancelar acionado pelo teclado. Falhas de carregamento permitem tentar novamente. Quando a resposta de um POST é incerta, a interface não reenvia automaticamente e orienta consultar o quadro para evitar duplicidade.

As URLs `/tarefas/nova/` e `/tarefas/{id}/editar/` continuam servindo páginas completas e aceitando POST tradicional. Com JavaScript, o acesso direto move o formulário para o modal; sem JavaScript, o mesmo formulário permanece funcional na página. O JavaScript deriva as rotas das URLs geradas pelo Django e funciona quando o app está montado sob um prefixo, como `/laboratorio/`.

## Formulário

O conteúdo foi dividido em três seções: Serviço e prazo, Descrição da tarefa e Equipe e recursos. O prazo herdado aparece em destaque e atualiza ao trocar o agendamento de serviço.

Responsáveis e equipamentos usam checkboxes com pesquisa e contador de selecionados. A seleção não depende mais de Ctrl/Command e continua acessível sem JavaScript. Pelo menos um responsável permanece obrigatório; equipamentos continuam opcionais.

Materiais aparecem em cartões numerados, cada um com material e quantidade textual própria. A inclusão e a remoção dinâmicas mantêm o contrato anterior do formset e seu fallback sem JavaScript. Nenhum modelo, migration, contrato da API, regra de permissão, status, prazo, versão, evento ou vínculo foi alterado.

## Contrato HTTP

Requisições do modal enviam `X-Task-Modal: 1`. GET e formulários inválidos retornam somente o fragmento marcado por `data-task-modal-content`, com `Cache-Control: no-store` e `Vary: X-Task-Modal`. Conflitos conservam HTTP 409. Um POST válido retorna JSON com `saved`, `message` e `detail_url`: HTTP 201 na criação e HTTP 200 na edição. Sem o cabeçalho, o redirecionamento tradicional ao detalhe é preservado.

Somente administradores recebem o componente e seus acionadores. As views continuam protegidas no servidor, e sessão, CSRF, campos estritos, concorrência otimista e gravação transacional mantêm as regras existentes. Se a sessão expirar, o modal reconhece a URL de login fornecida pelo hospedeiro, inclusive prefixo e parâmetros, tanto no carregamento quanto no envio.

## Verificação

| Comando ou cenário | Resultado |
| --- | --- |
| `python manage.py test --noinput` | 564 testes passaram |
| `python manage.py test inovalab_app.tests.portability --settings=inovalab_app.tests.host_settings --noinput` | 7 testes passaram |
| `manage.py check` / `makemigrations --check --dry-run` | Nenhum problema ou migration pendente |
| `node --check` nos dois scripts de Tarefas / `git diff --check` | Sem erros |
| Chromium, banco SQLite isolado | Criação, edição, pesquisa, seleções múltiplas, materiais, atualização da origem, foco e Escape passaram; com respostas atrasadas, preservou foco/filtros, bloqueou Cancelar durante POST e redirecionou GET/POST expirados ao login configurado |
| Layout e acessibilidade | 1366 e 360 px sem overflow; auditoria WCAG 2 A/AA do modal sem violações ou itens incompletos |

Os testes de navegador usaram dados fictícios em `.private/task-modal-ux-20261008/browser-2.sqlite3`; o banco local do projeto não foi alterado. A depuração restante deve conferir identidades e registros reais, outros navegadores e a integração com o provedor de autenticação.
