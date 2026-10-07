from django.urls import include, path
from importlib import import_module


def api_routes(domain):
    patterns = import_module('inovalab_app.'+domain+'.api_urls').urlpatterns
    for pattern in patterns:
        pattern.callback.inovalab_access = (
            'public' if pattern.name == 'public-banners' else
            'booking' if domain == 'agenda' else 'internal')
    return patterns

urlpatterns = [
    path('api/v1/', include(api_routes('catalogo'))),
    path('api/v1/', include(api_routes('tarefas'))),
    path('api/v1/', include(api_routes('agenda'))),
    path('api/v1/', include(api_routes('materiais'))),
    path('api/v1/', include(api_routes('conteudo'))),
    path('catalogo/', include('inovalab_app.catalogo.urls')),
    path('tarefas/', include('inovalab_app.tarefas.urls')),
    path('agenda/', include('inovalab_app.agenda.urls')),
    path('materiais/', include('inovalab_app.materiais.urls')),
    path('', include('inovalab_app.shared.urls')),
    path('', include('inovalab_app.conteudo.urls')),
]
