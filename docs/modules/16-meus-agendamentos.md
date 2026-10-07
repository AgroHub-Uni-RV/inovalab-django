# Meus agendamentos

A solicitação de 07/10/2026 substitui a página limitada a Minhas visitas por uma consulta pessoal de **Serviços**, **Equipamentos** e **Visitas**. A entrada principal é `/agenda/meus/`; `/agenda/visitas/` mantém compatibilidade com links antigos e apresenta a mesma consulta unificada. A antiga view e o template de listagem exclusiva de visitas foram removidos.

## Acesso e titularidade

Qualquer conta autenticada e ativa pode consultar a própria lista e os próprios detalhes. Usuários externos usam o cabeçalho institucional; equipe e administradores usam a estrutura interna. O menu da conta, o perfil, a sidebar interna e o cabeçalho da agenda oferecem Meus agendamentos. O login preserva o destino de consulta pessoal para contas externas.

A exceção no middleware é limitada às rotas pessoais, que aceitam somente GET/HEAD/OPTIONS. Não concede criação, edição, cancelamento, solicitações administrativas, APIs internas ou acesso ao dashboard para usuários externos. A sincronização da sessão AgroHub continua antes das consultas.

As consultas locais sempre filtram `criado_por` pela conta da sessão, inclusive para administradores. Não aceitam um usuário-alvo na URL. Categoria e ID identificam os detalhes, sem colisão entre tabelas. Registros cancelados e recusados/rejeitados permanecem visíveis; o detalhe inclui período, motivo, observações, equipamentos/material quando aplicável e histórico local. O detalhe pessoal não oferece ações de alteração.

| Rota | Responsabilidade |
| --- | --- |
| `/agenda/meus/` | Lista pessoal das três categorias, com busca/mês/categoria/situação e 25 itens por página |
| `/agenda/meus/<categoria>/<id>/` | Detalhe local pertencente ao usuário, incluindo cancelados |
| `/agenda/meus/visitas/<id>/` | Detalhe remoto autorizado pela sessão pessoal |
| `/agenda/visitas/` | Compatibilidade com a antiga entrada e seus filtros `status` |

Situações da lista: Pendente, Confirmado, Recusado e Cancelado. A pesquisa considera número, nome/título, motivo, observações e sala; o filtro de mês considera a interseção do período no fuso de Brasília. Paginação conserva os filtros.

## Limite do contrato remoto

O schema público descreve a listagem de reservas próprias, mas a implementação `ReservaQuerySet.owned_by` retorna **todas** as reservas quando a conta remota possui `is_staff=true`. O serializer não informa ID do solicitante e não há filtro de titular no `ReservaFilterSet`. Portanto não é possível separar com segurança as visitas próprias dessas contas apenas no InovaLab. Fontes primárias consultadas somente para leitura: [schema](https://agrohub.unirv.edu.br/api/v1/schema/?format=json), [models](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/models.py), [serializers](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/api/serializers.py) e [filters](https://github.com/AgroHub-Uni-RV/unirv-monolith/blob/main/apps/agendamentos/filters.py).

O responsável respondeu explicitamente **Manter o monólito sem alterações**. Com essa restrição, a consulta pessoal só lê visitas quando o perfil sincronizado confirma `is_staff=false`. Nos outros casos informa indisponibilidade da consulta individual e mantém os agendamentos locais próprios. Não deduz autoria por nome, não amplia a consulta ao consultar detalhes e não cria espelho, vínculo, fila ou cache persistente de visitas. As consultas administrativas já existentes continuam usando sua visibilidade autorizada na agenda e em Solicitações.

Se a API de reservas falhar para uma conta comum, a lista mantém os registros locais e informa que as visitas não puderam ser carregadas. Pendentes, confirmadas, recusadas e canceladas remotas são consultadas diretamente da API, sem escrita no AgroHub.

## Verificação

`agenda/tests/test_personal.py` cobre contas comuns e administradores, isolamento por titular, categorias com IDs iguais, registros cancelados/recusados, detalhes, acesso anônimo/inativo, bloqueio de POST, filtros/paginação, falhas remotas, bloqueio preventivo de visitas com visibilidade staff, navegação e retorno após login. Os testes do provedor usam HTTP simulado.

```powershell
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Resultado: **590 testes Django passaram**, incluindo nove testes novos da consulta pessoal. Esses nove também passaram isoladamente após reforçar a verificação dos detalhes e da preservação dos registros locais quando a API falha. `check`, ausência de novas migrations e `git diff --check` passaram.

A ferramenta de navegador não disponibilizou apps nem browsers nesta sessão. A verificação de navegação, renderização de templates, filtros, detalhes e permissões foi executada pelo cliente Django; a conferência visual no navegador permanece pendente.

Na depuração, conferir a apresentação no desktop/celular, navegação a partir do perfil, filtros e detalhes com dados reais; validar visitas com uma conta sem staff no provedor. Visitas próprias de staff exigiriam evolução do contrato AgroHub, expressamente fora desta entrega.
