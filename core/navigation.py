from django.urls import reverse

from accounts.policies import is_business_admin


def panel_navigation(request):
    actor = request.user
    if not actor.is_authenticated:
        return {}
    admin = is_business_admin(actor)
    routes = [('Dashboard', 'core:dashboard', 'home')]
    if admin:
        routes.append(('Agendamentos', 'agenda:list', 'calendar'))
    routes.extend([('Estoque/materiais', 'materiais:list', 'box'), ('Tarefas', 'tarefas:board', 'task')])
    if actor.is_active and actor.is_superuser:
        routes.append(('Usuários', 'admin:accounts_user_changelist', 'users'))
    if admin:
        routes.append(('Banners', 'conteudo:list', 'image'))
    routes.extend([('Páginas', 'conteudo:public-home', 'layers'), ('Estrutura', 'catalogo:servicos-list', 'building')])
    if admin:
        routes.append(('Integrações', 'integracoes:list', 'link'))
    routes.append(('Perfil', 'accounts:home', 'profile'))
    items = []
    for label, route, icon in routes:
        href = reverse(route)
        current = request.path.startswith(href)
        if route == 'core:dashboard':
            current = request.path in ('/index/', '/painel/')
        items.append({'label': label, 'href': href, 'icon': icon, 'current': current})
    return {'is_business_admin': admin, 'nav_items': items}
