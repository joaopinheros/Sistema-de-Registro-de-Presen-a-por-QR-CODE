from django.contrib import admin
from django.utils.html import format_html
from .models import Sala, Disciplina, Aula


@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    list_display = ['nome', 'predio', 'capacidade', 'raio_permitido', 'ativa']
    list_filter = ['predio', 'ativa']
    search_fields = ['nome', 'predio']


@admin.register(Disciplina)
class DisciplinaAdmin(admin.ModelAdmin):
    list_display = ['codigo', 'nome', 'professor', 'semestre', 'ano', 'ativa']
    list_filter = ['semestre', 'ano', 'ativa']
    search_fields = ['nome', 'codigo', 'professor__user__first_name']
    raw_id_fields = ['professor']


@admin.register(Aula)
class AulaAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'sala', 'data', 'horario_inicio', 'horario_fim', 'ativa', 'qr_preview']
    list_filter = ['ativa', 'data', 'disciplina']
    search_fields = ['disciplina__nome', 'disciplina__codigo', 'sala__nome']
    date_hierarchy = 'data'
    raw_id_fields = ['disciplina', 'sala']
    readonly_fields = ['token_qrcode', 'qrcode_imagem', 'criada_em']

    def qr_preview(self, obj):
        if obj.qrcode_imagem:
            return format_html('<img src="{}" width="50" height="50" />', obj.qrcode_imagem.url)
        return '-'
    qr_preview.short_description = 'QR Code'
