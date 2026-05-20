from django.urls import path
from . import admin_views

urlpatterns = [
    path('', admin_views.painel_admin_dashboard, name='painel_admin_dashboard'),
    path('usuarios/', admin_views.painel_admin_usuarios, name='painel_admin_usuarios'),
    path('usuarios/<int:user_id>/editar/', admin_views.editar_usuario, name='editar_usuario'),
    path('salas/', admin_views.painel_admin_salas, name='painel_admin_salas'),
    path('salas/<int:sala_id>/editar/', admin_views.editar_sala, name='editar_sala'),
    path('disciplinas/', admin_views.painel_admin_disciplinas, name='painel_admin_disciplinas'),
    path('disciplinas/<int:disc_id>/editar/', admin_views.editar_disciplina, name='editar_disciplina'),
    path('disciplinas/<int:disc_id>/alunos/', admin_views.disciplina_alunos_api, name='disciplina_alunos_api'),
    path('disciplinas/<int:disc_id>/presencas/', admin_views.disciplina_presencas_api, name='disciplina_presencas_api'),
    path('vincular/', admin_views.painel_admin_vincular, name='painel_admin_vincular'),
    path('vincular/api/', admin_views.vincular_api, name='painel_admin_vincular_api'),
    path('relatorios/', admin_views.painel_admin_relatorios, name='painel_admin_relatorios'),
    path('dashboard/dados-graficos/', admin_views.dashboard_dados_graficos, name='admin_dashboard_graficos'),
]
