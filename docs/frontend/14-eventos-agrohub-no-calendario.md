# Eventos AgroHub no calendário do index

Entrega de 06/10/2026: `/index/` e o alias `/painel/` consultam [GET /api/v1/agrohub/eventos/ — Ecosystem, Listar eventos](https://agrohub.unirv.edu.br/api/v1/schema/swagger-ui/#/Ecosystem/agrohub_eventos_list) e aplicam as datas aos seis meses do calendário existente.

## Comportamento

- Eventos ativos usam `start_date` e `end_date` no fuso `America/Sao_Paulo`. Sem término, marcar somente o dia de início. Com término, marcar os dias abrangidos pelo período; término exatamente à meia-noite não ocupa o dia seguinte. Eventos fora dos seis meses não aparecem.
- Dias de evento recebem vermelho `#eb1b23`, correspondente à legenda Evento. Títulos aparecem na dica do dia e no texto acessível para leitores de tela. Mais de um evento no mesmo dia conserva todos os títulos.
- Hoje mantém contorno neutro; reservas autorizadas conservam seu sublinhado e contagem. Esses indicadores podem coexistir com um evento real. A origem externa de um evento não cria reserva no InovaLab. Não são cadastrados recessos/feriados nem associadas essas categorias aos domingos.
- Eventos inativos, registros inválidos e IDs repetidos não acrescentam marcações. Títulos são escapados pelos templates; nenhum HTML ou link externo do evento é executado.
- A listagem é somente leitura. Não há formulário de criação de eventos nesta entrega.

## Consulta e cache

Reutiliza `AGROHUB_API_BASE_URL` e o transporte limitado do cliente AgroHub. A chamada fixa é GET `agrohub/eventos/?page=1&page_size=100`, seguida das páginas seguintes enquanto houver `next`. URLs de paginação recebidas não são acessadas: o cliente avança `page` na mesma origem e rota configuradas. Limite de 20 páginas, 100 registros por página e 512 KB de JSON por resposta.

O OpenAPI anuncia JWT nessa operação, mas a consulta anônima ao endpoint real retornou HTTP 200 com os eventos públicos. A implementação consulta essa listagem sem Bearer, filtra `is_active=true` e compartilha somente dados públicos normalizados. Tokens de usuários nunca entram nas consultas de eventos nem no cache. Se o provedor passar a exigir autenticação, a tela apresentará indisponibilidade; isso exige revisar o contrato antes de compartilhar respostas autenticadas.

Cache de sucesso por 300 segundos, com chave separada por base da API. O cache usa o backend Django configurado; o padrão local em memória pode ser recriado no runtime da Vercel. Reservas, tarefas, perfis e permissões não entram nesse cache. Falhas não são armazenadas: a próxima visita tenta novamente. Um evento alterado no AgroHub pode levar até cinco minutos para atualizar no mesmo processo.

Há um orçamento de cinco segundos **entre páginas**, e o timeout restante é aplicado a cada operação de socket. Isso não garante duração total máxima de cinco segundos: uma resposta que entrega bytes lentamente pode ultrapassar o orçamento durante a leitura. A revisão independente reproduziu essa limitação; não foi definido SLA total nesta solicitação.

Se houver erro HTTP/rede, JSON ou paginação inválida, ou o limite de páginas for atingido, nenhum resultado parcial é mostrado como completo. O dashboard continua respondendo e mantém tarefas/agendamentos, com o aviso **Não foi possível carregar os eventos do AgroHub. Tente atualizar a página.**

Arquivos principais: `core/agrohub_events.py` normaliza/cacheia o feed; `accounts/agrohub/client.py` faz o GET seguro; `core/dashboard.py` aplica as datas; view/template/CSS do dashboard exibem as marcações. Sem modelo ou migração novos.

## Verificações

```powershell
& .\venv\Scripts\python.exe manage.py test core --noinput
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check
```

Resultado: 22 testes de `core` e 480 testes completos passaram. `check` sem problemas; geração de migrações sem alterações; diff sem erros. Os oito testes novos usam HTTP em loopback, sem dependência de rede externa, e cobrem aplicação real ao index, escape de título, fuso, período/meia-noite, paginação, deduplicação/cache, origem fixa, inativos/datas inválidas, falha com recuperação, limite de páginas e coexistência com reservas/hoje. Os testes de identidade anteriores isolam o novo feed externo.

Uma consulta somente leitura à API real retornou dois eventos ativos e marcou **08/10/2026** no período atual. No navegador local, login usa uma conta de teste e a consulta de eventos usa o GET real: **Batalha de Robôs** apareceu em 08/10, cor computada `rgb(235, 27, 35)`, título acessível e sem aviso de falha. Verificados atualização de página, preferência da sidebar, desktop de 1200 px com sidebar expandida e celular de 360 px, sem rolagem horizontal e com imagens carregadas.

Revisão independente sem bloqueadores; limitação do timeout registrada acima. Nenhum evento remoto foi criado/alterado, nenhum deploy foi executado e a edição prévia de `.env.example` foi preservada.

Para depuração posterior: conferir novos eventos e suas alterações após o TTL do cache; verificar muitos eventos no mesmo dia e múltiplos períodos reais; validar conectividade e cache na implantação.
