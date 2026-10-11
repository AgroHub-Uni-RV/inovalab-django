# Tempo das tarefas e infraestrutura padrão

Entrega de 11/10/2026, organizada em [brainstorm](../superpowers/specs/2026-10-11-tarefas-infraestrutura-design.md), [planejamento](../superpowers/plans/2026-10-11-tarefas-infraestrutura.md) e quatro commits de implementação.

## Relógio

A topbar de Ver tarefa mostra HH:MM:SS, com horas que podem ultrapassar 24. Uma nova Demanda começa em zero. `tempo_criacao` guarda a duração acumulada e `criacao_desde` ancora o intervalo aberto. Somente Criação conta; Avaliação, Concluído, Demanda e exclusão pausam. Reentrada em Criação retoma o acumulado, inclusive após recusa/reabertura. Retornar administrativamente a Demanda preserva o trabalho já contado.

Gravações ocorrem nas operações já existentes, na mesma transação protegida por versão e com histórico. O navegador avança a exibição localmente, sem consultas ou gravações por segundo, suspendendo o intervalo de renderização quando a aba fica oculta. Fechar a página não interrompe a execução. Recarregar consulta o tempo persistido e o status atual; alterações por outra sessão são refletidas na próxima consulta.

`0008` reconstrói os intervalos disponíveis nos eventos sem mudar versões/eventos. Uma tarefa em Criação sem início comprovável no histórico começa a contar a partir da migração, sem atribuir duração antiga estimada. A API acrescenta `tempo_execucao_segundos`, `tempo_criacao` e `criacao_desde`, todos somente leitura.

## Quadro e lista

`/tarefas/` limita Concluídos às últimas 168 horas, com limite inclusivo. Contadores, filtros, cartões e paginação compartilham esse recorte. As demais colunas continuam mostrando todas as tarefas válidas.

Lista completa em `/tarefas/lista/`, com busca, serviço, status, responsável, De/Até, Limpar filtros e paginação de 25 itens. Datas inicial/final incluem o dia inteiro no fuso do projeto. O período usa conclusão para concluídas, início para outras tarefas iniciadas e evento de criação para as não iniciadas. Datas inválidas/invertidas mostram erros. Administradores veem todas as não excluídas; responsáveis veem somente suas tarefas. Opções de serviço/responsável também respeitam essa autorização.

## Equipamentos

Os seis padrões reproduzem os itens da antiga Estrutura pública: Plotter de impressão, Impressora 3D, Corte a Laser, Plotter de corte de madeira e acrílico, Óculos VR e Scanner 3D. A seção passa a Infraestrutura e consulta o catálogo ativo do banco, incluindo personalizados. Fotos públicas são servidas somente para equipamentos não excluídos; a rota interna mantém fotos históricas protegidas por autenticação.

`foto_webp` guarda bytes WebP no banco. Novos uploads são decodificados, orientados por EXIF, limitados a 1920 × 1920 e convertidos na gravação. O campo `foto`/contrato da API conserva nome e URL, sem expor bytes nas listagens. As imagens padrão continuam empacotadas no repositório para carga/restauração, mas sua resposta HTTP utiliza os bytes persistidos. Listagens e relações de tarefas adiam a leitura dos bytes.

`0009` cria padrões ausentes em instalações novas/existentes. Preserva nomes/descrições personalizados, status e exclusões; ajusta somente valores conhecidos dos padrões antigos. Fotos padrão são copiadas para o banco e uploads antigos legíveis são convertidos. Se um arquivo antigo estiver ausente, mantém a referência original sem apagar o registro; reenvie a foto para completar sua conversão. Os originais existentes em media não são apagados.

Restaurar equipamentos padrão aparece como ação secundária no painel e abre confirmação. Somente POST administrativo com CSRF restaura nome, descrição, foto, disponibilidade e exclusão dos padrões, mantendo seus IDs, vínculos e equipamentos personalizados. `seed_inovalab` apenas cria ausentes; não restaura padrões excluídos ou substitui edições.

Excluir está disponível na lista, nos detalhes e na edição para administradores, com confirmação. Remove do catálogo ativo e da infraestrutura pública por exclusão lógica; mantém tarefas/agendamentos e históricos. Padrões podem ser excluídos e posteriormente restaurados.

## Validação e banco local

- `venv/Scripts/python.exe manage.py test --noinput`: **649 testes, OK**, incluindo atualização de bancos e hospedeiro separado.
- `manage.py check`: sem problemas; `manage.py check_inovalab_upgrade`: banco compatível; `manage.py makemigrations --check --dry-run`: nenhuma mudança pendente.
- `scripts/verificar-tempo-lista-infraestrutura.cjs`: Chromium em banco isolado, com desktop 1366 px, celular 390 px e JavaScript desabilitado. Verificou relógio sem polling, pausa/recarga, filtros/paginação, padrão excluído, vínculo da tarefa e restauração com personalizado preservado. Capturas em `.private/browser-verification/screenshots/`.
- SQLite de trabalho: backup íntegro em `.private/backups/db-antes-tempo-infraestrutura-20261011-131233.sqlite3`; `0008`/`0009` aplicadas. Seis padrões com WebP registrados, um equipamento personalizado e a tarefa existente preservados.

O verificador exige `playwright-core` disponível ao Node, `TASK_TEST_BASE_URL` de servidor dedicado e `TASK_TEST_FIXTURES` de JSON com sessão administrativa e IDs `running`, `old`, `equipment`, `custom` e `owner`. Preparar 28 tarefas, uma concluída há oito dias, uma em Criação vinculada à Impressora 3D e um equipamento chamado Equipamento personalizado de verificação. Ele altera essas fixtures; usar somente banco isolado.

Restam a depuração do responsável com dados reais e a aplicação das migrações no banco publicado, com backup/pausa de escrita e verificação PostgreSQL no ambiente escolhido. Não houve push nem deploy nesta entrega.
