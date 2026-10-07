from django.urls import reverse

from accounts.policies import is_business_admin
from agenda.policies import can_access_agenda


def panel_navigation(request):
    actor = request.user
    if not actor.is_authenticated:
        return {}
    admin = is_business_admin(actor)
    routes = [('Dashboard', 'core:dashboard', 'home')]
    if can_access_agenda(actor):
        routes.append(('Agendamentos', 'agenda:list', 'calendar'))
    if admin:
        routes.append(('Solicitações de agendamento', 'agenda:requests', 'calendar'))
    routes.extend([('Estoque/materiais', 'materiais:list', 'box'), ('Tarefas', 'tarefas:board', 'task')])
    if actor.is_active and actor.is_superuser:
        routes.append(('Usuários', 'accounts:users', 'users'))
    if admin:
        routes.append(('Banners', 'conteudo:list', 'image'))
    routes.extend([('Páginas', 'conteudo:inicio', 'layers'), ('Estrutura', 'catalogo:servicos-list', 'building')])
    if admin:
        routes.append(('Integrações', 'integracoes:list', 'link'))
    routes.append(('Perfil', 'accounts:home', 'profile'))
    items = []
    for label, route, icon in routes:
        href = reverse(route)
        current = request.path.startswith(href)
        if route == 'core:dashboard':
            current = request.path in ('/index/', '/painel/')
        elif route == 'conteudo:inicio':
            current = request.path in ('/', '/sobre/', '/servicos/', '/contato/')
        elif route == 'catalogo:servicos-list':
            current = request.path.startswith('/catalogo/')
        elif route == 'agenda:list':
            current = request.path.startswith(href) and not request.path.startswith(reverse('agenda:requests'))
        items.append({'label': label, 'href': href, 'icon': icon, 'current': current})
    return {'is_business_admin': admin, 'nav_items': items}
