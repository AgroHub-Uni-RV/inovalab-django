# Sidebar, calendário e logo

Entrega de correções solicitadas após a padronização visual. Mantém a escala de `core/static/core/ui.css`, os módulos existentes e suas permissões.

## Comportamento

- Dashboard: legenda Recesso verde (`#76b82a`), Feriado azul (`#00a3d8`) e Evento vermelho (`#eb1b23`) para todos os usuários internos. A atualização de 06/10/2026 passa a [aplicar os eventos reais do AgroHub](14-eventos-agrohub-no-calendario.md). Domingos, hoje e reservas não recebem cores dessas categorias por si: hoje usa contorno neutro; reservas autorizadas mantêm contagem acessível e sublinhado neutro. Recessos e feriados continuam sem cadastro.
- Páginas (`/publico/` e `/publico/sobre/`): usuários autenticados veem sidebar, cabeçalho, rodapé e abas Início/Sobre; visitantes mantêm a base pública. A consulta continua mostrando apenas banners publicados para o local/período, inclusive para administradores; prévias privadas continuam na gestão de Banners.
- Sidebar: `localStorage['inovalab.sidebar.expanded']` guarda apenas a preferência visual, com valores `true`/`false`, no navegador atual. Navegação, atualização, Escape e fechamento móvel preservam a escolha. Sem preferência, inicia recolhida. Se o navegador bloquear o armazenamento, o menu continua funcionando, mas a preferência não persiste.
- Ícones recolhidos: centralizados na largura de 79 px. Antes da correção, a posição medida ficava 3,5 px à esquerda do centro.
- Logo: arquivo original copiado de `Referencias/logo.png` para `core/static/core/assets/logo.png`, sem edição. Aplicado no login, sidebar e cabeçalho público; fundo branco dá contraste ao texto azul. Marcas institucionais restantes aguardam seus arquivos.

Esta solicitação substitui a pendência anterior de manter a logo do InovaLab em branco. O layout de login permanece em duas áreas, com `/` para login e `/index/` após entrar.

## Verificação

```powershell
.\venv\Scripts\python.exe manage.py test --noinput
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
git diff --check

# Servidor iniciado e sessão ajustes-layout autenticada no agent-browser:
.\scripts\verificar-sidebar-calendario.ps1 -BaseUrl http://127.0.0.1:8000
```

O script usa `agent-browser` disponível no ambiente. Navega, atualiza, mede o DOM real e alterna a sidebar; modifica somente a preferência local, sem gravar dados de negócio. A sessão precisa ser de administrador para consultar Banners. `scripts/medir-sidebar-calendario.js` mede centro dos ícones, legenda/cores, estrutura, imagens e transbordamento.

O teste inicial reproduziu dez falhas entre 14 verificações do navegador. Os testes Django adicionais reproduziram a ausência da base interna em ambas as páginas, para administrador e usuário comum.

A suíte completa passou com **311 testes Django**. `manage.py check` não apontou problemas e `makemigrations --check --dry-run` não encontrou novas migrações. O fluxo de sidebar/calendário passou nas **17 verificações** finais em Chrome, incluindo HTTP 200, centros dos ícones, logo carregada, cores, estrutura, navegação, atualização e Escape no celular. A indisponibilidade de `localStorage` foi simulada em um iframe que carrega o HTML/JavaScript reais: abriu e fechou o menu sem erros.

A revisão independente não apontou problemas críticos/importantes. O ajuste menor do cabeçalho público em 320 px foi aplicado: as regras de largura da logo e gap passaram a usar `@media`, pois o cabeçalho não possui ancestral com `container-type`. A conferência posterior confirmou logo de 100 px, carregada, HTTP 200 e ausência de transbordamento. Banco e mídia usados no navegador são fixtures temporárias próprias; os dados reais permanecem preservados.

A comparação visual de Dashboard/Início/Sobre passou em **15 combinações** de largura/menu (1920, 1201 e 360 px), com HTTP 200, Montserrat, alinhamentos, abas ativas e ausência de transbordamento externo ou imagens quebradas. O medidor de padrões foi ajustado para recolher o menu antes de medir, pois a preferência persistida pode iniciar a página expandida. A logo incorporada tem o mesmo SHA256 do arquivo de referência. O login também foi conferido em 320 px, com logo carregada e sem transbordamento.

Capturas com fixtures: [Dashboard e legenda em 1920 px](screenshots/dashboard-legenda-sidebar-1920.png), [Páginas com sidebar expandida em 1920 px](screenshots/paginas-sidebar-1920.png), [Sobre em 360 px](screenshots/paginas-sidebar-360.png), [Página pública e logo em 320 px](screenshots/publico-logo-320.png) e [login com logo em 320 px](screenshots/login-logo-320.png).

## Conferência pelo responsável

1. Navegar e atualizar páginas com o menu aberto e fechado, no desktop e celular.
2. Conferir calendário, logo e centralização dos ícones com seus dados reais.
3. Abrir Início/Sobre autenticado e após sair; conferir que banners privados continuam fora da publicação.
4. Usar `Ctrl+F5` para atualizar os estilos; conferir Firefox/Safari e o ambiente de hospedagem posteriormente.
