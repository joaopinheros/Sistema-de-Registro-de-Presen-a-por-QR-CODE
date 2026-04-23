from django.contrib import admin
from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['timestamp', 'usuario', 'acao', 'ip', 'detalhe']
    list_filter = ['acao', 'timestamp']
    search_fields = ['usuario__email', 'acao', 'detalhe', 'ip']
    date_hierarchy = 'timestamp'
    readonly_fields = ['usuario', 'acao', 'detalhe', 'ip', 'user_agent', 'timestamp']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser
