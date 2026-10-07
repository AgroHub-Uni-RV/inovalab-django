# Agendas locais de serviços e equipamentos

## Objetivo e decisão aprovada

A solicitação mais recente substitui a importação de visitas confirmadas: visitas ficam exclusivamente no AgroHub, tanto na consulta quanto nas ações. O banco deste sistema mantém duas agendas concretas, `AgendaServico` e `AgendaEquipamento`, sem tabela de agendamento comum. O responsável autorizou planejar, confirmar o plano diretamente e executá-lo nesta sessão.

Foram consideradas três estruturas: manter o modelo único com campos opcionais; usar herança concreta com uma terceira tabela de agendamento; usar uma base abstrata e duas tabelas concretas. A terceira opção atende à separação solicitada sem campos de visita nem uma tabela pai persistida. A apresentação continua unificada.

## Restrições globais

- Alterar somente este repositório; não modificar o monólito AgroHub.
- Persistir agendamentos somente em `AgendaServico` e `AgendaEquipamento`; a base compartilhada deve ser abstrata.
- Consultar e executar ações de visitas exclusivamente pela API autenticada do AgroHub, sem espelho, fila ou reserva local.
- Preservar papéis Accounts, isolamento entre usuários, CSRF, validação de payload e controle de versão nas agendas locais.
- Preservar o layout atual, filtros, calendário e as abas Todas/Pendentes/Canceladas/Recusadas de solicitações.
- Preservar os dados, equipamentos associados, históricos e recibos dos agendamentos locais existentes.
- Antes de excluir visitas ou espaços históricos da estrutura antiga, preservar seus dados fora do banco operacional em arquivo privado, excluído do Git.
- Executar a suíte automatizada Django e verificações básicas das páginas; registrar qualquer impedimento à verificação visual.
- Fazer commits convencionais em português por alteração importante.

## Modelo local

`AgendaBase` é abstrata e contém motivo, observações, período, versão, cancelamento, criação, situação e avaliação. As FKs de usuário usam nomes de relação com substituição de classe para não colidir. Cada tabela tem constraints de período positivo, versão positiva e situação válida.

`AgendaServico` possui FK obrigatória para serviço, equipamentos associados e campos de material. `AgendaEquipamento` possui somente FK obrigatória para equipamento além dos campos comuns. Propriedades de apresentação expõem categoria, objeto, nome e criador sem atributos fictícios de serviço em equipamentos.

Os eventos e os recibos possuem duas FKs opcionais com constraint de exatamente um alvo. Não usar GenericForeignKey: manter integridade referencial no banco. Uma propriedade de leitura pode unificar o acesso ao agendamento. Os eventos conservam seus IDs, datas e alterações. Os recibos conservam suas chaves de idempotência, digest e timestamps.

URLs locais e identificadores de ações incluem `servico` ou `equipamento`, junto ao ID. Não resolver ambiguidades por preferência arbitrária de tabela. Rotas antigas de ID isolado podem funcionar como compatibilidade somente quando o resultado for inequívoco; ambiguidades retornam erro explícito/404. A API informa a categoria junto ao ID e usa identificação por tipo nas ações. A categoria de um registro existente é imutável; mudar de tipo exige um novo agendamento.

## Visitas e apresentação

Usar `RemoteReservation` e o cliente autenticado existente como dados transitórios de apresentação. Confirmadas aparecem em Agendamentos e no dashboard/calendário consultando a API. Pendentes, canceladas e recusadas permanecem em Solicitações. A confirmação altera apenas a reserva remota; uma consulta posterior apresenta a confirmada no calendário, sem inserir qualquer linha local.

Criação, edição e cancelamento de visitas seguem os endpoints de reservas do AgroHub. Validar sala pertencente a `site_code=inovalab`, identificador, período, quantidade de pessoas e resposta do provedor antes de apresentar sucesso. Não criar um histórico local de visitas. Preservar os mecanismos de autenticação, refresh e limites de paginação do cliente. A recusa usa PATCH e o cancelamento usa POST no endpoint cancelar. Não confirmar/recusar reservas em situação incompatível. O cancelamento de confirmadas deve respeitar as regras e recusas do provedor.

Falha da API deve exibir indisponibilidade de visitas enquanto os agendamentos locais continuam acessíveis. Não apresentar cópias antigas como atuais nem informar quantidade zero como uma consulta remota bem-sucedida. Usuários internos acessam as próprias reservas conforme o queryset e as permissões do provedor; administradores veem as reservas que sua sessão remota autoriza.

Seletores locais podem agregar listas das duas tabelas e ordenar por período, categoria e ID. Filtros e paginação operam sobre essa apresentação sem fingir um QuerySet de um modelo inexistente. Consultas de conflito continuam transacionais, com bloqueio dos cadastros e versão otimista. Não ampliar a política de sobreposição além das regras atuais.

## Migração e preservação

Criar as duas tabelas, copiar os agendamentos por tipo preservando PKs e timestamps, copiar M2M, religar eventos e recibos, validar contagens/vínculos e só então remover o modelo antigo e os modelos de espelhamento/lock de visitas. Separar migrations entre agenda e integrações para resolver a dependência das FKs.

Dados que não têm destino nas duas agendas (visitas e espaços legados, com seus eventos/recibos/vínculos remotos) devem ser exportados para um arquivo privado antes de retirar as tabelas antigas. A migração deve falhar, sem descartar dados, caso essa preservação não seja possível. Um mecanismo explícito de exportação/backup e a documentação devem permitir recuperar o estado anterior. Não enviar visitas antigas à API durante a migração.

Neste ambiente foram encontrados zero serviços, zero equipamentos, zero espaços antigos, uma visita recebida e registrada no AgroHub e zero recibos. Esses números não substituem os testes de migração com dados completos.

## Verificação e escopo

Testar migração com os dois tipos locais, M2M, material, datas, histórico, recibos e dados excluídos; testar IDs iguais nas duas tabelas, CRUD, versões, papéis, sobreposição e idempotência. Testar a consulta e as ações remotas com stub HTTP, confirmando ausência de escrita local, falhas do provedor e reservas fora do InovaLab. Atualizar testes das funcionalidades substituídas sem reduzir cobertura das regras preservadas. Verificar calendário, dashboard, detalhes, navegação e links de integração.

Esta entrega é exclusivamente a refatoração do módulo agenda e seus consumidores necessários. Login, identidade, catálogo, materiais e tarefas mantêm seus comportamentos. Não fazer push automático por uma autorização antiga de outra entrega.

## Revisão do desenho

Revisado contra a solicitação: duas tabelas locais concretas, base abstrata, visitas API em todas as ações e consultas, migração preservando dados e apresentação existente. Não há decisão pendente que impeça a execução. Trabalhar em branch local no checkout atual para manter a entrega disponível no IDE; não criar checkout adicional nem alterar `main` durante a implementação. Plano confirmado diretamente conforme autorizado pelo responsável.
