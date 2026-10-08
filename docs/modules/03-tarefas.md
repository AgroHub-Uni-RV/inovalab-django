# Módulo 3 — Tarefas

> Atualização de 08/10/2026: vínculo obrigatório ao agendamento de serviço, recursos opcionais e select de status. Consulte [25-servicos-tarefas-infraestrutura.md](25-servicos-tarefas-infraestrutura.md); os contratos anteriores abaixo permanecem como histórico.

Implementação de 01/10/2026: quadro único com quatro colunas, detalhe, criação/edição/exclusão administrativa, transições e histórico. As telas usam formulários e botões simples; interface e API chamam as mesmas operações de negócio.

## Executar

```powershell
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py runserver
```

A migração de tarefas já foi aplicada no checkout local, de forma aditiva. Entre em [login](http://127.0.0.1:8000/entrar/) e abra [Tarefas](http://127.0.0.1:8000/tarefas/). Administradores do laboratório podem criar a primeira demanda. Não foram carregadas tarefas demonstrativas permanentes.

## Regras e escolhas do MVP

Administradores ativos do grupo `Administradores` e superusuários ativos gerenciam todas as tarefas; `is_staff` sozinho não concede administração. Usuários internos ativos consultam somente tarefas atribuídas a eles e podem iniciar/enviar suas entregas. A mesma restrição protege detalhes, histórico, listas e contagens; ID alheio, excluído ou inexistente retorna 404.

Serviço, descrição e responsável são obrigatórios; descrição é aparada e não aceita apenas espaços. Nova atribuição exige serviço disponível e responsável ativo. Se esses cadastros forem desativados depois, os vínculos existentes continuam consultáveis/editáveis e administradores podem concluir seu fluxo. Serviço e responsável possuem referências protegidas contra exclusão física.

O responsável pediu execução direta com plano simples. Para as lacunas Q02/Q03/Q04/Q08 foram adotadas escolhas de implementação, ajustáveis durante a depuração: um quadro do laboratório, início real automático, prazo opcional com data/hora, conclusão automática, reabertura em criação e exclusão lógica. Essas escolhas não representam novas respostas do responsável às questões originais.

| Ação | Origem → destino | Quem executa | Datas |
| --- | --- | --- | --- |
| Criar | — → `demanda` | Admin | Início/conclusão vazios |
| `iniciar` | `demanda` → `criacao` | Responsável ou admin | Registra início |
| `enviar` | `criacao` → `avaliacao` | Responsável ou admin | Preserva início |
| `aprovar` | `avaliacao` → `concluido` | Somente admin | Registra conclusão |
| `recusar` | `avaliacao` → `criacao` | Somente admin | Preserva início |
| `reabrir` | `concluido` → `criacao` | Somente admin | Limpa conclusão; conserva evento anterior |

Não há `re-criar` nem atalhos para concluir. Edição administrativa altera somente serviço, descrição, responsável e prazo; status e datas automáticas mudam por transições. A conclusão anterior fica no histórico ao reabrir. Prazo vencido é permitido e não impede iniciar uma tarefa atrasada.

Exclusão exige confirmação no navegador e retira a tarefa de todas as consultas/contagens. Os dados e eventos permanecem no banco, sem tela de restauração neste módulo. Histórico guarda ator/nome, instante, ação, estados e alterações dos campos; API expõe os valores anteriores/novos. A web apresenta os eventos em linguagem simples. Histórico das excluídas fica retido no banco, fora da API/interface operacional.

Listas/quadro e histórico têm 25 registros por página. Contagens das colunas abrangem todo o escopo autorizado; cartões representam a página atual, ordenada pelos IDs mais recentes. Alteração de status usa botões no detalhe. Arrastar, comentários, anexos, filtros avançados e quadros múltiplos ficam para evolução.

## Web

`/tarefas/`, `/tarefas/nova/`, `/tarefas/{id}/`, `/tarefas/{id}/editar/`, `/tarefas/{id}/excluir/`, `/tarefas/{id}/transicoes/` (somente POST) e `/tarefas/{id}/historico/`.

GET sem sessão redireciona ao login. Formulários usam CSRF e versão oculta; dados inválidos retornam erros sem gravação. Alteração baseada em página antiga retorna 409 e pede atualização. Gerenciar tarefa própria sem perfil administrativo retorna 403; acesso a tarefa alheia retorna 404. GET da confirmação de exclusão não altera dados.

## API por sessão

| Caminho | Métodos e uso |
| --- | --- |
| `/api/v1/tarefas/` | GET lista autorizada; POST cria (admin) |
| `/api/v1/tarefas/{id}/` | GET detalhe; PUT/PATCH editam dados (admin); DELETE exclui logicamente (admin) |
| `/api/v1/tarefas/{id}/transicoes/` | POST com `acao` e `versao` |
| `/api/v1/tarefas/{id}/historico/` | GET histórico autorizado, paginado |
| `/api/v1/tarefas/responsaveis/` | GET opções de contas ativas, somente admin, paginado; `id`, `username`, `nome` |

Mesmo host do login, sessão Django, JSON e CSRF nas escritas (`X-CSRFToken` com cookie `csrftoken`). API sem sessão/inativa retorna 403. Não há credencial de integração externa nova.

Listas retornam `count`, `next`, `previous`, `results`; usar `?page=2`. Tarefa retorna `id`, `servico`, `servico_nome`, `descricao`, `responsavel`, `responsavel_nome` (username), `status`, `inicio`, `prazo`, `conclusao`, `versao`, `acoes_permitidas`. Datas usam ISO 8601 com fuso; entradas sem fuso usam Brasília. A interface exibe Brasília.

POST aceita somente `servico` (ID), `descricao`, `responsavel` (ID) e `prazo` opcional/nulo. Exemplo:

```json
{"servico": 4, "descricao": "Produzir protótipo", "responsavel": 2, "prazo": "2026-11-01T14:00:00-03:00"}
```

IDs dependem de seu banco. PUT exige os três campos obrigatórios e `versao`; PATCH exige `versao` e altera somente campos fornecidos. Campos opcionais omitidos permanecem. Status, início, conclusão, ID e campos desconhecidos são rejeitados em escritas. Criar não aceita `versao`; a primeira é 1.

```json
{"descricao": "Descrição corrigida", "versao": 1}
```

Transição aceita exatamente:

```json
{"acao": "iniciar", "versao": 1}
```

DELETE exige corpo JSON `{"versao": 1}`. Versão deve ser número inteiro positivo; edição, transição e exclusão incrementam a versão. Atualização condicional no banco e evento na mesma transação impedem sobrescrever uma versão já modificada, inclusive no SQLite. Isso não substitui testes de carga/concorrência no ambiente de implantação.

GET/transição/edição retorna 200; criação 201; exclusão 204 sem corpo. Erros: 400 por campo para payload/regra inválida, 403 para sessão/permissão/CSRF, 404 para ID fora do escopo, 409 para versão antiga (`{"code": "versao_desatualizada", "detail": "..."}`). Métodos não suportados retornam 405. HEAD/OPTIONS também exigem autenticação.

Eventos retornam `id`, `ator` (ID, ou nulo se conta técnica sem vínculos for removida), `ator_nome`, `instante`, `acao`, `status_anterior`, `status_novo`, `alteracoes`. Cada alteração contém `anterior`/`novo`; referências são IDs e datas ISO 8601. Eventos ordenados pelo ID mais recente. Não existe endpoint para editar/apagar histórico.

## Verificação e depuração

**117 testes passaram**: 44 novos (16 domínio, 14 web e 14 API) e os 73 anteriores. Check, migrações e dependências sem pendências. A revisão independente verificou escopo, transições, atomicidade do evento e atualização condicional, inclusive simulando falha de gravação do histórico e alteração após carregar uma versão, em banco isolado.

Um achado de precisão do prazo foi corrigido: editar somente a descrição na web preserva os segundos e a precisão mais fina recebida pela API. O teste de regressão reproduziu a perda antes da correção e passou depois; a suíte completa passou após a correção. O formulário permite editar segundos e conserva frações existentes quando o prazo não foi alterado.

Chrome: login, criação e edição por admin sem staff, início pelo responsável usando teclado, envio, recusa, novo envio, aprovação, reabertura, histórico, consulta JSON e exclusão com confirmação. Página desatualizada retornou 409; outro usuário recebeu 404 para tarefa/histórico alheios e 403 para cadastro; contagens ficaram restritas. Nome de serviço com 150 caracteres e layout a 360 px verificados visualmente, sem rolagem horizontal; CSS carregado e nenhuma exceção JavaScript nas instâncias finais. Respostas 403/404/409 negativas são esperadas. A primeira instância de desenvolvimento não localizou o template; uma instância nova e o carregador em processo novo localizaram corretamente, sem alteração de produto. A verificação ocorreu em porta 8001, com servidor temporário encerrado ao final.

As três contas, um serviço e uma tarefa temporários foram removidos depois da verificação; IDs anteriores foram conferidos e preservados. Não há dados demonstrativos permanentes. Ao atualizar um servidor que já estava aberto, reinicie-o para carregar o novo app.

Dois achados menores ficam registrados para evolução: diferenças de representação de fuso podem gerar um evento de prazo mesmo sem mudar o instante pela API; a web mostra quem realizou cada ação, enquanto os campos anteriores/novos são consultáveis pela API. Carga, concorrência real no banco de implantação e outros navegadores ficam para testes mais profundos.

```powershell
& .\venv\Scripts\python.exe manage.py test tarefas
& .\venv\Scripts\python.exe manage.py test
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Para aprofundar:

1. Admin cria uma tarefa para cada responsável; cada pessoa consulta somente as próprias, inclusive URLs/API/histórico/contagens. Repita com staff sem grupo.
2. Execute iniciar → enviar → recusar → enviar → aprovar → reabrir; confira datas, histórico e ausência de atalhos por payload adulterado.
3. Reatribua uma tarefa; antigo responsável perde acesso imediatamente, novo responsável recebe.
4. Abra duas abas; altere na primeira e tente editar/mover/excluir na antiga: 409, dados e eventos preservados. Aprofunde concorrência com conexões reais e banco de implantação.
5. Desative serviço/responsável após atribuição; confirme preservação dos vínculos e rejeição de novas atribuições inativas.
6. Exclua pela confirmação/API; confira retirada das consultas e retenção no banco. Não apagar o banco para testar.
7. Teste prazo vencido/nulo, datas com fusos distintos, descrição vazia/longa e mais de 25 tarefas/eventos, incluindo teclado, celular e outro navegador.
8. Tente operações sem CSRF, após logout e após desativar uma conta autenticada; confira rejeição e nenhuma gravação parcial.

Depurar este módulo antes de agenda. [Plano simples](../superpowers/plans/2026-10-01-tarefas.md).
