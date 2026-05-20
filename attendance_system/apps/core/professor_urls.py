from django.urls import path
from . import professor_views

urlpatterns = [
    path('', professor_views.painel_professor_dashboard, name='painel_professor_dashboard'),
    path('aulas/', professor_views.painel_professor_aulas, name='painel_professor_aulas'),
    path('disciplinas/', professor_views.painel_professor_disciplinas, name='painel_professor_disciplinas'),
    path('disciplinas/<int:disc_id>/alunos/', professor_views.disciplina_alunos_api, name='prof_disciplina_alunos_api'),
    path('presencas/', professor_views.painel_professor_presencas, name='painel_professor_presencas'),
    path('dashboard/dados-graficos/', professor_views.dashboard_dados_graficos, name='prof_dashboard_graficos'),
]
