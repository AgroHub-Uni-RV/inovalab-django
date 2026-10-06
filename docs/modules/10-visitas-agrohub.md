# Visitas no Laboratório InovaLab pelo AgroHub

Entrega de 06/10/2026: criar uma visita no formulário ou na API interna registra uma reserva na **sala ID 1** do AgroHub, já na criação, conforme confirmação do responsável. Contrato consultado: [Agendamentos](https://agrohub.unirv.edu.br/api/v1/schema/redoc/#tag/Agendamentos).

## Fluxo entregue

O formulário conserva somente dia, hora de início e hora de término. O servidor resolve a sala ID 1 em `GET agendamentos/salas/?site_code=inovalab` e exige sala ativa nesse site. A consulta real confirmou `Laboratório InovaLab`, slug `laboratorio-inovalab`, ativa e com aprovação. O POST `agendamentos/reservas/` usa esse slug, data/horas de Brasília, título automático, quantidade 1 e referência UUID técnica nas observações externas. O usuário não escolhe a sala nem edita esses campos automáticos.

O Bearer é da sessão AgroHub do criador. Nenhum token/senha é armazenado no vínculo da visita; a renovação verifica o mesmo ID de usuário. Permissões locais continuam locais e não dispensam as permissões do AgroHub.

Solicitações comuns continuam pendentes no InovaLab. A situação remota aparece separadamente no detalhe, junto ao ID da reserva. A confirmação automática pelo provedor não aprova a visita local. Aprovação administrativa envia atualização ao mesmo ID; rejeição/cancelamento envia `POST reservas/{id}/cancelar/`; edição usa `PATCH reservas/{id}/`. Conversão de visita para recurso cancela o vínculo anterior; conversão de recurso próprio para visita cria o vínculo. Equipamentos, serviços, visitas históricas sem vínculo e pedidos recebidos pelo adaptador de integrações não são exportados automaticamente.

## Resultado, falhas e conciliação

Visita, auditoria e intenção são confirmadas na mesma transação local. O envio ocorre depois; os dois sistemas não compartilham uma transação. A visita permanece salva se o provedor rejeitar o envio, com aviso explícito. Aprovação local após rejeição conhecida pode ser mantida pelo administrador; não cria reserva em nome dele. A criação rejeitada exige nova tentativa explícita do criador. Manutenção exige administrador do laboratório.

`ReservaAgroHub` guarda origem, referência, ID/status remoto, intenção, último claim e resultado. A migração 0009 é aditiva. Se a resposta de criação omitir ID, o cliente consulta as reservas do próprio usuário e vincula somente uma referência correspondente à sala 1 e aos instantes enviados. Nunca associa apenas pela coincidência de horário. Alterar a origem configurada bloqueia o envio de vínculos anteriores para outra API.

HTTP/rede com resultado incerto não gera repetição de POST/PATCH/cancelamento. **Consultar resultado no AgroHub** faz somente GET para conciliar. Envios em andamento ou incertos bloqueiam outras mudanças nessa visita. A rejeição HTTP conhecida permite nova tentativa. Quando a conciliação não encontra o resultado desejado, a operação permanece incerta e precisa de conferência técnica no provedor antes de liberar um reenvio; não há criação garantida exatamente uma vez sem idempotência do provedor.

Claims e atualizações condicionais impedem um processo antigo de repetir criação após perder a posse. A manutenção usa uma transação separada com lock no vínculo durante GET/mutação/GET. No PostgreSQL, o lock é por linha; no SQLite, bloqueia outras escritas durante o HTTP e concorrentes podem receber 409. O timeout configurado é por operação de socket, sem garantia de duração total. Paginação é limitada a 20 páginas de 100 registros; URLs `next` nunca são seguidas para outra origem. Respostas têm limite de 512 KB.

## Consulta e nova tentativa

| Caminho | Comportamento |
| --- | --- |
| `/agenda/{id}/` | Situação local e resultado da operação externa |
| `GET /agenda/{id}/agrohub/` | Resultado, inclusive após cancelamento local; sem mutação |
| `POST /agenda/{id}/agrohub/` | Nova tentativa/conciliação, com CSRF e `versao` |
| `GET /api/v1/agendamentos/{id}/agrohub/` | Resultado externo da própria visita ou de administrador |
| `POST /api/v1/agendamentos/{id}/agrohub/` | Nova tentativa/conciliação com sessão, CSRF e `versao` |

A resposta de agendamento acrescenta `reserva_agrohub` (`null` sem vínculo), com somente `reserva_id`, `estado`, `status` e `mensagem`. Payload, referência e origem permanecem privados. Criação/edição 201/200 indicam gravação local: o consumidor deve verificar esse resultado externo. DELETE retorna 204 quando concluído, ou 202 com o resultado pendente do cancelamento externo.

## Validação e depuração

Comandos executados:

```powershell
venv/Scripts/python.exe manage.py test --noinput
venv/Scripts/python.exe manage.py check
venv/Scripts/python.exe manage.py makemigrations --check --dry-run
venv/Scripts/python.exe manage.py migrate --noinput
git diff --check
```

A suíte completa passou com **508 testes** (55,916 s); os **28 testes da integração** também passaram em execução isolada após o último ajuste de texto (7,427 s). `check` sem problemas, drift sem alterações e diff sem erros. A migração 0009 foi aplicada ao SQLite local.

Os testes HTTP controlados cobrem criação web/API, sala/horários/identidade, resposta sem ID, confirmação remota independente, falhas/retry, refresh, referência inválida, origem/versão, acesso/CSRF, legado/conversões, interrupção/posse, manutenção/cancelamento e PATCH incerto com conciliação somente leitura. O teste com conexões reais SQLite pausa um PATCH e impede tomada de posse concorrente. O teste antigo da migração 0008 foi ajustado para restaurar as migrações atuais após verificar o legado.

Chrome com banco e provedor isolados: login, visita, ID remoto #101, edição mantendo esse ID, cancelamento remoto, criação rejeitada com aviso e nova tentativa resultando em #102. Detalhe/tela de resultado em 1200 px com sidebar expandida e 360 px sem transbordamento horizontal; imagens carregadas e nenhuma exceção JavaScript. Datas/horas nativas preenchidas no DOM e submetidas pelo formulário real. Revisão independente corrigiu os bloqueadores de concorrência e aprovou a entrega.

Conferência real foi somente leitura do schema e da sala. Restam validação com conta autorizada no AgroHub (aprovação, conflito, edição/cancelamento e conciliação reais), concorrência PostgreSQL e conectividade na implantação. Não foram criadas reservas fictícias na sala real. Migração 0009 aplicada somente ao SQLite local; produção não foi migrada nem publicada nesta entrega.
