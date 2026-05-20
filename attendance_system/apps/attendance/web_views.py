from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from apps.courses.models import Aula
from apps.attendance.models import Presenca
from apps.attendance.validators import AttendanceValidator, get_client_ip, marcar_presenca_cache
from apps.attendance.serializers import PresencaSerializer
from apps.audit.utils import log_action
import json
import logging

logger = logging.getLogger(__name__)


@require_GET
def presenca_scanner(request):
    return render(request, 'attendance/scanner_qr.html')


def _erro_amigavel(errors):
    """Converte erros técnicos do validator em mensagens amigáveis para o aluno."""
    for e in errors:
        el = e.lower()
        if 'rede' in el or 'universidade' in el or 'conectado' in el:
            return 'Você precisa estar na rede da universidade.'
        if 'token' in el or 'qr' in el or 'expirado' in el:
            return 'QR Code inválido ou expirado.'
        if 'horário' in el or 'aula não é hoje' in el or 'encerrou' in el or 'começa' in el:
            return 'Esta aula não está ativa no momento.'
        if 'já registrada' in el or 'duplicata' in el or 'cache' in el:
            return 'Você já registrou presença nesta aula.'
    return errors[0] if errors else 'Erro ao registrar presença.'


@require_http_methods(["GET", "POST"])
def presenca_scan(request):
    from urllib.parse import urlencode

    aula_id = request.GET.get('id') or request.POST.get('aula_id')
    token   = request.GET.get('token') or request.POST.get('token')

    if not aula_id or not token:
        return render(request, 'attendance/erro.html', {'tipo': 'sem_qr'})

    try:
        aula = Aula.objects.select_related(
            'disciplina__professor__user', 'sala'
        ).get(id=aula_id, ativa=True)
    except Aula.DoesNotExist:
        return render(request, 'attendance/erro.html', {
            'tipo': 'invalido',
            'mensagem': 'QR Code inválido ou expirado.',
        })

    if aula.token_qrcode != token:
        return render(request, 'attendance/erro.html', {
            'tipo': 'invalido',
            'mensagem': 'QR Code inválido ou expirado.',
        })

    if not request.user.is_authenticated:
        next_url = f'/presenca/registrar/?id={aula_id}&token={token}'
        return redirect(f'/accounts/login/?{urlencode({"next": next_url})}')

    # GET — tela de confirmação
    if request.method == 'GET':
        return render(request, 'attendance/registrar.html', {
            'aula': aula,
            'token': token,
            'estado': 'confirmar',
        })

    # POST — registrar presença
    if not request.user.is_student:
        return render(request, 'attendance/registrar.html', {
            'aula': aula,
            'token': token,
            'estado': 'erro',
            'mensagem': 'Somente alunos podem registrar presença.',
        })

    aluno = request.user.student_profile

    from apps.attendance.validators import checar_presenca_cache as _checar
    if _checar(aula.id, aluno.id) or Presenca.objects.filter(
        aluno=aluno, aula=aula, status=Presenca.Status.PRESENTE
    ).exists():
        return render(request, 'attendance/registrar.html', {
            'aula': aula,
            'estado': 'erro',
            'mensagem': 'Você já registrou presença nesta aula.',
        })

    validator = AttendanceValidator(request=request, aula=aula, token=token, aluno_id=aluno.id)

    if validator.run():
        Presenca.objects.create(
            aluno=aluno,
            aula=aula,
            ip_registrado=validator.ip,
            status=Presenca.Status.PRESENTE,
            validado_rede=validator.validado_rede,
            validado_geo=False,
        )
        marcar_presenca_cache(aula.id, aluno.id)
        log_action(request.user, 'PRESENÇA_REGISTRADA', f'Aula ID {aula.id}', request)
        return render(request, 'attendance/registrar.html', {
            'aula': aula,
            'estado': 'sucesso',
        })

    return render(request, 'attendance/registrar.html', {
        'aula': aula,
        'token': token,
        'estado': 'erro',
        'mensagem': _erro_amigavel(validator.errors),
    })


@login_required
@require_http_methods(["POST"])
def registrar_presenca_ajax(request):
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Dados inválidos'}, status=400)

    user = request.user

    if not user.is_student:
        return JsonResponse({
            'success': False,
            'error': 'Somente alunos podem registrar presença.'
        }, status=403)

    aula_id = data.get('aula_id')
    token = data.get('token')
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if not all([aula_id, token, latitude, longitude]):
        return JsonResponse({
            'success': False,
            'error': 'Parâmetros incompletos.'
        }, status=400)

    try:
        aula = Aula.objects.get(id=aula_id, ativa=True)
    except Aula.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Aula não encontrada ou inativa.'
        }, status=404)

    if aula.token_qrcode != token:
        return JsonResponse({
            'success': False,
            'error': 'QR Code inválido ou expirado.'
        }, status=403)

    # Bloqueia só se já tiver PRESENTE — falha anterior não impede nova tentativa
    if Presenca.objects.filter(
        aluno=user.student_profile, aula=aula, status=Presenca.Status.PRESENTE
    ).exists():
        return JsonResponse({
            'success': False,
            'error': 'Presença já registrada para esta aula.'
        }, status=409)

    aluno = user.student_profile
    validator = AttendanceValidator(
        request=request,
        aula=aula,
        token=token,
        student_lat=float(latitude),
        student_lon=float(longitude),
        aluno_id=aluno.id,
    )

    if validator.run():
        try:
            presenca = Presenca.objects.get(aluno=aluno, aula=aula)
            presenca.ip_registrado = validator.ip
            presenca.latitude = latitude
            presenca.longitude = longitude
            presenca.status = Presenca.Status.PRESENTE
            presenca.motivo_negacao = ''
            presenca.validado_rede = validator.validado_rede
            presenca.validado_geo = validator.validado_geo
            presenca.horario_registro = timezone.now()
            presenca.save()
        except Presenca.DoesNotExist:
            presenca = Presenca.objects.create(
                aluno=aluno,
                aula=aula,
                ip_registrado=validator.ip,
                latitude=latitude,
                longitude=longitude,
                status=Presenca.Status.PRESENTE,
                validado_rede=validator.validado_rede,
                validado_geo=validator.validado_geo,
            )
        # Marcar presença no Redis (TTL 24h) para evitar duplicatas
        marcar_presenca_cache(aula.id, aluno.id)
        log_action(user, 'PRESENÇA_REGISTRADA', f'Aula ID {aula.id}', request)
        return JsonResponse({
            'success': True,
            'message': 'Presença registrada com sucesso!',
            'data': PresencaSerializer(presenca).data
        }, status=201)
    else:
        try:
            presenca = Presenca.objects.get(aluno=aluno, aula=aula)
            presenca.ip_registrado = validator.ip
            presenca.latitude = latitude
            presenca.longitude = longitude
            presenca.status = Presenca.Status.NEGADO
            presenca.motivo_negacao = '; '.join(validator.errors)
            presenca.validado_rede = validator.validado_rede
            presenca.validado_geo = validator.validado_geo
            presenca.horario_registro = timezone.now()
            presenca.save()
        except Presenca.DoesNotExist:
            Presenca.objects.create(
                aluno=aluno,
                aula=aula,
                ip_registrado=validator.ip,
                latitude=latitude,
                longitude=longitude,
                status=Presenca.Status.NEGADO,
                motivo_negacao='; '.join(validator.errors),
                validado_rede=validator.validado_rede,
                validado_geo=validator.validado_geo,
            )
        log_action(user, 'PRESENÇA_NEGADA', '; '.join(validator.errors), request)
        return JsonResponse({
            'success': False,
            'error': 'Presença não registrada.',
            'errors': validator.errors
        }, status=403)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint assíncrono via Celery + RabbitMQ
# ─────────────────────────────────────────────────────────────────────────────
@login_required
@require_http_methods(["POST"])
def registrar_presenca_async(request):
    """
    Dispara registrar_presenca_task no Celery (broker=RabbitMQ) e retorna
    imediatamente com o task_id para polling posterior.
    """
    from apps.attendance.tasks import registrar_presenca_task

    if not request.user.is_student:
        return JsonResponse({'success': False, 'error': 'Somente alunos podem registrar presença.'}, status=403)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Dados inválidos.'}, status=400)

    aula_id = data.get('aula_id')
    token = data.get('token')
    latitude = data.get('latitude')
    longitude = data.get('longitude')

    if not all([aula_id, token, latitude, longitude]):
        return JsonResponse({'success': False, 'error': 'Parâmetros incompletos.'}, status=400)

    ip = get_client_ip(request)
    aluno = request.user.student_profile

    task = registrar_presenca_task.delay(
        aluno_id=aluno.id,
        aula_id=int(aula_id),
        latitude=float(latitude),
        longitude=float(longitude),
        ip=ip,
        token=token,
    )
    logger.info(f"[async] Task disparada: {task.id} | aluno={aluno.id} aula={aula_id}")

    return JsonResponse({
        'status': 'processing',
        'message': 'Presença sendo processada...',
        'task_id': task.id,
    }, status=202)


@login_required
@require_GET
def presenca_task_status(request, task_id):
    """
    Retorna o estado atual de uma task de registro de presença.
    Frontend usa polling neste endpoint.
    """
    from celery.result import AsyncResult
    result = AsyncResult(task_id)

    response = {'task_id': task_id, 'state': result.state}
    if result.ready():
        response['result'] = result.result if not isinstance(result.result, Exception) else str(result.result)
    return JsonResponse(response)
