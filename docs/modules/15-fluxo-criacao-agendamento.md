# Criação de agendamento por categoria

A solicitação de 07/10/2026 organiza a criação em duas etapas. Adicionar Agendamento abre `/agenda/novo/` com três cards quadrados e ícones: **Visita**, **Equipamento** e **Serviços**. Escolher um card abre somente o formulário correspondente. Os cards reorganizam as colunas conforme a largura disponível, incluindo a sidebar expandida; no celular ficam em uma coluna. Tipografia, espaçamentos e arredondamentos usam `core/static/core/ui.css`.

| Escolha | Formulário | Destino após confirmar |
| --- | --- | --- |
| Visita | `/agenda/visitas/novo/`: sala, título, pessoas, dia, horários e observações | API de reservas do AgroHub |
| Equipamento | `/agenda/novo/?categoria=equipamento`: equipamento, motivo, observações, dia e horários | `AgendaEquipamento` |
| Serviços | `/agenda/novo/?categoria=servico`: serviço, motivo, observações, dia, horários, equipamentos associados e material | `AgendaServico` |

Nos formulários locais de criação, a categoria é enviada como campo oculto e continua validada no servidor. Alterar tipo de agendamento e Voltar retornam à escolha. Categorias desconhecidas na abertura retornam HTTP 400 com a seleção disponível. O atalho `?categoria=visita` continua redirecionando para o formulário remoto.

**Confirmar agendamento** submete o formulário com POST e CSRF. Campos inválidos mantêm o formulário e os dados preenchidos para correção. Serviços e equipamentos continuam usando as validações e a gravação transacional existentes, incluindo disponibilidade, conflitos, autoria, histórico e regras de material. Solicitações da equipe são salvas como pendentes; administradores preservam a criação confirmada. Visitas são validadas e enviadas pela sessão AgroHub, que decide sua disponibilidade e situação, sem persistência local. A edição mantém seu fluxo próprio e a categoria original, mesmo se a URL receber outro parâmetro de categoria.

## Verificação

Os testes em `agenda/tests/test_create_flow.py` cobrem seleção sem formulário/gravação, categorias inválidas, campos específicos, preservação dos dados após erro, confirmação nas tabelas corretas e envio de visita a um provedor HTTP simulado sem registros locais. A suíte existente cobre permissões, CSRF, conflitos, erros do provedor e edição.

```powershell
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Resultado: **581 testes Django passaram**, incluindo os seis testes do novo fluxo. `check` não encontrou problemas, `makemigrations --check --dry-run` não detectou mudanças e `git diff --check` passou. Não há novas migrations.

A conferência visual no navegador ficou indisponível nesta sessão: a ferramenta não ofereceu Chrome nem navegador integrado. Na depuração, conferir os três cards, navegação de ida/volta, foco por teclado e formulários em desktop/celular com sidebar aberta e recolhida. Validar uma visita com a API real do AgroHub; os testes automatizados usam um provedor simulado.
