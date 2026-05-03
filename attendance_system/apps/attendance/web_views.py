# apps/attendance/web_views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET, require_http_methods
from django.http import JsonResponse
from django.utils import timezone
from apps.courses.models import Aula
from apps.attendance.models import Presenca
from apps.attendance.validators import AttendanceValidator, get_client_ip
from apps.attendance.serializers import PresencaSerializer
from apps.audit.utils import log_action
import json


@require_GET
def presenca_scanner(request):
    return render(request, 'attendance/scanner_qr.html')


@require_GET
def presenca_scan(request):
    aula_id = request.GET.get('id')
    token = request.GET.get('token')

    if not aula_id or not token:
        return render(request, 'attendance/erro.html', {
            'mensagem': 'QR Code inválido. Parâmetros ausentes.'
        })

    aula = get_object_or_404(Aula, id=aula_id, ativa=True)

    if aula.token_qrcode != token:
        return render(request, 'attendance/erro.html', {
            'mensagem': 'QR Code inválido ou expirado.'
        })

    if not request.user.is_authenticated:
        return redirect(f'/accounts/login/?next=/presenca/registrar?id={aula_id}&token={token}')

    return render(request, 'attendance/registrar.html', {
        'aula': aula,
        'token': token,
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

    validator = AttendanceValidator(
        request=request,
        aula=aula,
        token=token,
        student_lat=float(latitude),
        student_lon=float(longitude),
    )

    if validator.run():
        try:
            presenca = Presenca.objects.get(aluno=user.student_profile, aula=aula)
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
                aluno=user.student_profile,
                aula=aula,
                ip_registrado=validator.ip,
                latitude=latitude,
                longitude=longitude,
                status=Presenca.Status.PRESENTE,
                validado_rede=validator.validado_rede,
                validado_geo=validator.validado_geo,
            )
        log_action(user, 'PRESENÇA_REGISTRADA', f'Aula ID {aula.id}', request)
        return JsonResponse({
            'success': True,
            'message': 'Presença registrada com sucesso!',
            'data': PresencaSerializer(presenca).data
        }, status=201)
    else:
        try:
            presenca = Presenca.objects.get(aluno=user.student_profile, aula=aula)
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
                aluno=user.student_profile,
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
