# Identidade pelo Accounts do AgroHub

Entrega de 06/10/2026. A confirmação do responsável — **somente login pelo AgroHub** — substitui o login por senha local, inclusive no Django Admin. Os seis fluxos usam a [documentação Accounts da UniRV](https://agrohub.unirv.edu.br/api/v1/schema/redoc/). Catálogo, tarefas, agenda e suas permissões continuam associados aos IDs locais do InovaLab.

## Telas e contrato

Base padrão: `https://agrohub.unirv.edu.br/api/v1/`. Cada rota remota abaixo é relativa a `accounts/`.

| Tela InovaLab | Operação Accounts | Campos |
| --- | --- | --- |
| `/` e `/entrar/` | POST `login/`, GET `me/` | username (usuário ou e-mail), password |
| `/registro/` | POST `register/`, GET `me/` | username, email, password, password_confirm; first_name, last_name, cpf e telefone opcionais |
| `/perfil/` | PATCH `me/`, GET `me/` | first_name, last_name, cpf, telefone |
| `/perfil/foto/` | PUT `me/picture/`, GET `me/` | multipart `profile_picture` |
| `/recuperar-senha/` | POST `password-reset/` | email |
| `/recuperar-senha/confirmar/` | POST `password-reset/confirm/` | uid, token, new_password, new_password_confirm |

Todas as escritas são POST no navegador e exigem CSRF. O cadastro autentica imediatamente com os tokens recebidos. Senhas novas têm entre 8 e 128 caracteres e confirmação. Erros de validação documentados aparecem junto ao campo; falhas do provedor apresentam uma mensagem de nova tentativa sem detalhes internos.

Usuário e e-mail são somente leitura em `me/`, por isso a interface mostra esses dados sem oferecer edição. Nome, sobrenome, CPF e telefone são editáveis. O formulário de foto é separado de **Salvar perfil**. Os campos aninhados opcionais de `ProfileData` não são oferecidos nesta entrega.

Fotos PNG/JPEG/WebP têm limite de 5 MB e 16 milhões de pixels; são convertidas para WebP com até 512 px antes do envio. Avatares usam um proxy com as permissões existentes, limite de download e conversão de imagem. A URL remota não fica no HTML e o download de mídia nunca recebe o JWT.

## Sessões e privilégios

Login e cadastro validam `access`/`refresh` e consultam `me/` como identidade autoritativa. O ID retornado vincula a conta em `User.agrohub_id`, que é único. Nome ou e-mail coincidentes com uma conta local **não** associam identidades; nesse caso, a nova conta recebe outro identificador local. Contas novas têm senha local inutilizável e nenhum privilégio administrativo. Os `roles`, `is_staff` e `is_superuser` do retorno remoto não concedem permissões no InovaLab.

Privilégios continuam locais: grupo `Administradores` para gestão do laboratório, superusuário ativo para gestão técnica de contas. Uma conta AgroHub vinculada e aprovada pode receber esses privilégios pelos mecanismos administrativos existentes. No primeiro acesso de uma instalação sem administrador vinculado, o responsável deve selecionar e promover a conta por seu **ID AgroHub verificado**, usando o shell administrativo; não executar `createsuperuser` esperando que a senha local autentique.

Contas antigas sem vínculo permanecem no banco, com seus relacionamentos e histórico, mas não entram por senha local. Uma migração de identidades antigas requer conferência explícita pelo responsável; esta entrega não associa usuários automaticamente nem transfere tarefas ou reservas entre IDs.

JWTs ficam na sessão de banco do Django, somente no servidor. Os tokens são persistidos após `login()` concluir a rotação/limpeza da sessão, inclusive ao trocar de conta na administração. Cada requisição privada de conta vinculada consulta `me/`. HTTP 401 permite uma renovação em `login/refresh/`; a identidade renovada precisa manter o mesmo ID. Credenciais revogadas ou conta inativa encerram o acesso. Indisponibilidade retorna 503 em páginas/APIs privadas e mantém a sessão para nova tentativa. **Sair** funciona mesmo sem o provedor disponível e elimina os tokens da sessão; a API não documenta revogação/logout remoto.

O único backend de senha é `accounts.backends.AgroHubBackend`. Sessões antigas gravadas com `ModelBackend` deixam de ser reconhecidas. A API interna `/api/v1/me/` mantém seu contrato anterior de cinco campos e ID local; o JWT AgroHub não autentica diretamente essa API. O adaptador de agendamentos externos conserva seu próprio contrato e credenciais.

## Recuperação de senha

A solicitação mostra a mesma confirmação independentemente de o e-mail existir. UID e token podem ser copiados do e-mail para a tela local, ou recebidos em `/recuperar-senha/confirmar/?uid=...&token=...`. O link é redirecionado imediatamente para a URL sem parâmetros; o token fica na sessão por até 30 minutos e não é renderizado no HTML. A captura usa `Referrer-Policy: no-referrer`; o formulário na URL limpa usa `same-origin`, mantendo o Origin do POST/CSRF válido também no desenvolvimento HTTP. As respostas têm `no-store`.

Recuperação é pública mesmo com sessão remota expirada. Confirmação bem-sucedida limpa a sessão e pede novo login. A documentação não fornece `callback`/`redirect_url` para configurar o destino do e-mail: esse destino depende do AgroHub. O fluxo manual permite confirmar aqui sem presumir uma configuração externa. O primeiro request de um link ainda contém UID/token na URL; configurar os logs do ambiente para não conservar seus parâmetros.

## Configuração e migração

Não é necessário cadastrar credenciais técnicas nem copiar JWTs para `.env`. A configuração padrão aponta para o AgroHub informado pelo responsável.

| Configuração | Padrão e uso |
| --- | --- |
| `AGROHUB_API_BASE_URL` | `https://agrohub.unirv.edu.br/api/v1/`; HTTPS obrigatório, HTTP somente em loopback com DEBUG ativo para testes |
| `AGROHUB_PHOTO_ALLOWED_HOSTS` | Vazio; aceita fotos da origem da API. Se a conta real retornar mídia em outro host, adicionar somente o host HTTPS confiável, separado por vírgula |
| `AGROHUB_API_TIMEOUT` | Setting de 10 segundos por requisição HTTP |

O cliente só acessa rotas Accounts fixas, rejeita redirecionamentos e limita respostas JSON a 512 KB. Respostas interrompidas, timeout, erro de rede e JSON inválido são tratados como falha do provedor. URL malformada de foto é descartada.

Aplicar a migração aditiva antes de iniciar a nova versão:

```powershell
& .\venv\Scripts\python.exe manage.py migrate --noinput
& .\venv\Scripts\python.exe manage.py runserver
```

`accounts.0004_identidade_agrohub` acrescenta ID/usuário/foto remotos, CPF e telefone. Não altera grupos, senhas ou relacionamentos de contas existentes. A migração foi aplicada ao SQLite local. Deploy e banco de produção não foram alterados nesta entrega; `.env.example` teve sua edição prévia preservada.

## Verificações e depuração

```powershell
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Resultado final: **472 testes passaram**, `check` sem problemas, `makemigrations --check --dry-run` sem alterações e `git diff --check` sem erros. Os 27 testes novos Accounts usam um servidor HTTP em loopback que reproduz o contrato publicado, incluindo JSON, Bearer, refresh e multipart. Não cadastram usuários ou enviam e-mails no AgroHub real. Cobrem colisão com administrador local, ausência de fallback, preservação de privilégios, troca de conta no admin, revogação/inativação, identidade trocada no refresh, CSRF, limite/redirect/falhas HTTP, foto inválida, reset com sessão expirada e proteção do token.

Navegador local: login, cadastro com entrada imediata, edição de perfil, upload de foto e exibição de avatares, solicitação e confirmação de recuperação, logout, URL limpa sem token no HTML. Perfil em 1200 px com sidebar expandida e em 360 px, formulários públicos em 360 px: sem rolagem horizontal. Mantidos Montserrat e componentes existentes.

Para depuração com uma conta real autorizada, validar:

1. Login por usuário e e-mail, registro e campos de validação retornados pelo AgroHub.
2. Alterações de perfil e foto visíveis também no AgroHub; confirmar a origem da mídia e o suporte a WebP no PUT multipart.
3. Recebimento do e-mail e seu destino configurado; confirmar pelo link ou copiando UID/token, conferir token inválido/expirado e login com a nova senha.
4. Administrador local vinculado ao ID AgroHub correto, grupos e restrições de acesso; verificar sessão expirada/desativação em páginas e APIs.
5. HTTPS, migração e conectividade de saída no ambiente de implantação.

[Especificação](../superpowers/specs/2026-10-06-agrohub-accounts-design.md) · [Plano](../superpowers/plans/2026-10-06-agrohub-accounts.md).
