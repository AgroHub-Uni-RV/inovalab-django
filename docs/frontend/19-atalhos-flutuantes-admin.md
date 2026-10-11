# Atalhos flutuantes do administrador

Entrega autorizada em 11/10/2026. O painel oferece uma ilha flutuante à direita, centralizada verticalmente na janela, com Criar tarefa e Criar agendamento.

- Exibida pelo servidor somente para administradores ativos do laboratório, usando `is_business_admin` e as permissões existentes.
- Incluída na estrutura do painel; páginas institucionais não exibem a ilha, mesmo com administrador autenticado.
- Ícones reutilizados do sistema, rótulos no hover/foco e nomes acessíveis para leitores de tela. Áreas de toque de 44 × 44 pixels.
- Criar tarefa abre o modal de tarefas; Criar agendamento abre o modal de seleção de tipo. Não escolhe categoria antecipadamente nem grava ao abrir.
- Links preservam as URLs e funcionam como navegação normal sem JavaScript.
- A ilha flutua sobre a página, sem reservar espaço lateral ou alterar o padding original do conteúdo, conforme ajuste solicitado na depuração. A versão compacta móvel mantém a posição à direita. A ilha pertence à estrutura que fica inerte com o menu móvel aberto.
- Oculta durante modais e abertura do menu móvel. Fechar os modais devolve o foco ao atalho usado.
- Sem JavaScript adicional, polling, mudanças de banco ou novas regras de autorização.

## Verificação

`venv/Scripts/python.exe manage.py test --noinput`: 660 testes passaram em 66,9 segundos. Inclui acesso aos atalhos nas páginas internas, ausência para equipe/contas externas e ausência nas páginas públicas. `venv/Scripts/python.exe manage.py check`: sem problemas.

Após remover o padding adicional, `venv/Scripts/python.exe manage.py test inovalab_app.tests.shared --noinput`: 40 testes passaram; `manage.py check` continuou sem problemas. Chromium confirmou o padding padrão de 32 px no desktop e 16 px no celular, com os mesmos atalhos e modais funcionando.

Chromium em banco isolado: posição central/lateral em desktop e celular, padding original preservado, abertura dos dois modais por teclado/toque, fechamento e retorno de foco, integração com menu móvel, ausência para equipe e página pública, links funcionando sem JavaScript. Nenhum erro JavaScript nos cenários.

Aguardar a depuração do responsável antes da próxima entrega. Sem push ou deploy.
