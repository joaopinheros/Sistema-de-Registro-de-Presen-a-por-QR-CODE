from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('alunos/', views.gerenciar_alunos, name='gerenciar_alunos'),
    path('professores/', views.gerenciar_professores, name='gerenciar_professores'),
    path('salas/', views.gerenciar_salas, name='gerenciar_salas'),
    path('disciplinas/', views.gerenciar_disciplinas, name='gerenciar_disciplinas'),
    path('aulas/', views.gerenciar_aulas, name='gerenciar_aulas'),
    path('aulas/nova/', views.criar_aula, name='criar_aula'),
    path('presencas/', views.gerenciar_presencas, name='gerenciar_presencas'),
]

# urlpatterns = [
#    path('', dashboard, name='dashboard'),
# ]
