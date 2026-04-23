import uuid
import secrets
from django.db import models
from django.utils import timezone
from apps.accounts.models import Professor


class Sala(models.Model):
    nome = models.CharField(max_length=100, verbose_name='Nome da Sala')
    predio = models.CharField(max_length=100, verbose_name='Prédio')
    latitude = models.DecimalField(max_digits=10, decimal_places=8, verbose_name='Latitude')
    longitude = models.DecimalField(max_digits=11, decimal_places=8, verbose_name='Longitude')
    raio_permitido = models.PositiveIntegerField(default=50, verbose_name='Raio Permitido (metros)')
    capacidade = models.PositiveIntegerField(default=40, verbose_name='Capacidade')
    ativa = models.BooleanField(default=True, verbose_name='Ativa')

    class Meta:
        verbose_name = 'Sala'
        verbose_name_plural = 'Salas'
        ordering = ['predio', 'nome']

    def __str__(self):
        return f'{self.nome} - {self.predio}'


class Disciplina(models.Model):
    SEMESTRE_CHOICES = [(str(i), f'{i}º Semestre') for i in range(1, 11)]

    nome = models.CharField(max_length=200, verbose_name='Nome')
    codigo = models.CharField(max_length=20, unique=True, verbose_name='Código')
    professor = models.ForeignKey(
        Professor, on_delete=models.PROTECT,
        related_name='disciplinas', verbose_name='Professor Responsável'
    )
    semestre = models.CharField(max_length=2, choices=SEMESTRE_CHOICES, verbose_name='Semestre')
    ano = models.PositiveIntegerField(default=2024, verbose_name='Ano')
    descricao = models.TextField(blank=True, verbose_name='Descrição')
    ativa = models.BooleanField(default=True, verbose_name='Ativa')
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Disciplina'
        verbose_name_plural = 'Disciplinas'
        ordering = ['nome']

    def __str__(self):
        return f'{self.codigo} - {self.nome} ({self.semestre}º/{self.ano})'


class Aula(models.Model):
    disciplina = models.ForeignKey(
        Disciplina, on_delete=models.CASCADE,
        related_name='aulas', verbose_name='Disciplina'
    )
    sala = models.ForeignKey(
        Sala, on_delete=models.PROTECT,
        related_name='aulas', verbose_name='Sala'
    )
    data = models.DateField(verbose_name='Data')
    horario_inicio = models.TimeField(verbose_name='Horário de Início')
    horario_fim = models.TimeField(verbose_name='Horário de Fim')
    token_qrcode = models.CharField(
        max_length=64, unique=True, editable=False,
        verbose_name='Token QR Code'
    )
    qrcode_imagem = models.ImageField(
        upload_to='qrcodes/', blank=True, null=True,
        verbose_name='Imagem QR Code'
    )
    descricao = models.CharField(max_length=255, blank=True, verbose_name='Descrição')
    ativa = models.BooleanField(default=True, verbose_name='Ativa')
    criada_em = models.DateTimeField(auto_now_add=True)
    atualizada_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Aula'
        verbose_name_plural = 'Aulas'
        ordering = ['-data', '-horario_inicio']

    def __str__(self):
        return f'{self.disciplina.codigo} - {self.data} {self.horario_inicio}'

    def save(self, *args, **kwargs):
        if not self.token_qrcode:
            self.token_qrcode = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def esta_ativa(self):
        now = timezone.localtime(timezone.now())
        today = now.date()
        current_time = now.time()
        return (
            self.data == today and
            self.horario_inicio <= current_time <= self.horario_fim
        )

    @property
    def presenca_url(self):
        from django.conf import settings
        return f"{settings.SYSTEM_BASE_URL}/presenca?id={self.id}&token={self.token_qrcode}"
