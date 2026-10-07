# Diretrizes para a futura migração ao monólito UniRV

Orientação registrada pelo responsável em 07/10/2026. Trata-se de uma decisão para a futura integração deste sistema ao repositório `unirv-monolith`, sem mudança no comportamento do InovaLab separado.

## Identidade compartilhada

Ao executar dentro do monólito, os módulos devem reutilizar o usuário principal de `apps.accounts.CustomUser`, configurado em `AUTH_USER_MODEL`. As referências de autores, responsáveis, solicitantes e avaliadores devem apontar para esse modelo compartilhado por meio de `settings.AUTH_USER_MODEL` ou `get_user_model()`.

Não criar outro modelo ou tabela de usuário para o InovaLab, nem uma cópia representativa da conta central. O vínculo `agrohub_id` existente no sistema separado pode orientar a associação das identidades durante a transferência de dados. Preservar autoria, responsáveis e históricos ao associar os registros às contas centrais.

## Autenticação e autorização

Reutilizar a autenticação e a sessão compartilhadas do Django no monólito. Para acesso interno e administrativo, seguir as flags e permissões nativas utilizadas pelo projeto de destino, incluindo `is_staff` e `is_superuser`, sem depender do preenchimento manual de `roles`.

`is_staff` é a flag utilizada nas verificações de acesso da equipe no painel LabMaker; `is_superuser` identifica o superusuário do Django. `is_admin` não é uma flag nativa. Os detalhes de quais operações cada condição permite devem seguir as regras do monólito e ser tratados na implementação da migração.

O responsável relata que o campo `roles` retornou vazio e precisou ser preenchido manualmente no Django Admin do monólito para liberar os acessos atuais. Esse relato motiva a orientação futura; não autoriza trocar a fonte de autorização do sistema separado nesta entrega.

## Escopo desta anotação

Esta entrega modifica somente documentação. A autenticação pela API do AgroHub, a sincronização de papéis, o modelo `accounts.User` e as permissões atuais permanecem em vigor enquanto o sistema estiver separado. A transferência de dados e a alteração dos fluxos serão uma etapa futura, solicitada pelo responsável.

Referências examinadas no monólito: `config/settings/auth.py`, `apps/accounts/models.py`, `apps/common/access.py` e `apps/labmaker/api/permissions.py`.
