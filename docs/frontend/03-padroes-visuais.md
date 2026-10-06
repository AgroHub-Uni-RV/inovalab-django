# Padrões visuais compartilhados

A solicitação de padronização parte da margem lateral maior em Banners. A página limitava o conteúdo a 1160 px, enquanto os demais módulos usavam 1436 px. Existiam também medidas próprias nos contadores de Banners/Usuários e um estilo de formulário que acrescentava borda e padding aos filtros de Materiais.

Esta entrega consolida a apresentação existente dos módulos, perfil, Dashboard, páginas públicas e login. Mantém a composição e as cores das referências locais, com seus dados e ações atuais. As logos continuam reservadas para inclusão futura pelo responsável. A manutenção técnica avançada no Django Admin mantém sua apresentação própria.

## Escala

As definições compartilhadas ficam em [`core/static/core/ui.css`](../../core/static/core/ui.css). Os templates das três bases carregam esse arquivo antes dos estilos de layout. Montserrat é servida localmente, com os pesos variáveis de 100 a 900.

| Elemento | Padrão |
| --- | --- |
| Conteúdo, cabeçalho e rodapé internos | Mesma largura máxima de 1436 px e alinhamento |
| Margem horizontal mínima | 32 px no desktop; 16 px até 760 px |
| Espaço superior/inferior do conteúdo | 64/48 px no desktop; 24/32 px no celular |
| Escala de espaçamentos | 4, 8, 12, 16, 20, 24, 32, 40, 48 e 64 px |
| Gap principal entre cartões e campos | 24 px; componentes compactos usam a escala de 8 a 20 px |
| Cantos de cartões, painéis, campos e botões | 12 px |
| Cantos de etiquetas, miniaturas e controles pequenos | 8 px |
| Avatares | Circulares |
| Títulos de página | 28 px; 24 px no celular |
| Títulos de seção | 20 px |
| Corpo, campos e ações principais | 16 px |
| Rótulos e tabelas | 14 px |
| Texto auxiliar / anotações compactas | 12 / 10 px |
| Contadores | Título 20/18 px e valor 56/48 px conforme espaço disponível |
| Altura mínima de campos e ações principais | 56 px |

Espaçamentos são aplicados por função: distância entre seções, padding de cartões, gap de campos e espaçamento de texto. Equivalentes têm a mesma medida em cada módulo; calendário, Kanban e tabelas conservam suas composições próprias. Formulários e detalhes usam a mesma tipografia dos títulos de listagem. O login conserva a composição em duas áreas e utiliza a Montserrat e os componentes da escala comum.

As listagens têm o mesmo alinhamento externo, inclusive quando a sidebar é expandida. As regiões de tabela e calendário mantêm rolagem própria quando necessário. Filtros de listagem ficam diretamente sobre o fundo da página; formulários de cadastro permanecem nos painéis apropriados.

## Verificação no navegador

[`scripts/verificar-padroes-visuais.ps1`](../../scripts/verificar-padroes-visuais.ps1) consulta as páginas em uma sessão já autenticada como superusuário. [`scripts/medir-padroes-visuais.js`](../../scripts/medir-padroes-visuais.js) recarrega os CSS com uma URL de verificação, evitando medidas de versões antigas em cache, e mede o DOM após o carregamento da fonte. A verificação compara alinhamentos e componentes equivalentes e detecta transbordamento externo, imagens quebradas, fonte ausente, rótulos que ultrapassam o contador e indicadores de aba ativa ocultos.

```powershell
# Com o servidor iniciado e a sessão do agent-browser autenticada:
.\scripts\verificar-padroes-visuais.ps1 -BaseUrl http://127.0.0.1:8000

# Permite restringir a verificação ou registrar todas as medidas:
.\scripts\verificar-padroes-visuais.ps1 -BaseUrl http://127.0.0.1:8000 `
  -Widths 1920,1366,820,768,360 -Paths /agenda/,/banners/,/materiais/,/usuarios/ `
  -OutputPath .superpowers/padroes-visuais.json
```

O comando usa o `agent-browser` disponível neste ambiente; não é uma dependência de execução do Django. A verificação consulta páginas e alterna a sidebar, sem criar ou editar registros. Para testar outros papéis, use uma sessão desse usuário e informe apenas suas rotas autorizadas. Uma resposta de login ou acesso negado para rota privada interrompe a verificação.

O teste inicial no Chrome reproduziu os desalinhamentos e diferenças de medidas, antes de alterar os estilos. As verificações da entrega usam banco e mídia temporários próprios, sem modificar os registros reais.

## Resultados da entrega

```powershell
& .\venv\Scripts\python.exe manage.py test --noinput
& .\venv\Scripts\python.exe manage.py check
& .\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check
```

309 testes Django passaram. A configuração, a ausência de novas migrações e o diff também foram verificados. A correção é visual; não há alterações nos modelos, contratos de API ou permissões.

No Chrome, a matriz de 16 páginas em seis larguras passou em 171 combinações de página/menu. Os primeiros 37 registros dessa matriz antecederam a inclusão da coleta do status HTTP; os demais 134 registraram HTTP 200. Uma consulta adicional às 35 rotas de listagem, cadastro, edição, detalhes, históricos, confirmação e publicação confirmou HTTP 200 sem redirecionamentos.

A revisão independente encontrou uma regressão no Dashboard em 1201 px com sidebar expandida: títulos e abas invadiam o espaço vizinho, embora a página não tivesse transbordamento externo. O teste foi ampliado para medir esses componentes. A disposição passou a considerar a largura disponível no conteúdo. Após a correção, 17 combinações do Dashboard em nove larguras passaram, incluindo 1201 px. Outros 29 casos de detalhes, históricos e formulários em 1366/360 px passaram após esse ajuste. O script inclui 1201 px entre as larguras padrão para manter essa cobertura.

Também foram conferidos: login em 1920/1366/360 px, senha inválida e entrada válida com retorno ao index; menu móvel/Escape; formulário de banner inválido em 360 px, com erros visíveis e sem transbordamento; upload com Montserrat. O espaçamento entre o ID e o nome das tarefas do Dashboard agora respeita os 8 px da escala, usando a largura real do ID. O caso de rótulo longo no contador de Usuários foi reproduzido em 1440 px e corrigido pela reorganização dos cartões. A pendência visual registrada na entrega anterior foi tratada aqui.

A conferência das capturas identificou que o indicador azul das abas ficara oculto após converter o deslocamento de borda em margem de espaçamento. O deslocamento agora acompanha a espessura da borda de 2 px, separado da escala de gaps. A verificação da visibilidade do indicador passou em 35 combinações de Banners, Materiais, Tarefas, Usuários e Catálogo, em quatro larguras, recarregando os estilos atuais.

Uma revisão independente foi concluída, com um problema importante corrigido e nenhum ajuste menor adicional apontado. Seu escopo manteve as decisões já autorizadas: Django Admin técnico, funcionalidades novas, APIs e permissões ficam fora da apresentação desta entrega; logos serão incluídas pelo responsável; comparação exata no Figma continua indisponível; outros navegadores/hospedagem e testes mais profundos permanecem para a depuração posterior.

Capturas com fixtures: [Banners em 1920 px](screenshots/banners-padroes-1920.png), [Agenda em 1920 px](screenshots/agenda-padroes-1920.png), [Dashboard em 1201 px com menu expandido](screenshots/dashboard-padroes-1201-menu.png) e [Formulário de banner em 360 px](screenshots/banner-form-padroes-360.png).

Ao conferir um navegador que já estava aberto durante a alteração, use `Ctrl+F5` para recarregar os estilos. A entrega permanece local na branch `feat/frontend-completo`, aguardando a depuração do responsável.

## Depuração pelo responsável

1. Comparar Banners, Agenda, Materiais, Tarefas e Usuários na mesma janela, com o menu aberto e fechado.
2. Conferir nomes reais extensos, filtros, estados vazios e contadores com números maiores.
3. Abrir formulários e detalhes, verificar mensagens de erro e confirmar a apresentação dos campos e ações.
4. Conferir login, perfil, Dashboard e páginas públicas em desktop e celular; usar teclado e rolagem das tabelas/calendário.
5. Conferir Firefox/Safari e as fontes no ambiente de hospedagem futuro. Os testes básicos desta entrega usam Chrome local.
