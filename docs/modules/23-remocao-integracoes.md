# Remoção do módulo de integradores

Em 07/10/2026, o responsável solicitou retirar o módulo de Integrações e os arquivos associados. Esta decisão substitui as diretrizes anteriores que preservavam o recebimento externo.

Foram removidos o app `integracoes`, modelos, serviços, autenticação Bearer própria, formulários, templates, endpoints, testes específicos e documentação exclusiva. O menu, o middleware de acesso interno, o detalhe da agenda e o script de verificação visual deixam de referenciar o módulo. As rotas `/integracoes/` e `/api/v1/integracoes/`, incluindo seus descendentes, não estão registradas e retornam 404.

Agendamentos de serviço, equipamento e visita, autores, versões, avaliações e eventos históricos continuam no sistema. O nome de um ator externo já registrado no histórico permanece como dado de auditoria. Accounts, sincronização de papéis/sessões, eventos e contato do AgroHub não foram removidos.

## Atualização de bancos existentes

```powershell
& .\venv\Scripts\python.exe manage.py migrate
```

A migração `agenda.0017_remove_integracoes` apaga as tabelas de pedidos e clientes do módulo, seus tipos de conteúdo, permissões e associações de permissões, além dos registros antigos de execução de suas migrações. Contas, grupos e permissões de outros módulos permanecem. Credenciais e recibos desse módulo deixam de existir; voltar as migrações da agenda não os recupera.

As migrações `0014` e `0015` da agenda deixam de depender do app excluído. Uma rotina privada de compatibilidade elimina as FKs das tabelas retiradas antes de copiar/remover a agenda legada. Isso permite migrar bancos que ainda não passaram pela separação das agendas. Bancos novos não criam tabelas, tipos de conteúdo ou permissões de integradores. Arquivos históricos privados da agenda continuam disponíveis; uma restauração preserva agendamentos e eventos, sem reinstalar recibos do módulo retirado.

Os documentos de entregas anteriores permanecem como histórico, identificados quando descrevem decisões substituídas. O guia e o plano exclusivos do módulo removido foram excluídos.

## Verificação

```powershell
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\venv\Scripts\python.exe -m pip check
git diff --check
```

A suíte completa passou com **541 testes**, em **60,115 segundos**, no SQLite local. Os checks não encontraram problemas, divergências de migrações ou dependências quebradas. Os testes novos verificam ausência do app, rotas e menu; limpeza de um banco existente com tabelas e permissões de integradores; instalação nova; atualização anterior à separação das agendas; preservação das três agendas, histórico, usuários, grupos e permissões restantes. Os testes anteriores da agenda continuam verificando exportação, recuperação do legado e falha transacional do arquivo de exportação.

A migração foi aplicada no SQLite local, que ainda estava em `agenda.0010`; o legado sem destino operacional foi exportado pelo mecanismo privado existente da agenda. A revisão independente não encontrou problemas funcionais ou de integridade.

Chrome conferiu **16 combinações** de Dashboard, Agenda, Materiais e Perfil, em 1201 e 360 px, com menu aberto/fechado: navegação disponível sem Integrações, rotas retiradas com 404, ausência de transbordamento horizontal ou imagens quebradas e preferência da sidebar mantida após atualização. A tela de login continuou disponível; não houve erros JavaScript. Essa conferência usou uma cópia isolada do SQLite e uma sessão administrativa de teste, com eventos simulados, sem alterar contas do banco local ou chamar o AgroHub real.

Na depuração, validar os dados reais, login pelo Accounts e atualização no PostgreSQL do ambiente de implantação. Nenhuma instalação externa ou repositório do AgroHub foi alterado nesta entrega.
