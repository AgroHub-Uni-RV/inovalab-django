# Remoção do cadastro de espaços — 07/10/2026

A solicitação posterior do responsável remove o modelo `catalogo.Espaco`. O catálogo atual mantém somente Serviços e Equipamentos. Foram removidos formulário, serializer, viewset, rotas web/API, aba de navegação, carga inicial atual e widgets/CSS antigos de seleção de espaços. As rotas `/catalogo/espacos/` e `/api/v1/espacos/`, incluindo seus detalhes e formulários, não existem mais.

A agenda continua com Serviços, Equipamentos e Visitas. A sala de visitas obtida no AgroHub permanece no provedor externo; ela não depende do modelo local removido. O serviço existente chamado **Uso do espaço** permanece no catálogo de serviços.

## Dados históricos e atualização

`agenda.0011_desvincula_espacos_legados` copia o identificador e o nome de cada espaço referenciado para `Agendamento.espaco_legado_id` e `espaco_legado_nome`, somente para histórico, e remove a FK. Depois, `catalogo.0007_remove_espaco` exclui a tabela de espaços. Migrações antigas permanecem intactas para instalações novas e atualização de ambientes existentes.

Reservas ativas e canceladas mantêm os mesmos IDs, períodos, situação, versão, autoria, textos e eventos. Pedidos externos mantêm recibos/digests e reenvio idempotente. A representação de reservas antigas continua com categoria `espaco`, objeto e nome original; consulta, busca por nome e cancelamento permanecem disponíveis. Edição e novas reservas de espaço continuam rejeitadas. Os campos de histórico não são aceitos nos payloads de gravação.

Execute em outros ambientes:

```powershell
.\venv\Scripts\python.exe manage.py migrate
```

A migração já foi aplicada ao SQLite local e verificou a preservação da única reserva antiga, sem alterar as contagens de reservas, eventos e pedidos externos. Antes dela, foi criado um backup em `C:\Users\henri\AppData\Local\Temp\inovalab-antes-remocao-espacos-2026-10-07.sqlite3`.

Ao atualizar um ambiente em execução, reinicie os processos Django após as migrações. Um servidor iniciado com `--noreload` continua usando os modelos/consultas anteriores em memória, mesmo quando os arquivos já foram atualizados. Isso causou `no such table: catalogo_espaco` em `/index/` no servidor local antigo. Para desenvolvimento, use `python manage.py runserver` com recarga automática; alterações de esquema ainda exigem aplicar as migrações e reiniciar o servidor quando necessário.

A exclusão da tabela descarta os cadastros de espaços e seus atributos de capacidade/status/restrição/código inicial. A reversão das migrações recupera somente espaços referenciados, com ID/nome e demais atributos padrão; recuperar o catálogo completo exige restaurar o backup.

## Verificação e depuração

Comandos executados:

```powershell
.\venv\Scripts\python.exe manage.py test --noinput
.\venv\Scripts\python.exe manage.py test agenda.tests.test_api agenda.tests.test_services agenda.tests.test_visits --noinput
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe manage.py check
git diff --check
```

Os testes incluem remoção do modelo/tabela/rotas, renderização do catálogo com duas abas, atualização preservada de equipamentos, migração com reservas ativas e canceladas, visitas, auditoria, recibos e reversão. A agenda verifica a leitura/busca/cancelamento do legado, rejeição de novos espaços e reenvios externos.

Resultados: suíte completa com **578 testes aprovados** em 64,681 s; após ampliar as verificações de leitura/busca e proteção dos campos históricos, **41 testes da agenda aprovados**. `makemigrations --check --dry-run` não encontrou alterações pendentes, `manage.py check` não apontou problemas e `git diff --check` não encontrou erros de whitespace.

Na correção do erro de `/index/`, o processo antigo com `--noreload` foi encerrado e o servidor com recarga automática já iniciado pelo responsável assumiu a porta 8000. Requisições HTTP autenticadas reais a `/index/`, `/index/?agenda=proximos`, `/painel/` e às duas listas do catálogo retornaram 200; `/api/v1/espacos/` retornou 404. A sessão temporária de verificação foi removida. Foi acrescentado um teste de `/index/` e `/painel/` com reserva histórica, incluindo a contagem do calendário, e removida a rota extinta do script de verificação visual. A nova execução de `manage.py test --noinput` aprovou **579 testes** em 64,178 s; verificações Django/migrações/diff continuam sem problemas. O conector de navegador permaneceu indisponível.

Verificação visual pendente: esta sessão não disponibilizou Chrome nem navegador integrado; ambas as tentativas de conexão retornaram navegador indisponível. Conferir o catálogo de Serviços/Equipamentos e seus formulários, sidebar expandida/recolhida, mobile, busca/detalhe de reservas antigas e cancelamento em dados de teste. Validar também a atualização e os dados de produção no PostgreSQL; o banco alterado nesta entrega foi somente o SQLite local.
