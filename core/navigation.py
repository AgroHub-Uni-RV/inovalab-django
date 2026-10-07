from django.urls import reverse

from accounts.policies import can_access_panel, is_business_admin, is_technical_admin
from agenda.policies import can_access_agenda


def panel_navigation(request):
    actor = request.user
    if not actor.is_authenticated:
        return {}
    internal = can_access_panel(actor)
    admin = is_business_admin(actor)
    if not internal:
        return {'can_access_panel': False, 'is_business_admin': False, 'nav_items': []}
    routes = [('Dashboard', 'core:dashboard', 'home')]
    if can_access_agenda(actor):
        routes.append(('Agendamentos', 'agenda:list', 'calendar'))
    routes.extend([('Estoque/materiais', 'materiais:list', 'box'), ('Tarefas', 'tarefas:board', 'task')])
    if is_technical_admin(actor):
        routes.append(('Usuários', 'accounts:users', 'users'))
    if admin:
        routes.append(('Banners', 'conteudo:list', 'image'))
    routes.extend([('Páginas', 'conteudo:inicio', 'layers'), ('Estrutura', 'catalogo:servicos-list', 'building')])
    routes.append(('Perfil', 'accounts:home', 'profile'))
    items = []
    for label, route, icon in routes:
        href = reverse(route)
        current = request.path.startswith(href)
        if route == 'core:dashboard':
            current = request.path in ('/index/', '/painel/')
        elif route == 'conteudo:inicio':
            current = request.path in ('/', '/sobre/', '/servicos/', '/contato/', '/regimento/', '/calendario-de-funcionamento/')
        elif route == 'catalogo:servicos-list':
            current = request.path.startswith('/catalogo/')
        items.append({'label': label, 'href': href, 'icon': icon, 'current': current})
    return {'can_access_panel': True, 'is_business_admin': admin, 'nav_items': items}
