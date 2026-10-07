# Agendamentos para usuários comuns

Entrega de 07/10/2026: contas autenticadas e ativas podem criar serviços, equipamentos e visitas e cancelar seus próprios agendamentos. Esta solicitação substitui a restrição anterior de criação apenas pela equipe e cancelamento apenas por administradores.

## Comportamento

- Meus agendamentos oferece Novo agendamento para qualquer conta ativa. A criação mantém o modal único e os formulários como alternativa sem JavaScript.
- Solicitações de usuários comuns são pendentes; confirmação, recusa e edição continuam administrativas. As regras locais de disponibilidade e validação permanecem nas três agendas.
- Detalhes pessoais oferecem Cancelar agendamento enquanto o registro não estiver cancelado. A confirmação usa POST com CSRF e versão; GET apenas apresenta o formulário. O cancelamento libera o horário e preserva registro e histórico.
- A autoria é verificada na consulta pessoal e novamente pelo serviço antes da gravação, inclusive após adquirir o bloqueio de concorrência. Usuários comuns não podem agir sobre registros de terceiros, nem usando IDs iguais em categorias diferentes.
- A API de sessão aceita criação e cancelamento pessoal; edição continua administrativa. Contas externas continuam sem acesso à listagem interna da API e usam Meus agendamentos para consulta.
- Accounts continua sincronizando a sessão e os papéis. Login retorna aos acessos de criação autorizados; contas externas recebem links para detalhes pessoais e estrutura institucional. O modal usa o estilo compartilhado também para essas contas e atualiza a lista pessoal após salvar.
- Apenas a leitura autenticada das fotos dos equipamentos é liberada para apresentar os formulários. Cadastro, catálogo interno, tarefas, materiais, integrações e demais funções mantêm suas permissões.

## Banner inicial

A proporção fixa do banner reduzia sua altura abaixo do conteúdo em telas intermediárias, cortando Agendar visita. A altura agora acompanha o conteúdo, com altura mínima proporcional à largura; título pode quebrar linha e a margem móvel é simétrica. Os dois botões ficam dentro do banner.

## Verificação

- `python manage.py test --noinput`: 567 testes aprovados.
- `python manage.py check`: sem problemas de configuração.
- `python manage.py makemigrations --check --dry-run`: sem alterações de modelos.
- Navegador Chromium com banco SQLite isolado: usuário comum cria e cancela as três categorias; registros aparecem na lista sem recarregar manualmente; terceiros recebem 404 ao tentar cancelar; modal móvel e Agendar visita institucional funcionam.
- Fluxo administrativo no Chromium: escolha das três categorias, validação, persistência, atualização da lista, Escape e modal móvel aprovados.
- Banner verificado em 320, 360, 412, 768, 1024, 1366 e 1920 pixels, sem corte dos botões nem transbordamento horizontal.

Os testes cobrem sessão vinculada ao Accounts, autoria, aprovação administrativa, cancelamento de confirmados, histórico, versão desatualizada, CSRF, campos forjados, contas inativas e manutenção das restrições dos demais módulos. A validação com contas e provedor reais permanece para a depuração do responsável.
