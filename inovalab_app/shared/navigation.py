from django.urls import Resolver404, resolve, reverse

from inovalab_app.adapters.host import can_access_panel, get_adapter, is_business_admin, is_technical_admin
from inovalab_app.agenda.policies import can_access_agenda


def panel_navigation(request):
    actor = request.user
    if not actor.is_authenticated:
        return {}
    internal = can_access_panel(actor)
    admin = is_business_admin(actor)
    match = request.resolver_match
    if match is None:
        try:
            match = resolve(request.path_info)
        except Resolver404:
            pass
    if not internal:
        return {'can_access_panel': False, 'is_business_admin': False, 'nav_items': []}
    routes = [('Dashboard', 'core:dashboard', 'home')]
    if can_access_agenda(actor):
        routes.append(('Agendamentos', 'agenda:list', 'calendar'))
    routes.extend([('Estoque/materiais', 'materiais:list', 'box'), ('Tarefas', 'tarefas:board', 'task')])
    if admin:
        routes.append(('Banners', 'conteudo:list', 'image'))
    routes.append(('Infraestrutura', 'catalogo:equipamentos-list', 'building'))
    items = []
    for label, route, icon in routes:
        href = reverse(route)
        current = request.path.startswith(href)
        if route == 'core:dashboard':
            current = bool(match and match.namespace == 'core')
        elif route == 'conteudo:inicio':
            current = bool(match and match.namespace == 'conteudo' and
                           match.url_name in {'inicio', 'sobre', 'servicos', 'contato', 'regimento', 'calendario-funcionamento'})
        elif route == 'catalogo:equipamentos-list':
            current = bool(match and match.namespace == 'catalogo')
        items.append({'label': label, 'href': href, 'icon': icon, 'current': current})
    identity = get_adapter().identity_context(request)
    if is_technical_admin(actor) and identity.get('users_url'):
        items.insert(4, {'label': 'Usuários', 'href': identity['users_url'], 'icon': 'users',
                         'current': request.path.startswith(identity['users_url'])})
    if identity.get('profile_url'):
        items.append({'label': 'Perfil', 'href': identity['profile_url'], 'icon': 'profile',
                      'current': request.path.startswith(identity['profile_url'])})
    return {'can_access_panel': True, 'is_business_admin': admin, 'nav_items': items}
