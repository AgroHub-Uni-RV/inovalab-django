from rest_framework.routers import SimpleRouter

from inovalab_app.tarefas.api import TaskViewSet


app_name = 'tarefas_api'
router = SimpleRouter()
router.register('tarefas', TaskViewSet, basename='tarefa')
urlpatterns = router.urls
