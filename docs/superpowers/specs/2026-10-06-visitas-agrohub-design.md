# Visitas na sala 1 do AgroHub

Solicitação: cada nova visita criada no InovaLab deve registrar uma reserva na sala ID 1, Laboratório InovaLab, pela API Agendamentos. Consulta de 06/10/2026 confirmou ID 1, slug `laboratorio-inovalab`, site `inovalab`, sala ativa e com aprovação. Fonte: https://agrohub.unirv.edu.br/api/v1/schema/redoc/#tag/Agendamentos.

## Fluxo e contrato

Envio na criação, confirmado expressamente pelo responsável. Apenas criação interna por conta vinculada ao AgroHub; equipamentos/serviços e recebimento de integração externa não são reenviados. O formulário de visita continua somente dia, início e término.

POST `agendamentos/reservas/` usa JWT da sessão do criador, sala resolvida pelo ID 1, `data`, `hora_inicio`, `hora_fim`, título automático `Visita ao Laboratório InovaLab`, quantidade automática 1 e uma referência UUID em `observacoes`. Sala/status/solicitante não são campos editáveis da visita. GET de salas resolve o slug da sala 1; o nome e o número de pessoas não são perguntados ao usuário nesta etapa.

Um vínculo privado por agendamento armazena intenção, origem da API, referência UUID, ID/status remoto, estado de envio e mensagem operacional. Não armazenar senha/JWT nem expor payload/referência na API local. Aprovação local continua controlada pelos administradores do laboratório; não conceder privilégios pelo retorno remoto.

Persistir a visita e sua intenção na mesma transação local; enviar fora dessa transação. Resultado externo é registrado separadamente: não existe transação distribuída. Uma falha preserva a solicitação e informa que a reserva externa ainda não foi registrada. Um POST de criação com resultado incerto nunca é repetido automaticamente. Uma ação autenticada permite reconciliar pela referência, consultando reservas da sala/dia na origem fixa; repetir criação somente após rejeição HTTP conhecida, sem reserva conhecida.

O schema de POST projeta ReservaWrite e não promete ID na resposta. Quando faltar ID, consultar a lista para encontrar a referência e verificar sala/período/status. Não vincular uma reserva por simples coincidência de horário. IDs remotos pertencem à origem registrada, não a uma configuração futura da API.

Editar uma visita vinculada usa PATCH do ID existente; cancelamento/rejeição local usa POST cancelar. Não criar nova reserva nessas operações. Quando houver envio em andamento ou resultado incerto, bloquear mudanças até conciliar, preservando a intenção original. Criar uma visita a partir de outra categoria de conta alheia não pode atribuir a reserva ao administrador por engano. Retries de criação exigem o criador; atualização/cancelamento exigem administrador local e são submetidos também às permissões do AgroHub. Após rejeição conhecida da criação, aprovação/edição local atualiza a intenção sem repetir POST: o criador pode tentar novamente explicitamente.

Claims usam timestamp e gravações condicionais antes do POST e na finalização. A manutenção usa uma transação separada com lock de escrita do vínculo durante GET/mutação/GET, evitando que um processo antigo modifique o remoto após outro concluir. Em SQLite, esse lock bloqueia outras escritas durante o HTTP. Timeout após mutação resulta em estado incerto; conciliação faz somente GET. Se o resultado desejado não for encontrado, manter bloqueado para conferência técnica no provedor. A confirmação remota automática na criação não altera a aprovação local.

## Limites

Não exportar visitas históricas automaticamente. Vínculos antigos só seriam reconciliados mediante entrega própria. Falhas de sincronização aparecem no detalhe, inclusive cancelamentos locais cujo envio externo falhou; acesso para revisão do envio cancelado precisa conservar as permissões do agendamento. Sem fila/processo de fundo ou credenciais técnicas nesta entrega. Sem garantia de exatamente uma criação se o provedor não tiver idempotência: uma criação incerta permanece em conciliação até ser encontrada/conferida, em vez de reenviar às cegas.

Testar com HTTP controlado, nunca com reservas fictícias no laboratório real. Conferência real de permissões, sobreposição e campos write-only depende de conta autorizada. Preservar `.env.example` editado pelo responsável; sem deploy/migração de produção.
