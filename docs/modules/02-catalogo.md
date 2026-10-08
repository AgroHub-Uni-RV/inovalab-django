# Módulo 2 — Catálogo

> Atualização de 08/10/2026: serviços definidos por solicitação e Infraestrutura somente com equipamentos. Consulte [25-servicos-tarefas-infraestrutura.md](25-servicos-tarefas-infraestrutura.md); os contratos anteriores abaixo permanecem como histórico.

**Atualização de 07/10/2026:** o cadastro/modelo de espaços foi removido. O catálogo atual tem somente Serviços e Equipamentos; telas e API `/espacos/` deixaram de existir. As descrições de espaços abaixo registram entregas anteriores. Ver [remoção de espaços](11-remocao-espacos.md).

Entrega de 01/10/2026: serviços, equipamentos e espaços, com listas, detalhes, cadastro/edição, API autenticada e onze serviços iniciais do PDF. Frontend simples; as páginas anteriores de identidade foram preservadas e ganharam um link **Catálogo**.

## Executar

No PowerShell, na pasta do projeto:

```powershell
& .\venv\Scripts\python.exe -m pip install -r requirements.txt
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py carregar_servicos_iniciais
& .\venv\Scripts\python.exe manage.py runserver
```

As migrações do catálogo já foram aplicadas no banco deste checkout; repeti-las é seguro. A primeira migração cria as tabelas e restrições; a segunda carrega os onze serviços. O comando de carga cria apenas serviços ausentes, usando chave técnica estável: não duplica cadastros após renomeá-los nem sobrescreve nome, descrição ou status editados.

Entre em [login local](http://127.0.0.1:8000/entrar/) com sua conta e clique em **Catálogo**, ou abra [Serviços](http://127.0.0.1:8000/catalogo/servicos/). Use **Equipamentos** e **Espaços** para os demais cadastros. Equipamentos e espaços começam sem registros demonstrativos.

Se precisar da primeira conta técnica em outro ambiente, use `manage.py createsuperuser`. Para permitir manutenção a uma conta interna sem acesso técnico, atribua-lhe o grupo `Administradores` pelo Django Admin.

## Permissões e campos

Todos os usuários internos ativos consultam. Somente membro ativo de `Administradores` ou superusuário ativo cadastra/edita. `is_staff` isolado não concede escrita; o grupo de negócio não concede gestão técnica de contas.

| Cadastro | Campos | Status |
| --- | --- | --- |
| Serviço | Nome obrigatório até 150 caracteres; descrição opcional | `disponivel`, `indisponivel` |
| Equipamento | Nome obrigatório até 150 caracteres; descrição opcional | `disponivel`, `ocupado`, `indisponivel` |
| Espaço | Nome obrigatório até 150 caracteres; capacidade inteira de 1 a 2147483647 | `disponivel`, `ocupado`, `indisponivel` |

Nome é aparado e pode se repetir: cada cadastro tem ID próprio. Status inicial é disponível. O estado ocupado é manual nesta entrega; reservas e cálculo de ocupação pertencem à agenda futura.

Para retirar um cadastro de uso, edite seu status para **Indisponível**. O ID e os dados são preservados. Não há exclusão física pela interface/API; nenhuma mudança do catálogo cria ou cancela tarefas/reservas.

## Rotas web

Para cada categoria `servicos`, `equipamentos` ou `espacos`:

- `/catalogo/{categoria}/`: lista paginada em 25 registros, ordenada por nome/ID.
- `/catalogo/{categoria}/{id}/`: detalhe.
- `/catalogo/{categoria}/novo/`: cadastro, somente administradores do laboratório.
- `/catalogo/{categoria}/{id}/editar/`: edição, mesma permissão.

Formulários usam POST com CSRF. Sem sessão, GET redireciona ao login; sem permissão, acesso direto à manutenção retorna 403. ID inexistente retorna 404. Erros de campo impedem a gravação; sucesso redireciona ao detalhe com mensagem.

## API entregue

Autenticação por sessão Django, usando o mesmo host do login. `localhost` e `127.0.0.1` têm cookies distintos. Respostas JSON, sem chave técnica dos serviços iniciais.

| Rota | Métodos |
| --- | --- |
| `/api/v1/servicos/` | GET lista; POST cadastra |
| `/api/v1/servicos/{id}/` | GET detalhe; PUT/PATCH editam |
| `/api/v1/equipamentos/` e detalhe `/{id}/` | Mesmas operações |
| `/api/v1/espacos/` e detalhe `/{id}/` | Mesmas operações |

Listas retornam `count`, `next`, `previous`, `results`, com 25 registros por página e parâmetro `page`. Detalhe retorna o objeto diretamente. ID é somente leitura; `codigo_inicial` nunca é exposto e tentativas de editá-lo são rejeitadas. DELETE não é suportado.

Exemplo de serviço (o ID depende do banco):

```json
{"id": 4, "nome": "Impressão 3D", "descricao": "Modelagem e Impressão 3D.", "status": "disponivel"}
```

Exemplo de cadastro de espaço:

```json
{"nome": "Sala de reunião", "capacidade_maxima_de_pessoas": 8, "status": "disponivel"}
```

GET válido retorna 200; POST, 201; PUT/PATCH, 200. Validação retorna 400 com erros por campo, sem alterações parciais; sessão ausente/inativa ou permissão negada, 403; ID ausente, 404; DELETE autorizado com CSRF válido, 405. Sem token CSRF, a autenticação por sessão pode retornar 403 antes de verificar o método. HEAD/OPTIONS também exigem autenticação.

PUT exige os campos obrigatórios do cadastro; PATCH altera apenas os fornecidos. Campos opcionais omitidos na edição são preservados, inclusive em PUT. POST sem status usa disponível. Para escrita via JavaScript, enviar o cookie da sessão e o cookie `csrftoken` no cabeçalho `X-CSRFToken`.

Após login, este exemplo consulta o catálogo no console do navegador:

```javascript
fetch('/api/v1/servicos/').then(response => response.json()).then(console.log);
```

Não há autenticação de sistemas externos neste módulo; a etapa de integração terá contrato próprio.

## Verificações executadas

38 testes de catálogo e 35 de identidade/configuração passaram: **73 testes no total**. Cobrem modelos/restrições, carga repetível, preservação de edições, campos privados, consulta e escrita nos três cadastros, permissões, paginação, CSRF, validação sem persistência parcial e revogação da sessão.

A revisão independente identificou que chamadas diretas à operação compartilhada podiam converter uma capacidade fracionária ou booleana em inteiro antes da validação. A validação do modelo agora verifica o valor original. O teste de regressão reproduziu a falha antes da correção e passou depois, cobrindo criação, edição sem persistência parcial e `full_clean`, inclusive valores não finitos. A suíte completa passou após a correção; não foi necessária nova migração.

`manage.py check`, `makemigrations --check --dry-run`, `pip check` e `git diff --check` sem pendências. Migrações locais aplicadas e repetidas; carga repetida criou zero serviços adicionais. Contas anteriores preservadas.

No Chrome: login, listagem dos onze serviços, leitura JSON, cadastro de equipamento/espaço por administrador sem staff, edição para indisponível, capacidade zero rejeitada, usuário comum sem ações de manutenção, URL de cadastro negada 403, API de consulta 200 e API sem sessão 403 após logout. Uso por teclado e layout a 360 px verificados, inclusive nome de 150 caracteres; CSS carregado e nenhuma exceção da aplicação registrada. Respostas 400/403 nos cenários negativos são esperadas. Contas e registros temporários foram removidos; onze serviços iniciais e dados anteriores permanecem.

## Testes para repetir e aprofundar

```powershell
# Apenas catálogo
& .\venv\Scripts\python.exe manage.py test catalogo
# Regressão completa, incluindo identidade
& .\venv\Scripts\python.exe manage.py test
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
```

Para sua depuração posterior:

1. Entre com uma conta comum e outra do grupo `Administradores`; confirme consulta para ambas e manutenção só para a segunda. Verifique também um staff sem grupo.
2. Crie e edite serviços, equipamentos e espaços; confira persistência após atualizar a página e consulte os mesmos IDs na API.
3. Tente nomes vazios/longos, status inválidos e capacidades 0, negativas, fracionárias, booleanas e acima de 2147483647; confirme rejeição sem gravação parcial na web/API.
4. Renomeie um serviço inicial, edite descrição/status e execute `carregar_servicos_iniciais` duas vezes; confirme ID e edições preservados. Não apagar seu banco para esse teste.
5. Com mais de 25 registros, percorra todas as páginas web/API e confira ordenação e total.
6. Tente POST/PATCH como usuário comum, como staff sem grupo e sem CSRF; confira 403 e dados inalterados. Com administrador e CSRF válido, tente DELETE: 405.
7. Desative uma conta já autenticada; confira perda de acesso na próxima requisição. Repita após logout.
8. Confira nomes/descrições reais do laboratório, navegação por teclado, celular e outro navegador. Testes de uso prolongado, volume e concorrência ficam para sua avaliação; agenda ainda não está implementada.

Corrigir eventuais problemas deste módulo antes de iniciar tarefas. [Especificação](../superpowers/specs/2026-10-01-catalogo-design.md) · [Plano](../superpowers/plans/2026-10-01-catalogo.md).
