"""
Signals de auditoria.

Monitora automaticamente criação, edição e exclusão dos modelos principais
e registra no AuditLog usando o usuário capturado pelo AuditMiddleware
(via thread-local) para que os signals tenham acesso ao request.
"""
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import AuditLog
from .middleware import get_current_user, get_current_request
from apps.attendance.validators import get_client_ip


# ── Helper ────────────────────────────────────────────────────────────────────

def _log(acao, detalhe=''):
    """Cria AuditLog com usuário e IP do request corrente."""
    user = get_current_user()
    request = get_current_request()
    ip = get_client_ip(request) if request else None
    user_agent = ''
    if request:
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:500]
    AuditLog.objects.create(
        usuario=user,
        acao=acao,
        detalhe=detalhe,
        ip=ip,
        user_agent=user_agent,
    )


# ── Login / Logout ────────────────────────────────────────────────────────────

@receiver(user_logged_in)
def log_login(sender, request, user, **kwargs):
    AuditLog.objects.create(
        usuario=user,
        acao='login',
        detalhe=f'Login realizado por {user.get_full_name() or user.username}',
        ip=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
    )


@receiver(user_logged_out)
def log_logout(sender, request, user, **kwargs):
    AuditLog.objects.create(
        usuario=user,
        acao='logout',
        detalhe=f'Logout realizado por {user.get_full_name() or user.username}',
        ip=get_client_ip(request),
        user_agent=request.META.get('HTTP_USER_AGENT', '')[:500],
    )


# ── Aula ─────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='courses.Aula')
def log_aula_save(sender, instance, created, **kwargs):
    acao = 'CRIACAO' if created else 'EDICAO'
    _log(f'AULA_{acao}', f'Aula ID={instance.id} | {instance.disciplina.codigo} | {instance.data}')


@receiver(post_delete, sender='courses.Aula')
def log_aula_delete(sender, instance, **kwargs):
    _log('AULA_EXCLUSAO', f'Aula ID={instance.id} | {instance.disciplina.codigo} | {instance.data}')


# ── Presença ──────────────────────────────────────────────────────────────────

@receiver(post_save, sender='attendance.Presenca')
def log_presenca_save(sender, instance, created, **kwargs):
    acao = 'CRIACAO' if created else 'EDICAO'
    _log(
        f'PRESENCA_{acao}',
        f'Presença ID={instance.id} | aluno={instance.aluno_id} | aula={instance.aula_id} | status={instance.status}'
    )


@receiver(post_delete, sender='attendance.Presenca')
def log_presenca_delete(sender, instance, **kwargs):
    _log('PRESENCA_EXCLUSAO', f'Presença ID={instance.id} | aluno={instance.aluno_id} | aula={instance.aula_id}')


# ── Disciplina ────────────────────────────────────────────────────────────────

@receiver(post_save, sender='courses.Disciplina')
def log_disciplina_save(sender, instance, created, **kwargs):
    acao = 'CRIACAO' if created else 'EDICAO'
    _log(f'DISCIPLINA_{acao}', f'Disciplina ID={instance.id} | {instance.codigo} — {instance.nome}')


@receiver(post_delete, sender='courses.Disciplina')
def log_disciplina_delete(sender, instance, **kwargs):
    _log('DISCIPLINA_EXCLUSAO', f'Disciplina ID={instance.id} | {instance.codigo}')


# ── Sala ──────────────────────────────────────────────────────────────────────

@receiver(post_save, sender='courses.Sala')
def log_sala_save(sender, instance, created, **kwargs):
    acao = 'CRIACAO' if created else 'EDICAO'
    _log(f'SALA_{acao}', f'Sala ID={instance.id} | {instance.nome} — {instance.predio}')


@receiver(post_delete, sender='courses.Sala')
def log_sala_delete(sender, instance, **kwargs):
    _log('SALA_EXCLUSAO', f'Sala ID={instance.id} | {instance.nome}')


# ── Student ───────────────────────────────────────────────────────────────────

@receiver(post_save, sender='accounts.Student')
def log_student_save(sender, instance, created, **kwargs):
    if created:
        _log('ALUNO_CRIACAO', f'Aluno ID={instance.id} | matrícula={instance.matricula}')


@receiver(post_delete, sender='accounts.Student')
def log_student_delete(sender, instance, **kwargs):
    _log('ALUNO_EXCLUSAO', f'Aluno ID={instance.id} | matrícula={instance.matricula}')


# ── Professor ─────────────────────────────────────────────────────────────────

@receiver(post_save, sender='accounts.Professor')
def log_professor_save(sender, instance, created, **kwargs):
    if created:
        nome = instance.user.get_full_name() if instance.user_id else '?'
        _log('PROFESSOR_CRIACAO', f'Professor ID={instance.id} | {nome}')


@receiver(post_delete, sender='accounts.Professor')
def log_professor_delete(sender, instance, **kwargs):
    nome = instance.user.get_full_name() if instance.user_id else '?'
    _log('PROFESSOR_EXCLUSAO', f'Professor ID={instance.id} | {nome}')
