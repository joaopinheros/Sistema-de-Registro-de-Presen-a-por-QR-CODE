from django.contrib import admin
from .models import Presenca


@admin.register(Presenca)
class PresencaAdmin(admin.ModelAdmin):
    list_display = [
        'aluno', 'aula', 'horario_registro', 'status',
        'ip_registrado', 'validado_rede', 'validado_geo'
    ]
    list_filter = ['status', 'validado_rede', 'validado_geo', 'aula__data']
    search_fields = [
        'aluno__user__first_name', 'aluno__user__last_name',
        'aluno__matricula', 'aula__disciplina__nome'
    ]
    date_hierarchy = 'horario_registro'
    readonly_fields = ['horario_registro', 'ip_registrado', 'validado_rede', 'validado_geo']

    def has_add_permission(self, request):
        return request.user.is_superuser
