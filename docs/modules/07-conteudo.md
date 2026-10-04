# Módulo 7 — Conteúdo e banners

Entrega local em 04/10/2026, conforme o [plano simples](../superpowers/plans/2026-10-04-conteudo.md). F3 autorizou desenvolver o módulo 7. O PDF confirma título, imagem WebP, status e local; a tela F4 apresenta consulta, edição, desativação, exclusão e ordem. Administração exclusiva, consulta pública, período obrigatório e vários banners ordenados são escolhas iniciais para depuração de Q10/Q12/Q15; a pergunta opcional não recebeu resposta nesta entrega. Não classificá-las como confirmação adicional do responsável.

## Uso e regras

Após entrar, administradores usam **Banners** ou `/banners/`. Superusuários ativos e membros ativos de `Administradores` consultam e mantêm o cadastro completo. `is_staff` sozinho não concede acesso. Contas comuns, inativas, visitantes e credenciais de integradores não administram banners. O frontend de identidade foi preservado, acrescentando apenas o link administrativo.

| Campo | Contrato |
| --- | --- |
| titulo | Obrigatório, até 150 caracteres; nomes repetidos permitidos |
| texto_alternativo | Opcional, até 250; a publicação usa o título se vazio |
| banner_img | Upload WebP real e estático; obrigatório na criação, opcional na edição |
| status | `ativo`, `inativo` ou `agendado`; formulário/modelo iniciam inativo |
| local | `home` ou `sobre` |
| ordem | Inteiro de 0 a 2147483647; padrão 0, menor primeiro, desempate por ID |
| inicio_exibicao/fim_exibicao | Ambos obrigatórios para agendado, com fim posterior ao início; vazios nos outros estados |
| versao | Inicial 1, definida pelo servidor; incrementada em alteração/exclusão aceita |

Textos são aparados nas bordas. Tamanhos, alternativa textual, limite de arquivo, versão e exclusão lógica são escolhas técnicas. Vários banners podem ocupar o mesmo local, inclusive no mesmo período. Editar ordem não renumera os demais.

Ativo publica imediatamente; inativo permanece oculto. Agendado publica quando `início <= agora < fim`, calculado em cada leitura, sem cron. Interface recebe horário de Brasília; API exige ISO8601 com fuso e normaliza UTC. Ao mudar um agendado para ativo/inativo, limpar os dois horários. A lista administrativa apresenta o status configurado, sem alterar automaticamente agendado para ativo.

Imagem aceita até **5 MiB (5242880 bytes)** e **4096 × 4096 pixels**. Pillow decodifica os bytes; MIME/extensão informados não comprovam formato. PNG renomeado, arquivo truncado, WebP animado, dimensão/tamanho excedente e conteúdo inválido são rejeitados antes de persistir. WebP válido com nome original `.png` é aceito e armazenado com UUID e extensão `.webp`. Não há conversão automática, base64 nem upload por URL.

| Caminho web | Operação |
| --- | --- |
| `/banners/` | Administração paginada em 25 itens |
| `/banners/novo/` | Cadastro com upload |
| `/banners/{id}/` | Detalhe e preview administrativo |
| `/banners/{id}/editar/` | Metadados, período, ordem, status ou substituição de imagem |
| `/banners/{id}/excluir/` | GET confirma; POST com versão exclui logicamente |
| `/publico/` | Página pública dos banners elegíveis em home |
| `/publico/sobre/` | Página pública dos banners elegíveis em sobre |
| `/banners/{id}/imagem/` | Imagem elegível ou preview de administrador; caso contrário 404 |

As páginas públicas mostram todos os elegíveis em ordem, com imagens responsivas e alternativa textual. Quando vazias, mostram uma mensagem simples. `/` continua sendo a página privada de identidade. Não foi construído um site institucional completo ou carrossel.

Escritas web exigem CSRF. Formulário inválido retorna 200 com erros; versão ausente/inválida em edição e exclusão retorna 400; versão antiga retorna 409 e permanece no campo oculto para impedir sobrescrita silenciosa. Depois de conflito, consultar novamente antes de decidir a correção. Upload deve ser selecionado novamente após erro do formulário.

## API administrativa

Autenticação por sessão Django; escritas exigem CSRF. Token Bearer de integrador não autentica esta API. JSON nas alterações de metadados; multipart na criação/substituição com arquivo. `application/x-www-form-urlencoded` não é aceito.

| Método/caminho | Operação |
| --- | --- |
| `GET /api/v1/banners/` | Cadastro completo, paginação 25 |
| `POST /api/v1/banners/` | Criar com `banner_img` multipart; 201 |
| `GET /api/v1/banners/{id}/` | Detalhe administrativo |
| `PUT /api/v1/banners/{id}/` | Exige título, status, local e versão; imagem e opcionais omitidos são preservados |
| `PATCH /api/v1/banners/{id}/` | Campos desejados e versão; 200 |
| `DELETE /api/v1/banners/{id}/` | Enviar versão; 204, exclusão lógica |

Na criação, título/status/local e arquivo são obrigatórios; alt, ordem e datas são opcionais conforme status. `versao` inicial é proibida. Campos desconhecidos, `id`, `imagem_url`, caminho de armazenamento e `excluido_em` não são alteráveis. Campos repetidos no multipart são rejeitados. Não registrar `Banner` no Django Admin para contornar a operação compartilhada.

Versão e ordem em JSON exigem inteiro real: string, booleano e decimal são rejeitados. Em multipart, aceita-se string de dígitos ASCII não negativa. Versão de escrita entre 1 e 9223372036854775806. Enviar a versão obtida no detalhe, nunca incrementá-la no cliente.

Exemplo PATCH de agendamento:

```json
{
  "status": "agendado",
  "inicio_exibicao": "2026-11-01T10:00:00-03:00",
  "fim_exibicao": "2026-11-01T11:00:00-03:00",
  "ordem": 2,
  "versao": 1
}
```

Exemplo de desativação do agendamento atualizado:

```json
{"status": "inativo", "inicio_exibicao": null, "fim_exibicao": null, "versao": 2}
```

DELETE: `{"versao": 3}`. A resposta administrativa contém ID, título, alternativa textual, URL controlada da imagem, status, local, ordem, horários e versão; não devolve nome original ou caminho do arquivo.

| Resposta | Situação |
| --- | --- |
| 400 | Campos, imagem, horários ou versão inválidos |
| 403 | Sessão ausente/inativa, papel insuficiente ou CSRF inválido |
| 404 | Inexistente, excluído ou página de lista inexistente |
| 409 | `{"detail":"…","code":"versao_desatualizada"}`; consultar antes de tentar novamente |
| 405 | Método não oferecido |
| 415 | Formato de corpo não aceito |

## Consulta pública e imagem

`GET /api/v1/publico/banners/?local=home` ou `?local=sobre` dispensa autenticação; local obrigatório/válido, paginação de 25 com `count/next/previous/results`. Somente GET/HEAD/OPTIONS. Cada resultado contém exatamente:

```json
{
  "id": 1,
  "titulo": "InovaLab",
  "texto_alternativo": "InovaLab",
  "imagem_url": "/banners/1/imagem/",
  "local": "home",
  "ordem": 0
}
```

URL da imagem é relativa à origem do InovaLab. Consumidores devem resolvê-la nessa origem e tratar 404 se o banner sair de publicação entre catálogo e download. Inativos, futuros, expirados e excluídos não revelam metadados na consulta pública. O mesmo seletor aplica a regra em HTML/API/imagem; a rota de imagem consulta arquivo e elegibilidade na mesma leitura para não misturar versões em substituição concorrente.

Administrador ativo pode visualizar imagem não publicada de cadastro existente; excluídos não permitem preview. Resposta WebP, `X-Content-Type-Options: nosniff`, `Cache-Control: no-store`, nome genérico `banner-{id}.webp`. Imagem não publicada, inexistente ou arquivo ausente retorna 404 genérico também sem cache, permitindo nova leitura após publicação. Páginas/API também sem cache. Cada pedido revalida publicação; isso não apaga uma imagem que um visitante já baixou.

`MEDIA_ROOT` local é `media/`, ignorado no Git; não há rota pública direta `/media/`, inclusive em desenvolvimento. Não acrescentar `static(settings.MEDIA_URL, document_root=...)` nem servir esse diretório com nginx/CDN irrestritos: isso contornaria a autorização. Arquivo ausente retorna 404. Nunca expor `banner_img.url` no HTML/serializador público.

## Persistência e concorrência

`save_banner` valida o cadastro inteiro e os bytes antes de gravar um novo UUID. Uma edição atualiza todos os campos em um único UPDATE condicionado por ID/versão e ausência de exclusão. Duas substituições da mesma versão produzem um vencedor, sem misturar título/arquivo; o arquivo novo do perdedor é removido. Falha da persistência também remove somente o upload novo.

Imagens anteriores são preservadas em substituição e exclusão lógica, evitando apagar arquivo em uso. O cadastro excluído fica fora de todas as consultas operacionais; não há restauração, remoção física nem histórico adicional. Deve-se definir política de retenção/limpeza e monitorar armazenamento antes de produção. Backup precisa incluir banco e arquivos.

Chamadores atuais usam autocommit e não `ATOMIC_REQUESTS`. Envolver esse serviço em transação externa com rollback exige desenho adicional do ciclo de vida do arquivo: o serviço não remove automaticamente upload cuja gravação foi revertida por um chamador externo depois de retornar. Storage remoto, CDN, carga e banco de produção não foram verificados.

## Verificação executada

Python 3.14.3, Django 6.1.1, DRF 3.18.1 e **Pillow 12.3.0**, acrescentado a `requirements.txt`. Migração aditiva `conteudo.0001_initial` aplicada no banco local.

```powershell
& .\venv\Scripts\python.exe -m pip install -r requirements.txt
& .\venv\Scripts\python.exe manage.py migrate
& .\venv\Scripts\python.exe manage.py test conteudo
& .\venv\Scripts\python.exe manage.py test
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
& .\venv\Scripts\python.exe -m pip check
git diff --check
```

**36 testes de banners**: 12 de domínio, 1 de concorrência com conexões reais SQLite, 12 de API e 11 web. **Suíte completa: 270 testes passaram.** Checks, drift de migração, dependências e diff verificados. Validação inclui limites/formato/animação, upload com falha de banco, versão/permissões/CSRF, paginação/ordem, horários equivalentes e limites exatos de início/fim, privacidade e exclusão.

Revisão independente única encontrou um Important: consulta separada autorizava a imagem anterior privada após substituição/ativação concorrente. Regressão `test_image_and_publication_are_read_from_same_version` falhou antes e passou depois da consulta unificada; suíte completa verde. A verificação do executor identificou ausência de no-store no 404 de imagem; `test_image_not_found_responses_cannot_cache_publication_state` confirmou RED/GREEN e Chrome verificou o cabeçalho corrigido. Nenhum Critical. **Minor adiado:** inteiro multipart de administrador com mais de 4300 dígitos pode gerar 500 por `ValueError`, em vez de 400; limites e entradas usuais são validados. Não afeta consulta pública nem concede autorização.

Chrome verificou upload válido e PNG renomeado rejeitado, preview, troca de imagem, consulta pública/local, ordem, agendamento dentro e fora do período, alt derivado, inativação, exclusão com teclado, CSRF e versões antigas web/API, staff negado e `/media/` inacessível. Layout público/formulário a 360 px; um título de 150 caracteres sem espaços causava rolagem, corrigido e verificado de 2547 para 360 px. Foco visível e imagens carregadas; nenhuma exceção JavaScript da aplicação. O CLI não preencheu `datetime-local` com `fill`; a automação usou o valor nativo e eventos do campo, sem modificar o produto. Fixtures próprias de três banners/quatro arquivos, duas contas/sessões removidas; Chrome e servidor encerrados.

## Depuração restante

1. Validar Q10/Q12/Q15: autoridade exclusiva, leitura pública, vários banners, ordem, período e política de exclusão/retenção.
2. Testar imagens e textos reais, leitores de tela, mais combinações de tamanho/limites e duas abas editando/substituindo/excluindo o mesmo banner.
3. Validar consumidores reais, URLs relativas, paginação e tratamento de imagem 404 após revogação/expiração.
4. Definir produção, backup/restauração conjunta de banco/arquivos, retenção e desempenho; o AgroHub real permanece sem conexão validada.
5. Priorizar o Minor de inteiro multipart extremo e o Minor histórico de horário de verão da agenda conforme uso. São pendências conhecidas, não novos módulos.

Os sete módulos planejados possuem entrega funcional local. Aguardar sua depuração; melhorias visuais e novas funcionalidades exigem nova etapa autorizada.
