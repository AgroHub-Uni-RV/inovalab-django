# Carrossel de equipamentos em Serviços

Solicitação de 11/10/2026: corrigir o carrossel de equipamentos de `/servicos/`, acrescentar a seta para a esquerda e repetir a sequência em loop depois do último equipamento.

O carrossel avança ou volta um equipamento por vez, usando a largura e o espaçamento reais dos cards. Depois do último, continua no primeiro; antes do primeiro, continua no último, mantendo a passagem visual na mesma direção. O loop é aplicado somente ao carrossel de Serviços; a página inicial conserva a navegação existente.

As duas setas preservam o visual dos controles atuais e têm rótulos acessíveis. No desktop ficam nas laterais; até 760 px ficam abaixo dos cards para preservar a largura de leitura. O teclado usa as setas esquerda/direita quando a lista está focada, e a rolagem horizontal continua disponível para toque. Respeita a preferência de movimento reduzido e conserva o equipamento atual ao redimensionar a tela.

As cópias nas extremidades são criadas uma única vez, ocultas para leitores de tela e inertes, sem duplicar IDs ou elementos focáveis. A lista não cresce durante a navegação. As setas e as cópias ficam ocultas quando todos os equipamentos cabem na área; catálogo vazio ou unitário permanece simples. Sem JavaScript, os registros originais continuam disponíveis por rolagem horizontal, sem botões inativos aparentes.

O catálogo ativo, nomes, descrições, imagens WebP do banco e autorização permanecem os mesmos. Sem mudanças de banco, dependências, migrações, push ou deploy.

## Verificação

`venv/Scripts/python.exe manage.py test inovalab_app.tests.conteudo --noinput`: 78 testes passaram. `manage.py check`, `node --check inovalab_app/static/inovalab_app/conteudo/institucional/site.js` e `git diff --check`: aprovados.

Chromium aprovado em cinco larguras (1920, 1366, 768, 390 e 320 px): loop nos dois sentidos, teclado, cliques rápidos, quantidade fixa de cópias, ausência de transbordamento externo, redimensionamento, rolagem pelas extremidades, toque, preferência de movimento reduzido, catálogos com zero/um/dois itens e alternativa sem JavaScript. Banco isolado de verificação; aguardar depuração do responsável antes de outra entrega.
