# Correção das categorias de agendamento

Solicitação de 06/10/2026: novos agendamentos são de Equipamentos, Serviços ou Visitas. Espaços continuam no catálogo e não são alvos de novas reservas. Esta decisão substitui os requisitos anteriores de reservas de espaços.

- Equipamentos e serviços mantêm os campos atuais, incluindo motivo obrigatório e observações opcionais.
- Visita contém somente dia, hora de início e hora de término como dados específicos. Não possui objeto de catálogo, motivo, observações, equipamentos associados ou material. Usuário criador, situação, versão e histórico continuam automáticos.
- Visitas usam um único dia no fuso do laboratório e término posterior ao início. A API conserva início/fim ISO 8601 com fuso.
- Permissões e avaliação administrativa permanecem: usuário interno solicita; administrador confirma, edita e cancela.
- Proposta operacional provisória, pendente de resposta: uma visita confirmada por intervalo; visitas não bloqueiam equipamentos/serviços. Intervalos adjacentes são permitidos.
- Política conservadora para legado: preservar reservas de espaços e sua auditoria, identificar como legado e permitir consulta/cancelamento. Não converter em visitas nem aceitar edição/aprovação que renove a reserva.
- Interface, API interna e integração externa rejeitam novas reservas de espaços. Reenvios idempotentes de pedidos externos já recebidos continuam retornando o registro original.
- Preservar login, identidade, catálogo e alterações locais em `.env.example`; não publicar nem alterar banco de produção nesta entrega.
