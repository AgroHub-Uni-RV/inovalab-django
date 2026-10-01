from django.urls import path

from tarefas import views


app_name = 'tarefas'
urlpatterns = [
    path('', views.TaskBoardView.as_view(), name='board'),
    path('nova/', views.TaskCreateView.as_view(), name='create'),
    path('<int:pk>/', views.TaskDetailView.as_view(), name='detail'),
    path('<int:pk>/editar/', views.TaskUpdateView.as_view(), name='update'),
    path('<int:pk>/excluir/', views.TaskDeleteView.as_view(), name='delete'),
    path('<int:pk>/transicoes/', views.transition_view, name='transition'),
    path('<int:pk>/historico/', views.TaskHistoryView.as_view(), name='history'),
]
