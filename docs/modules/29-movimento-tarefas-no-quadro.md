# Movimento de tarefas no quadro

Entrega de 08/10/2026, após revisão e aprovação do responsável. A mudança é somente no quadro de Tarefas; criação, edição e páginas de detalhes permanecem nos fluxos existentes. Não há migration nem novas regras de negócio.

## Uso

No computador, arrastar pela alça de pontos do cartão e soltar numa coluna destacada. Apenas destinos autorizados são destacados. Links e texto do cartão continuam utilizáveis normalmente. Soltar fora de um destino válido não altera a tarefa; Escape cancela o movimento.

O seletor **Mover para…** e o botão **Mover** oferecem a mesma mudança por teclado ou celular, inclusive quando o filtro mostra somente uma coluna. O arraste nativo é voltado a mouse; dispositivos de toque usam o seletor. Sem JavaScript, o formulário existente salva e retorna ao detalhe da tarefa.

Durante a gravação, os controles aguardam e o quadro informa o resultado. O cartão não muda de coluna antecipadamente: uma consulta atualiza os cartões, contadores e destinos com o estado persistido. Busca, serviço e aba continuam aplicados, incluindo texto ainda em digitação. A página atual é mantida se existir; se o movimento esvaziar a última página, retorna à primeira. Os eventos continuam funcionando após atualizações automáticas dos filtros.

Correção posterior de 08/10/2026: o quadro exige confirmação de que o script compartilhado iniciou a atualização. Se um script antigo em cache ou bloqueado ignorar o evento, recarrega a página por GET preservando filtros e retornando à primeira página, sem reenviar o POST. Os dois scripts usam versão na URL para renovar o cache. O sintoma relatado localmente (status persistido sem atualização visual) foi reproduzido com o script compartilhado da versão anterior; o cache da sessão do responsável não foi inspecionado diretamente.

## Regras preservadas

- Administradores ativos podem escolher qualquer outro status.
- Responsáveis atribuídos podem mover Demanda → Criação e Criação → Avaliação. Aprovar, recusar e reabrir continuam administrativos. Em Avaliação/Concluído, responsáveis não recebem controles de movimento.
- A API existente recebe somente `status` e `versao`, com sessão e CSRF. O servidor valida acesso e transição independentemente da interface.
- Descrição, serviço, responsáveis, equipamentos, materiais e suas quantidades permanecem intactos. Prazo continua herdado do serviço. Início/conclusão seguem a coerência já implementada pelo domínio; cada mudança real incrementa versão e registra histórico.
- Conflitos, acesso revogado e falhas de transporte não repetem o POST. O quadro reconsulta os dados antes de uma nova tentativa. Após 15 segundos sem resposta, libera os controles e trata o resultado como incerto, pois o servidor pode ter gravado antes da desconexão.
- Mensagens de movimento e consulta ficam empilhadas, sem sobreposição. Textos secundários e abas desta página receberam contraste mais legível.

## Verificação

Testes Django de destinos administrativos/responsáveis, espera pela aprovação, alternativa tradicional e preservação dos campos. O hospedeiro nativo valida usuário central e URLs com prefixo `/laboratorio/`.

Comandos executados: `python manage.py test --noinput` (598 testes aprovados), `python manage.py test inovalab_app.tests.portability --settings=inovalab_app.tests.host_settings --noinput` (9 aprovados), `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `node --check` nos scripts alterados e `git diff --check`. Não há alteração de schema. O verificador de Limpar filtros também foi reexecutado nas sete telas, com e sem JavaScript; seu seletor de teste agora identifica o campo de status dentro do formulário de filtros, distinguindo os novos formulários dos cartões.

`scripts/verificar-movimento-tarefas.cjs` executa Chromium contra banco dedicado. Exige `TASK_TEST_BASE_URL` e `TASK_TEST_SESSION` de administrador de testes; `TASK_TEST_OWNER_SESSION` habilita o cenário do responsável e `TASK_TEST_AXE_PATH` habilita axe-core. Usa `playwright-core` via `NODE_PATH`. **O script altera status das tarefas do banco dedicado**, restaurando Demanda para preparar o cenário; nunca apontar para produção ou banco pessoal.

Cenários: drag, teclado, toque via seletor, layouts 1366/768/390/360, datas e versão, filtro de coluna única, concorrência real (409), envio duplicado, falha de rede, timeout, resposta atrasada de busca, paginação válida/esvaziada, ausência de JavaScript, permissão do responsável e WCAG A/AA automatizada. Validar posteriormente Firefox/Safari e dispositivos móveis reais; a checagem automática não substitui avaliação manual com leitor de tela.

`scripts/verificar-atualizacao-tarefas.cjs` usa o mesmo servidor/sessão dedicados para verificar arraste com o script compartilhado antigo e bloqueado. Requer Git com o commit `bb5e9c9` disponível para o cenário histórico. Confirma persistência, atualização visual automática, filtros e somente um POST por movimento.
