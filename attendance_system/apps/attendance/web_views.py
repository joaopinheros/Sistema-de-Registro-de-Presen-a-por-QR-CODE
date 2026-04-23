from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from apps.courses.models import Aula


@require_GET
def presenca_scan(request):
    """
    Landing page when a student scans a QR Code.
    URL: /presenca?id=<aula_id>&token=<token>
    """
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
        return redirect(f'/accounts/login/?next=/presenca?id={aula_id}&token={token}')

    return render(request, 'attendance/registrar.html', {
        'aula': aula,
        'token': token,
    })
