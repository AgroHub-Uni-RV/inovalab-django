# Autosave, formulários e confirmações

Entrega de 11/10/2026, conforme `docs/superpowers/plans/2026-10-11-autosave-formularios-confirmacoes.md`, em quatro commits de implementação além do plano.

## Status e equipamentos públicos

Alterar o status em Ver tarefa salva automaticamente pela API de transições existente. Durante o envio, o seletor fica desabilitado. O resultado é anunciado e os detalhes, histórico e relógio são consultados novamente. Conflitos mostram o estado atual; falhas não repetem o POST. Se a consulta também falhar, a tarefa exige atualização da página antes de nova alteração. Sem JavaScript, Salvar status continua disponível. Permissões, versões e regras do relógio permanecem no domínio.

Equipamentos em `/servicos/` utiliza nome, descrição e foto dos equipamentos ativos do catálogo. Fotos usam o endpoint público de infraestrutura; equipamentos excluídos não aparecem. Há apresentação para equipamento sem foto e catálogo vazio.

## Formulários

Banners, equipamentos e materiais abrem em um diálogo compartilhado, tanto pelos links do painel quanto pelas URLs diretas. Os campos são organizados em seções, com orientações, erros próximos aos campos e ações de salvar/cancelar. Equipamentos e banners têm prévia da imagem selecionada. Arquivos selecionados são mantidos após erro de validação dentro do modal.

O banner mostra o período ao selecionar Agendado ou quando existem datas/erros; mudar o status não apaga datas. Limpar período é uma ação explícita. As restrições de upload existentes continuam: banners aceitam WebP estático até 5 MiB; equipamentos convertem novas fotos para WebP persistido no banco.

## Confirmações

Exclusão de tarefa, banner e equipamento, restauração dos equipamentos padrão e cancelamento interno/pessoal de agendamento usam o mesmo modal. Aprovação, recusa e registro de realização de visita pedem confirmação antes de enviar os formulários existentes. Confirmar serviço continua abrindo a criação da tarefa obrigatória.

Restaurar padrões mantém equipamentos personalizados e vínculos históricos, conforme a preferência aprovada. Exclusões continuam lógicas. Nenhuma confirmação grava dados ao abrir ou fechar o diálogo.

## Comportamento compartilhado

O diálogo oferece título acessível, foco contido, fechamento por Escape e retorno de foco à origem. Envios duplicados e fechamento durante gravação são bloqueados. O sucesso é reconhecido somente pela resposta explícita emitida após a operação autorizada; redirecionamento para login não é tratado como sucesso. CSRF, autorização e conflitos continuam nos endpoints existentes.

Após sucesso, a origem é consultada novamente, preservando filtros e paginação válida; página esvaziada volta à primeira. Se o detalhe foi excluído, segue para a lista. Uma consulta pendente dos filtros é interrompida ao abrir o modal para não substituir os dados atualizados. Falha de resposta bloqueia novo envio até consultar os dados, sem reenvio automático. Conflitos oferecem recarga explícita. Páginas completas e seus POST/redirect continuam funcionando sem JavaScript.

Login, identidade, recuperação de senha e interface técnica do Django Admin permanecem fora deste módulo. Não há migrações ou mudanças de contrato da API JSON existente. Apenas requisições web com `X-UI-Modal: 1` recebem a confirmação JSON de sucesso.

## Verificação

- `venv/Scripts/python.exe manage.py test --noinput`: 658 testes passaram em 67,8 segundos.
- `venv/Scripts/python.exe manage.py check`: sem problemas.
- `venv/Scripts/python.exe manage.py makemigrations --check --dry-run`: sem alterações.
- `venv/Scripts/python.exe manage.py check_inovalab_upgrade`: banco compatível.
- Chromium em banco isolado: autosave e pausa/retomada do relógio; criação/edição dos três cadastros; upload mantido após erro; publicação do equipamento; período do banner; exclusões, restauração, aprovação, cancelamento interno/externo e realização; conflitos, falha sem repetir POST, filtros, foco/teclado, largura móvel e fluxos sem JavaScript.

O responsável fará a depuração com dados e autenticação do ambiente conectado. Não houve push, deploy ou alteração do banco publicado.
