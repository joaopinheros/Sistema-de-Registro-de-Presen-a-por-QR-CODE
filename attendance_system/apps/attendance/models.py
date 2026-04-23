from django.db import models
from django.utils import timezone
from apps.accounts.models import Student
from apps.courses.models import Aula


class Presenca(models.Model):
    class Status(models.TextChoices):
        PRESENTE = 'presente', 'Presente'
        AUSENTE = 'ausente', 'Ausente'
        NEGADO = 'negado', 'Negado'
        PENDENTE = 'pendente', 'Pendente'

    aluno = models.ForeignKey(
        Student, on_delete=models.CASCADE,
        related_name='presenças', verbose_name='Aluno'
    )
    aula = models.ForeignKey(
        Aula, on_delete=models.CASCADE,
        related_name='presenças', verbose_name='Aula'
    )
    horario_registro = models.DateTimeField(default=timezone.now, verbose_name='Horário do Registro')
    ip_registrado = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP Registrado')
    latitude = models.DecimalField(
        max_digits=10, decimal_places=8,
        null=True, blank=True, verbose_name='Latitude'
    )
    longitude = models.DecimalField(
        max_digits=11, decimal_places=8,
        null=True, blank=True, verbose_name='Longitude'
    )
    status = models.CharField(
        max_length=10, choices=Status.choices,
        default=Status.PENDENTE, verbose_name='Status'
    )
    motivo_negacao = models.TextField(blank=True, verbose_name='Motivo de Negação')
    validado_rede = models.BooleanField(default=False, verbose_name='Rede Universitária Validada')
    validado_geo = models.BooleanField(default=False, verbose_name='Geolocalização Validada')

    class Meta:
        verbose_name = 'Presença'
        verbose_name_plural = 'Presenças'
        ordering = ['-horario_registro']
        unique_together = [('aluno', 'aula')]

    def __str__(self):
        return f'{self.aluno} - {self.aula} [{self.status}]'
