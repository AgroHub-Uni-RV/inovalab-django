# Visitas no Laboratório InovaLab pelo AgroHub

Entrega de 06/10/2026: criar uma visita no formulário ou na API interna registra uma reserva na **sala ID 1** do AgroHub, já na criação, conforme confirmação do responsável. Contrato consultado: [Agendamentos](https://agrohub.unirv.edu.br/api/v1/schema/redoc/#tag/Agendamentos).

## Fluxo entregue

O formulário de visita exige dia, hora de início, hora de término e **quantidade de pessoas**, inteira e no mínimo 1. O servidor resolve a sala ID 1 em `GET agendamentos/salas/?site_code=inovalab` e exige sala ativa nesse site e capacidade para a quantidade informada, quando houver limite de capacidade. A consulta real confirmou `Laboratório InovaLab`, slug `laboratorio-inovalab`, ativa e com aprovação. O POST `agendamentos/reservas/` usa esse slug, data/horas de Brasília em **HH:MM**, título automático, quantidade escolhida e nome do criador nas observações externas, junto à referência UUID técnica. Não envia status na criação: a API o define pela configuração da sala. O usuário não escolhe a sala nem edita o título ou as observações automáticas.

O Bearer é da sessão AgroHub do criador. Nenhum token/senha é armazenado no vínculo da visita; a renovação verifica o mesmo ID de usuário. Permissões locais continuam locais e não dispensam as permissões do AgroHub.

Solicitações comuns continuam pendentes no InovaLab. A situação remota aparece separadamente no detalhe, junto ao ID da reserva. A confirmação automática pelo provedor não aprova a visita local. Aprovação administrativa envia atualização ao mesmo ID; rejeição/cancelamento envia `POST reservas/{id}/cancelar/`; edição usa `PATCH reservas/{id}/`. Conversão de visita para recurso cancela o vínculo anterior; conversão de recurso próprio para visita cria o vínculo. Equipamentos, serviços, visitas históricas sem vínculo e pedidos recebidos pelo adaptador de integrações não são exportados automaticamente.

## Resultado, falhas e conciliação

Antes de gravar uma visita vinculada, o sistema valida o período e consulta `GET agendamentos/disponibilidade/?sala=laboratorio-inovalab&data=AAAA-MM-DD`. Reservas remotas **pendentes e confirmadas** bloqueiam sobreposição; horários adjacentes são permitidos, e a própria reserva é excluída ao editar. Falha na consulta ou resposta inválida impede a gravação local. Visitas históricas sem vínculo conservam seu tratamento anterior.

Visita, auditoria e intenção são confirmadas na mesma transação local. O envio ocorre depois, com nova conferência de disponibilidade; os dois sistemas não compartilham uma transação. A API valida novamente no POST/PATCH e continua sendo a autoridade final. A visita permanece salva se o provedor rejeitar nessa etapa, com motivo explícito. Aprovação local após rejeição conhecida pode ser mantida pelo administrador; não cria reserva em nome dele. A criação rejeitada exige nova tentativa explícita do criador. Manutenção exige administrador do laboratório.

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

## Correção das mensagens após a depuração

Em 06/10/2026, a imagem enviada pelo responsável mostrou uma visita salva no InovaLab com envio externo rejeitado. A faixa de aviso aparecia verde porque o template compartilhado descartava `message.tags` e aplicava a cor de sucesso a todas as mensagens. O bloco externo também chamava uma falha conhecida de operação aguardando confirmação.

A faixa agora informa somente **Agendamento salvo no InovaLab.**, com cor de aviso quando o envio não foi concluído. A situação local tem o rótulo **Situação no InovaLab**; o resultado externo fica no bloco AgroHub. Falhas conhecidas não mostram o texto genérico de confirmação pendente. O template conserva a categoria da mensagem e distingue avisos em amarelo e erros em vermelho. Essa correção esclarece o resultado; não transforma uma falha de envio em reserva externa.

Validação: regressão reproduzida antes da correção; `venv/Scripts/python.exe manage.py test --noinput` passou com **509 testes** (41,967 s). `check`, drift e diff sem problemas. Chrome com falha HTTP controlada verificou aviso amarelo (`rgb(255, 243, 216)`), rótulo local, ausência de confirmação externa indevida e ausência de transbordamento em desktop/celular. A causa do envio real rejeitado não foi armazenada nos registros anteriores; permanece necessária sua conferência no provedor.

## Correção do contrato após leitura do monólito

A inspeção somente leitura de `unirv-monolith/apps/agendamentos/api/serializers.py` identificou `TimeField(input_formats=["%H:%M"])`. O cliente enviava `HH:MM:SS`, e o stub anterior aceitava esse formato indevidamente. Além disso, o cliente descartava erros de campos de Agendamentos e esperava confirmação imediata de visitas administrativas, embora a sala tenha `requer_aprovacao=True` e a API derive o status inicial desse campo.

O cliente agora envia minutos e conserva erros de validação dos campos conhecidos, limitados e escapados na interface. Segundos e frações diferentes de zero são rejeitados sem arredondamento. O formulário usa passos de um minuto; serviços/equipamentos mantêm sua precisão anterior. Criação aceita status remoto pendente ou confirmado, independentemente da aprovação local.

Novas reservas externas exigem início futuro e antecedência configurada em `AGROHUB_MIN_ADVANCE_NOTICE_HOURS`, padrão **2**. A configuração remota não é publicada pela API: alinhar esse valor ao `MIN_ADVANCE_NOTICE_HOURS` do provedor se ele mudar. A regra de antecedência é aplicada à criação, inclusive a novas tentativas ainda sem ID externo; edições de reservas já registradas seguem a validação final da API.

Uma nova tentativa de falha conhecida reconstrói o payload em HH:MM a partir da visita, mantendo UUID e ID existentes. Registros com segundos ou período passado precisam ser corrigidos pelo responsável; não são modificados automaticamente. Operações incertas mantêm o payload original para conciliação somente leitura. Mutações aceitas seguidas de erro na consulta de confirmação também ficam incertas, inclusive se essa consulta retornar 401/403/404, impedindo repetição de PATCH/cancelamento.

A integração permanece por HTTP. Não foram importados `prepare_reservation()`/`save_reservation()` nem alterados banco compartilhado, monólito ou regras de administradores nesta etapa.

## Quantidade de pessoas e identificação do criador

A solicitação seguinte acrescentou `Agendamento.quantidade_pessoas`, exclusiva de visitas. O formulário exige preenchimento, iniciando em 1; criação pela API interna aceita omissão com padrão 1 para manter os consumidores anteriores. Atualizações sem o campo preservam o valor atual; recursos rejeitam o campo, e a conversão de visita em recurso limpa a quantidade com auditoria. Quantidade é exibida no detalhe e enviada em criação/edição ao AgroHub. A capacidade da sala é conferida antes de salvar e antes do envio, e a API conserva a validação final.

As observações remotas usam o formato:

```text
Registrado por: Nome Sobrenome
inovalab-visita:UUID
```

O nome vem da conta que criou a visita, inclusive quando outro administrador a edita. Sem nome completo, é usado o login. Não existe campo de observações livre no formulário de visita. A referência continua sendo uma linha exata e única, compatível com as reservas antigas que continham somente o UUID. A confirmação após envio verifica observações e quantidade contra o payload persistido; divergências ficam incertas e não disparam outra criação. A conciliação de envio incerto conserva o nome originalmente enviado mesmo se o perfil mudar.

A migração `0010_quantidade_pessoas_visitas` atribui 1 às visitas existentes, que era o valor enviado anteriormente, e mantém recursos com `null`. Não altera referências ou payloads de operações em andamento/incertas e não reenvia reservas históricas. Aplicada somente ao SQLite local nesta entrega; executar `venv/Scripts/python.exe manage.py migrate --noinput` ao implantar. Contrato de recebimento por integradores externos permanece na versão anterior, com padrão compatível de 1 para visitas.

Validação desta ampliação:

- `venv/Scripts/python.exe manage.py test --noinput`: **536 testes passaram** (66,424 s). O recorte de visitas, integração e migração passou com **68 testes** (19,034 s), incluindo quantidade inválida, capacidade, autoria em edição administrativa, fallback de login, migração, divergência de observações/quantidade remotas e conciliação sem novo POST.
- `manage.py check`, `makemigrations --check --dry-run` e `git diff --check`: sem problemas. Migração 0010 aplicada ao SQLite local.
- Chrome com API simulada: formulário iniciou em 1, bloqueou 11 pessoas para sala de capacidade 10, registrou 8 e editou para 6 mantendo reserva #101. Detalhe mostrou a quantidade; troca de categoria incluiu/removeu o campo. Desktop 1200 px com sidebar expandida e celular 360 px sem transbordamento; sem exceções JavaScript.
- Revisão independente aprovada. Resta a depuração com conta e sala reais; o monólito permaneceu somente leitura e nenhuma reserva fictícia foi enviada à API real.

Validação desta correção:

- `venv/Scripts/python.exe manage.py test --noinput`: **523 testes passaram** (67,056 s).
- Após o ajuste final de formulário, `venv/Scripts/python.exe manage.py test agenda.tests.test_agrohub agenda.tests.test_web --noinput`: **55 testes passaram** (13,866 s).
- `manage.py check`, `makemigrations --check --dry-run`, `node --check core/static/core/auto-apply.js` e `git diff --check`: sem problemas; nenhuma migração nova.
- Chrome com banco/provedor isolados: criação registrada com status pendente, conflito antes de gravar, recusa com motivo e aviso amarelo, nova tentativa conhecida, troca Serviço→Visita→Serviço preservando horários e rejeitando segundos sem truncamento. Desktop 1200 px com menu expandido e celular 360 px sem transbordamento; sem exceções JavaScript. A troca de categoria também atualiza o passo e a ajuda dos horários sem substituir os campos enquanto o usuário digita.
- Revisão independente verificou contrato, preflight, concorrência e conciliação; os problemas apontados foram corrigidos. A gravação na API real continua pendente de depuração com uma conta autorizada; nenhuma reserva fictícia foi enviada à sala real.
