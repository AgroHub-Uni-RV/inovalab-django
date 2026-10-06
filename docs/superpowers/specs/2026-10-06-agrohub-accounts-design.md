# Identidade pelo AgroHub

Solicitação de 06/10/2026: login, registro, atualização de perfil/foto e solicitação/confirmação de recuperação de senha usam Accounts da API UniRV. Resposta posterior: somente login pelo AgroHub; sem entrada alternativa por senha local.

Fonte: https://agrohub.unirv.edu.br/api/v1/schema/redoc/ e Swagger UI. OpenAPI 1.0.0 consultado em `/api/v1/schema/?format=json`; o schema de resposta de login/cadastro omite os tokens descritos no texto, portanto o cliente valida access/refresh e consulta `/accounts/me/` como identidade autoritativa.

## Contrato

Base padrão: `https://agrohub.unirv.edu.br/api/v1/`.

| Operação | Método/rota Accounts | Dados |
| --- | --- | --- |
| Login | POST login/ | username (usuário ou e-mail), password |
| Renovação | POST login/refresh/ | refresh |
| Consultar perfil | GET me/ | Bearer access |
| Registro | POST register/ | username, email, password, password_confirm; first_name, last_name, cpf, telefone opcionais |
| Perfil | PATCH me/ | first_name, last_name, cpf, telefone |
| Foto | PUT me/picture/ | multipart `profile_picture` |
| Solicitar recuperação | POST password-reset/ | email |
| Confirmar recuperação | POST password-reset/confirm/ | uid, token, new_password, new_password_confirm |

`username` e `email` do perfil são somente leitura. Campos administrativos não entram em formulários ou requisições. Campos aninhados opcionais de ProfileData não fazem parte desta primeira interface.

## Sessão e identidade

- Backend Django autentica exclusivamente na API, inclusive administração. Backend local anterior deixa de ser aceito, encerrando sessões antigas ao atualizar.
- Usuário local vinculado por `agrohub_id` único; nunca associar contas existentes por nome/e-mail. Colisão cria identificador local alternativo, sem copiar privilégios.
- Novos usuários possuem senha local inutilizável, sem staff/superusuário/grupos. Privilégios existentes de uma conta já vinculada permanecem locais; `roles` remotos não concedem acesso administrativo.
- JWT fica na sessão de banco no servidor; navegador recebe somente cookie de sessão, protegido por CSRF/HttpOnly. Não expor tokens em HTML, URLs, logs ou localStorage.
- Cada requisição autenticada de conta vinculada revalida `me/`. Um 401 permite uma renovação e nova tentativa; falha de credencial encerra a sessão. Indisponibilidade retorna erro útil sem autenticação local alternativa.
- Logout elimina tokens da sessão. A API não documenta endpoint de revogação/logout.
- Perfis/fotos são atualizados pela API. Cache local dos campos básicos preserva autoria e exibição. URL de foto é validada contra origem configurada; proxy autorizado aceita imagens limitadas e nunca encaminha JWT a URL arbitrária.

## Interface e recuperação

Preservar layout de login e perfil, Montserrat e estilos comuns. Login apresenta Criar conta, Esqueci minha senha e confirmação de recuperação. Registro válido usa tokens para login imediato. Perfil mostra usuário/e-mail como somente leitura, dados editáveis e formulário separado de foto, mantendo Salvar perfil e Sair.

Recuperação pode receber uid/token por link ou preenchimento manual. O token em URL é removido por redirecionamento e guardado na sessão por até 30 minutos. Respostas não permitem cache; a captura do link usa Referrer-Policy no-referrer, e o formulário na URL limpa usa same-origin para preservar o Origin do POST/CSRF inclusive no desenvolvimento HTTP. A API não aceita callback/redirect documentado: o link do e-mail depende da configuração do AgroHub; usuário também pode copiar UID/token para a tela local.

## Limites da entrega

Somente identidade nesta etapa. Não publicar nem alterar contas de produção para testar. Contrato/HTTP são exercitados com servidor de homologação local que reproduz Accounts; testes reais com conta autorizada, entrega de e-mail e URL final da foto permanecem para depuração do responsável. `.env.example` contém alteração prévia e deve ser preservada.
