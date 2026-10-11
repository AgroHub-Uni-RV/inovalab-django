# Agenda mais compacta

Solicitação de 11/10/2026: melhorar a UX de `/agenda/`, conservar a ordem e o design dos elementos e diminuir o calendário.

Os ajustes ficam restritos a `.agenda-page`. Mantida a sequência: título/ações, contadores, filtros, informação do mês, calendário, legenda, lista e paginação. Cores, bordas, arredondamentos, fontes, ícones e formatos dos botões permanecem iguais. A margem externa do painel continua original, sem espaço reservado para a ilha.

- Cabeçalho quebra entre seus elementos, evitando dividir a palavra Agendamentos. A ordem das ações permanece.
- Os dois contadores distribuem-se igualmente na largura disponível e empilham em telas estreitas, com o mesmo design dos cartões.
- Filtros usam grade responsiva, preservando sua ordem e os campos existentes. Busca e seletores aproveitam a largura disponível; as consultas automáticas e Limpar filtros continuam funcionando.
- Espaçamento entre seções reduzido com a escala compartilhada, aproximando informação do mês, calendário, legenda e lista.
- Altura mínima dos dias reduzida de 220 para 104 px. Cabeçalho semanal e reservas têm menos padding, mantendo tipografia, cores e bordas. A largura mínima do calendário passa de 840 para 700 px, com rolagem horizontal própria nas telas menores.
- Dias com reservas crescem para manter todos os dados exibidos. A regra de três reservas por dia com acesso às restantes na lista permanece.

## Verificação

`venv/Scripts/python.exe manage.py test inovalab_app.tests.agenda inovalab_app.tests.shared.test_clear_filters --noinput`: 206 testes passaram. `venv/Scripts/python.exe manage.py check`: sem problemas. `git diff --check`: aprovado.

Chromium em banco isolado, em 1920, 1366, 900, 768, 390 e 320 px, com dois meses: ordem preservada, mesmas cores/bordas/arredondamentos, mesmas reservas, sem transbordamento externo e padding original. Na amostra de 1366 px, o calendário passou de 1282,8 para 766,8 px e de 1361,1 para 794,8 px, redução aproximada de 40%. Conferidos filtros, Limpar filtros, criação pelo modal, rolagem do calendário pelo teclado, acesso da equipe e filtro sem JavaScript.

Sem mudanças de banco, regras de negócio, permissões ou APIs. Aguardar a depuração do responsável antes de outra entrega; sem push ou deploy.
