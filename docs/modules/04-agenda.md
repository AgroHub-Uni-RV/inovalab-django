# Módulo 4 — Agenda interna

Entrega local em 02/10/2026, autorizada para implementação direta com [plano simples](../superpowers/plans/2026-10-02-agenda.md). Somente agenda interna nesta etapa. Aguardar depuração e autorização antes da integração AgroHub.

## Uso e permissões

Entre com superusuário ativo ou conta ativa do grupo `Administradores` e abra `/agenda/`. O papel de negócio não exige `is_staff`. Usuários comuns, inclusive staff sem esse papel, recebem 403 em todas as telas e endpoints da agenda. Sem sessão, as telas redirecionam ao login e a API retorna 403.

A tela reúne calendário mensal, contagem de reservas por dia e lista de até 25 registros por página. Filtros: mês e categoria. Reservas que atravessam dias ou meses aparecem em todos os períodos ocupados; uma reserva terminando à meia-noite não conta no dia seguinte. As contagens incluem todo o filtro, independentemente da página da lista. Os formulários usam horário de Brasília (`America/Sao_Paulo`).

Selecione uma categoria e clique em **Atualizar opções**, escolha o objeto, preencha requerente, motivo, início e término e salve. A atualização das opções conserva textos/datas não salvos e a versão original de uma edição. Usa POST com CSRF para manter esses dados fora da URL. Não requer JavaScript. Depois de uma edição concorrente, recarregue o formulário antes de reaplicar alterações.

| Caminho web | Operação |
| --- | --- |
| `/agenda/` | Calendário mensal e lista filtrada |
| `/agenda/novo/` | Formulário de criação |
| `/agenda/{id}/` | Detalhe |
| `/agenda/{id}/editar/` | Edição com versão |
| `/agenda/{id}/cancelar/` | Confirmação; somente POST cancela |
| `/agenda/{id}/historico/` | Eventos paginados, com valores anteriores e novos |

O frontend de identidade foi preservado, com apenas um link para a agenda nas contas autorizadas. As novas telas são listas, formulários e ações simples.

## Regras entregues

- **Confirmado pelo responsável:** cada reserva tem exatamente um serviço, equipamento ou espaço. Em 02/10 foi confirmado que serviços também são exclusivos: uma reserva por objeto em cada horário, nas três categorias. Não há reserva automática de recursos associados.
- Campos públicos: `categoria`, `objeto`, `requerente`, `motivo`, `inicio`, `fim`. Categoria pertence a `servico`, `equipamento`, `espaco`; o ID de objeto é interpretado nessa categoria. IDs iguais em categorias diferentes não identificam o mesmo objeto. Troca exige categoria e objeto juntos.
- Requerente é nome obrigatório de até 150 caracteres, sem exigir conta local; motivo é obrigatório. Espaços no início/fim dos textos são removidos.
- Três FKs protegidas e restrição de exatamente uma preenchida; categoria derivada da FK. O banco também exige versão positiva e fim posterior ao início.
- Intervalos `[início, fim)`; sobreposição no mesmo objeto retorna conflito, horários adjacentes são permitidos. A edição exclui o próprio registro da busca de conflito. Falhas não deixam mudanças parciais.
- Cada criação, edição e cancelamento grava um evento na mesma transação, com ator, instante, ação e mudanças. Datas nas mudanças são normalizadas em UTC para evitar diferenças fictícias entre fusos equivalentes.
- Edição e cancelamento exigem versão inteira positiva. Versão desatualizada retorna 409. Cada gravação incrementa a versão, inclusive edição sem mudança material, que pode ter evento com alterações vazias.

**Escolhas de implementação para depuração, sem novas respostas a Q06/Q08/Q13/Q14:**

- Cancelamento lógico libera o intervalo e preserva o registro/eventos. Canceladas ficam fora da lista, detalhe e histórico operacionais; não há restauração nem consulta de canceladas nesta entrega. Os registros permanecem no banco, inclusive as referências protegidas ao catálogo.
- Não há etapa adicional de aprovação ou criação automática de tarefa.
- `indisponivel` impede reserva nova, troca de alvo ou mudança de período. Alteração apenas de requerente/motivo de uma reserva existente continua possível após desativar o alvo; cancelamento também. `ocupado` manual não bloqueia automaticamente reservas futuras. Reservar/cancelar não muda o status do catálogo.
- Permitir datas passadas e atravessar meia-noite, sem impor funcionamento, feriados, antecedência, duração mínima/máxima ou margem entre reservas ainda não definidos. Não há campo de participantes nem validação de capacidade do espaço.

## API entregue

JSON, autenticação por sessão Django e CSRF obrigatório nas escritas; nenhum acesso público ou credencial AgroHub foi acrescentado.

| Método e caminho | Resultado |
| --- | --- |
| `GET /api/v1/agendamentos/` | Todos os ativos, paginados 25; filtros opcionais `mes=AAAA-MM`, `categoria`; `page` seleciona página |
| `POST /api/v1/agendamentos/` | Cria com os seis campos públicos, 201 |
| `GET /api/v1/agendamentos/{id}/` | Detalhe, 200 |
| `PUT /api/v1/agendamentos/{id}/` | Substitui os seis campos públicos, com `versao`, 200 |
| `PATCH /api/v1/agendamentos/{id}/` | Altera campos informados, com `versao`, 200 |
| `DELETE /api/v1/agendamentos/{id}/` | Cancela com corpo `{"versao": 1}`, 204 |
| `GET /api/v1/agendamentos/{id}/historico/` | Eventos mais recentes primeiro, paginados 25 |

Criação, usando um ID real obtido no catálogo:

```json
{
  "categoria": "servico",
  "objeto": 1,
  "requerente": "Nome do requerente",
  "motivo": "Produzir protótipo",
  "inicio": "2026-11-01T14:00:00-03:00",
  "fim": "2026-11-01T15:00:00-03:00"
}
```

A resposta acrescenta `id`, `objeto_nome`, `versao`, `criado_por` e `criado_em`. Horários exigem ISO 8601 com fuso; UTC também é aceito. Campos internos/protegidos e desconhecidos são rejeitados. `objeto` e `versao` exigem inteiros JSON, rejeitando strings, booleanos e decimais. A criação não aceita `versao`: começa em 1.

Erros: 400 para payload/filtro inválido ou objeto indisponível; 403 para ausência de autorização/CSRF; 404 para ID inexistente/cancelado. Conflitos retornam 409 com `detail` e `code`:

| Código | Significado |
| --- | --- |
| `horario_ocupado` | Sobreposição para o mesmo objeto |
| `versao_desatualizada` | Edição/cancelamento baseado em versão antiga |
| `agenda_ocupada` | SQLite ocupado por outra transação; atualizar e tentar novamente |

Para PATCH somente de texto, envie por exemplo `{"versao": 1, "motivo": "Descrição corrigida"}`. A ausência dos dois campos de alvo preserva o existente. Enviar apenas categoria ou apenas objeto retorna 400.

## Concorrência e integridade

`save_booking`, `cancel_booking` e `visible_bookings` centralizam operações/escopo. O primeiro acesso ao banco dentro da transação é um UPDATE sem mudança do status do alvo; na troca, os alvos antigo e novo são bloqueados em ordem estável. Só depois são revalidados versão, disponibilidade e sobreposição. Reserva e evento são persistidos juntos; edições/cancelamentos também usam UPDATE condicionado à versão.

No SQLite, a escrita anterior às leituras adquire o bloqueio de escrita; `select_for_update` sozinho não protegeria esse fluxo. O SQLite serializa escritores, inclusive de objetos distintos, e busy/locked vira conflito recuperável. Referências: [transações SQLite](https://www.sqlite.org/lang_transaction.html), [SQLite no Django](https://docs.djangoproject.com/en/6.0/ref/databases/#sqlite-notes).

Esta estratégia foi verificada no SQLite local com duas conexões reais, threads e `TransactionTestCase`. O teste de ordem SQL falhou ao remover temporariamente a proteção, depois voltou a passar. Não foi executada validação de concorrência/carga em PostgreSQL ou ambiente de produção; banco e hospedagem de produção continuam pendentes. Escritas diretas via ORM fora dessas operações não representam uma API autorizada e podem ignorar a proteção de sobreposição.

## Verificação realizada

Em 02/10/2026, Python 3.14.3, Django 6.1.1 e DRF 3.18.1:

```powershell
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py test agenda.tests
& .\venv\Scripts\python.exe manage.py test
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\venv\Scripts\python.exe -m pip check
git diff --check
```

42 testes da agenda passaram: 17 de domínio, 3 de concorrência, 10 de API e 12 web. Suíte completa: **159 testes passaram**, sem falhas. Check, drift de migrações, dependências e diff sem pendências. Migração local aplicada de forma aditiva.

Chrome: cadastro das três categorias; atualização de opções preservando rascunho; conflito de período; adjacência; edição; história de valores; cancelamento e nova reserva no horário liberado; API com sessão/CSRF; conflito de versão após edição via API e refresh do formulário; usuário staff sem papel negado em telas/API; teclado e layout 360 px sem rolagem horizontal da página. Sem exceções JavaScript da aplicação. Datas nativas foram preenchidas por automação do DOM e submetidas pelo formulário real. Apenas fixtures temporárias identificadas por IDs/prefixo foram removidas; contas e cadastros anteriores foram preservados.

Revisão independente única: um Important corrigido — atualizar opções renovava indevidamente a versão; duas regressões demonstraram RED/GREEN, e a suíte voltou a passar. **Minor adiado:** intervalo histórico durante a repetição de hora do horário de verão em fevereiro de 2019 pode ser rejeitado incorretamente. Exemplo API: início `2019-02-16T23:30:00-02:00`, fim `2019-02-16T23:15:00-03:00` (45 minutos válidos em UTC). A comparação local com `ZoneInfo` precisa ser normalizada em UTC em correção posterior; a aceitação de datas históricas tem essa limitação conhecida.

## Depuração mais profunda pelo responsável

1. Revisar as escolhas provisórias de cancelamento/histórico, indisponibilidade, funcionamento e capacidade com a operação do laboratório.
2. Exercitar várias abas e administradores simultâneos: criação, edição de período, troca entre alvos e cancelamento, conferindo versão, bloqueio e eventos. Testar carga no banco/ambiente que vier a ser escolhido para produção.
3. Testar reservas longas e viradas de mês/ano, segundos/frações pela API e preservação ao editar pelo navegador, além do caso histórico de horário de verão conhecido.
4. Testar volume alto, paginação dos eventos, filtros, textos grandes e operação em navegadores/dispositivos adicionais.
5. Confirmar o contrato AgroHub (Q07): autenticação, identidade externa, chave de idempotência, fuso/período, edição/cancelamento e dados mínimos antes do próximo módulo.
