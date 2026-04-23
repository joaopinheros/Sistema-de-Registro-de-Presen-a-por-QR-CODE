from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='audit_logs',
        verbose_name='Usuário'
    )
    acao = models.CharField(max_length=100, verbose_name='Ação')
    detalhe = models.TextField(blank=True, verbose_name='Detalhe')
    ip = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP')
    user_agent = models.CharField(max_length=500, blank=True, verbose_name='User Agent')
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name='Data/Hora')

    class Meta:
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'
        ordering = ['-timestamp']

    def __str__(self):
        return f'[{self.timestamp:%d/%m/%Y %H:%M}] {self.usuario} - {self.acao}'
