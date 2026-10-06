# Módulo 1 — Identidade e acesso

**Atualização de 06/10/2026:** login, cadastro, perfil/foto e recuperação de senha agora usam exclusivamente Accounts do AgroHub. Consulte o [contrato e a execução atuais](09-agrohub-accounts.md). As instruções de senha local e `createsuperuser` abaixo documentam a entrega histórica de 01/10 e não autenticam na versão atual.

Entrega de 01/10/2026: contas internas pelo Django Admin, login por usuário/senha, página privada, logout e API da identidade atual. A próxima etapa depende da depuração deste módulo pelo responsável.

## Executar localmente

No diretório do projeto, com Python 3.14 instalado, use PowerShell. Se o `venv` já existe, pule sua criação.

```powershell
python -m venv venv
& .\venv\Scripts\python.exe -m pip install -r requirements.txt
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py createsuperuser
& .\venv\Scripts\python.exe manage.py runserver
```

O cadastro inicial solicita usuário, e-mail opcional e senha. Não há conta ou senha padrão. As migrações criam o grupo `Administradores` sem duplicá-lo; o banco SQLite local não é versionado.

Abra [a página de login](http://127.0.0.1:8000/) e entre com a conta criada. O login padrão abre `/index/`; o perfil fica em `/perfil/`. **Administrar contas** abre a nova tela `/usuarios/`, exclusiva de superusuários ativos. Use **Configurar usuários** para a manutenção técnica no Django Admin. Em **Contas e acesso → Usuários → Adicionar**, cadastre contas com autenticação por senha habilitada. Após salvar, edite nome, e-mail, ativação e grupos conforme necessário.

## Papéis

| Conta | Identidade de negócio | Gestão de contas e grupos |
| --- | --- | --- |
| Usuário ativo sem grupo | Usuário interno | Não |
| Membro ativo de `Administradores` | Administrador do laboratório | Não |
| Apenas `is_staff` | Usuário interno | Não, mesmo com permissões de usuários/grupos |
| Superusuário ativo | Administrador do laboratório | Sim; `createsuperuser` também define `is_staff` |
| Conta inativa | Sem acesso autenticado | Não |

O grupo classifica o papel do laboratório. As permissões operacionais de catálogo, tarefas e demais módulos serão implementadas nas suas entregas. Neste módulo somente o superusuário ativo gerencia contas e grupos; mantenha o indicador de acesso ao admin (`is_staff`) para acessar o site administrativo.

## Rotas entregues

| Rota | Comportamento |
| --- | --- |
| `/` e `/entrar/` | GET exibe login; POST com CSRF autentica conta ativa e segue por padrão ao index |
| `/index/` e `/painel/` | Dashboard privado; `/painel/` é alias |
| `/perfil/` | Página privada com nome, usuário, papel e botão Sair |
| `/usuarios/` | Cartões, busca e filtros; somente superusuários ativos |
| `/sair/` | POST com CSRF encerra sessão; GET retorna 405 |
| `/admin/` | Administração nativa do Django; gestão de identidade exclusiva do superusuário |
| `/api/v1/me/` | GET autenticado por sessão retorna a identidade atual em JSON |

Sem sessão, a página privada redireciona para login. Erros de login são genéricos; destinos externos no parâmetro `next` são rejeitados. Desativar uma conta impede novo login e revoga acesso nas próximas requisições web/API.

## Contrato da API

Após entrar pelo navegador, abra `/api/v1/me/` no mesmo endereço e navegador. `localhost` e `127.0.0.1` têm cookies separados: mantenha o mesmo host durante o teste.

```json
{
  "id": 1,
  "username": "ana",
  "first_name": "Ana",
  "last_name": "Silva",
  "is_business_admin": false
}
```

O ID é gerado pelo banco. A resposta contém exatamente esses cinco campos; parâmetros como `?id=2` não alteram o usuário consultado. Sem sessão válida, retorna `403` e um objeto com `detail`, sem identidade. POST/PUT/PATCH/DELETE autenticados com CSRF válido retornam `405`; sem CSRF válido, a autenticação por sessão pode retornar `403` antes da verificação do método. HEAD e OPTIONS seguem o comportamento padrão do DRF, também exigindo autenticação.

A API é somente leitura e usa a sessão Django. A autenticação de sistemas externos terá contrato próprio em outra entrega.

## Configuração

Por padrão, desenvolvimento usa debug ativo, hosts `localhost,127.0.0.1` e chave exclusivamente local. `.env` não é carregado automaticamente; configure as variáveis no processo PowerShell antes de iniciar Django:

```powershell
$env:DJANGO_DEBUG = 'true'
$env:DJANGO_ALLOWED_HOSTS = 'localhost,127.0.0.1'
# Opcional no desenvolvimento; use uma chave privada fornecida pelo seu ambiente.
$env:DJANGO_SECRET_KEY = 'substitua-por-uma-chave-privada'
```

`DJANGO_DEBUG` aceita true/1/yes/on ou false/0/no/off, sem diferenciar maiúsculas e com espaços aparados. Valores desconhecidos são erro. Sem debug, `DJANGO_SECRET_KEY` ausente, vazia ou composta somente de espaços impede a inicialização. Hosts são separados por vírgulas e aparados. Produção e hospedagem não foram validadas nesta entrega.

## Roteiro para depuração

1. Sem login, abra `/`: deve exibir o login. `/index/` e `/perfil/` devem redirecionar ao login com `next` local.
2. Entre como superusuário, abra o admin e crie uma conta comum com senha. Edite seu nome e e-mail.
3. Em outro navegador ou janela privada, tente uma senha errada: deve aparecer mensagem genérica. Entre com a senha correta e confira nome, usuário e papel **Usuário interno**, sem link para gerenciar contas.
4. Abra `/api/v1/me/`: confira as cinco chaves e somente a identidade dessa conta. Repita com `?id=<id-de-outra-conta>`.
5. No admin, adicione a conta ao grupo `Administradores`. Atualize sua página/API: o papel deve mudar, sem conceder gestão técnica de usuários ou grupos.
6. Desative a conta no admin e atualize sua página privada/API: acesso deve ser negado. Reative-a e entre novamente.
7. Abra `/sair/` por GET: deve retornar 405 e manter a sessão. Use o botão **Sair da conta**: deve voltar ao login e a API deve retornar 403.
8. Verifique login e página privada no celular ou a 360 px. Navegue com Tab/Shift+Tab e use Enter para enviar o formulário; o foco deve permanecer visível.

## Verificações da entrega

```powershell
& .\venv\Scripts\python.exe manage.py test
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\venv\Scripts\python.exe -m pip check
git diff --check
```

35 testes automatizados passaram no runtime local Python 3.14.3, Django 6.1.1 e DRF 3.18.1. Eles cobrem criação/edição de contas, hash e validação de senha, privilégios, configuração, sessão, CSRF, redirecionamento, inativação e contrato JSON. Migração local aplicada e repetida sem alterações pendentes.

No Chrome automatizado foram verificados login com erro e sucesso, envio por teclado, página privada, API antes/depois do logout, acesso ao admin e cadastro de conta. Login e página privada foram inspecionados a 360 px; CSS carregado e nenhuma exceção de página registrada. A revisão independente encontrou rolagem horizontal na saudação de usuários com identificadores longos: corrigida a quebra de texto e confirmada largura de 360 px mesmo com username de 150 caracteres. Os 35 testes passaram novamente após o ajuste. As consultas sem sessão à API retornaram 403, como previsto. Contas temporárias de verificação removidas; não ficou conta provisionada no banco local.

## Revisão e decisões de execução

A revisão independente examinou código, testes, documentação e os cinco focos do plano. Não encontrou falhas de autorização ou sessão. O problema visual foi tratado como impeditivo para a entrega responsiva, reproduzido antes da correção e verificado depois. A entrega permanece na branch local `feat/identidade-acesso`, no checkout do IDE, aguardando depuração do responsável.

- Execução no checkout ativo em branch própria: atende à implementação no sistema e facilita depuração; custo de isolamento menor, pois as alterações ficaram visíveis durante o trabalho.
- Registros de progresso em PowerShell: substituem os auxiliares Bash indisponíveis neste ambiente; custo de acompanhamento manual, com evidências de testes e commits registradas.
- Django Admin mantém o favicon nativo ausente: pendência cosmética que produz um 404 em `/favicon.ico`, sem afetar login, estilos ou cadastro.
- Hospedagem, HTTPS, proteção contra tentativas repetidas e validação de produção ficam para a implantação: este módulo foi verificado para desenvolvimento local; não há garantia de operação pública.
- SSO, recuperação por e-mail e autenticação de sistemas externos continuam fora deste módulo, conforme a especificação; essas capacidades exigem entregas posteriores.
- Escrita por sessão sem CSRF válido pode retornar 403 antes de 405: preservada a proteção do DRF; clientes devem tratar os dois estados conforme o contrato.

Nenhum merge ou push foi executado; os commits e a aplicação permanecem disponíveis localmente para os testes do responsável.

[Especificação aprovada](../superpowers/specs/2026-10-01-identidade-e-acesso-design.md) · [Plano de implementação](../superpowers/plans/2026-10-01-identidade-e-acesso.md).
