from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Count, Q
from django.views.decorators.http import require_http_methods


@login_required
def dashboard(request):
    user = request.user

    # Role-based redirect to dedicated panels
    if user.is_admin:
        return redirect('/painel-admin/')
    if user.is_professor:
        return redirect('/painel-professor/')

    context = {'user': user}

    if user.is_student:
        from apps.attendance.models import Presenca
        presencas = Presenca.objects.filter(
            aluno__user=user
        ).select_related('aula__disciplina', 'aula__sala').order_by('-horario_registro')[:10]

        stats = Presenca.objects.filter(aluno__user=user).aggregate(
            total=Count('id'),
            presentes=Count('id', filter=Q(status='presente')),
            negadas=Count('id', filter=Q(status='negado')),
        )
        context.update({'presencas': presencas, 'stats': stats})

    elif user.is_professor:
        from apps.courses.models import Aula, Disciplina
        from apps.attendance.models import Presenca
        disciplinas = Disciplina.objects.filter(
            professor__user=user, ativa=True
        ).annotate(total_aulas=Count('aulas'))

        aulas_hoje = Aula.objects.filter(
            disciplina__professor__user=user,
            data=timezone.localdate()
        ).select_related('disciplina', 'sala')

        stats = {
            'disciplinas': disciplinas.count(),
            'aulas_hoje': aulas_hoje.count(),
            'total_presencas': Presenca.objects.filter(
                aula__disciplina__professor__user=user,
                status='presente'
            ).count(),
        }
        context.update({
            'disciplinas': disciplinas,
            'aulas_hoje': aulas_hoje,
            'stats': stats,
        })

    elif user.is_admin:
        from apps.accounts.models import Student, Professor
        from apps.courses.models import Aula, Disciplina
        from apps.attendance.models import Presenca

        stats = {
            'alunos': Student.objects.count(),
            'professores': Professor.objects.count(),
            'disciplinas': Disciplina.objects.filter(ativa=True).count(),
            'aulas_hoje': Aula.objects.filter(data=timezone.localdate()).count(),
            'presencas_hoje': Presenca.objects.filter(
                horario_registro__date=timezone.localdate()
            ).count(),
        }
        context['stats'] = stats

    return render(request, 'core/dashboard.html', context)


@login_required
def gerenciar_alunos(request):
    if not request.user.is_admin:
        return redirect('dashboard')
    
    from apps.accounts.models import Student
    
    alunos = Student.objects.select_related('user').all()
    
    context = {
        'alunos': alunos,
        'total': alunos.count(),
    }
    return render(request, 'core/gerenciar_alunos.html', context)


@login_required
def gerenciar_professores(request):
    if not request.user.is_admin:
        return redirect('dashboard')
    
    from apps.accounts.models import Professor
    
    professores = Professor.objects.select_related('user').all()
    
    context = {
        'professores': professores,
        'total': professores.count(),
    }
    return render(request, 'core/gerenciar_professores.html', context)


@login_required
def gerenciar_salas(request):
    if not request.user.is_admin:
        return redirect('dashboard')
    
    from apps.courses.models import Sala
    
    salas = Sala.objects.all()
    
    context = {
        'salas': salas,
        'total': salas.count(),
    }
    return render(request, 'core/gerenciar_salas.html', context)


@login_required
def gerenciar_disciplinas(request):
    if not (request.user.is_admin or request.user.is_professor):
        return redirect('dashboard')
    
    from apps.courses.models import Disciplina
    
    if request.user.is_admin:
        disciplinas = Disciplina.objects.select_related('professor__user').all()
    else:
        disciplinas = Disciplina.objects.filter(professor__user=request.user).select_related('professor__user')
    
    context = {
        'disciplinas': disciplinas,
        'total': disciplinas.count(),
    }
    return render(request, 'core/gerenciar_disciplinas.html', context)


@login_required
def gerenciar_aulas(request):
    if not (request.user.is_admin or request.user.is_professor):
        return redirect('dashboard')

    from apps.courses.models import Aula, Disciplina, Sala
    from apps.courses.services import QRCodeService
    from decimal import Decimal, InvalidOperation

    if request.user.is_admin:
        aulas = Aula.objects.select_related('disciplina__professor__user', 'sala').all()
        disciplinas = Disciplina.objects.filter(ativa=True).select_related('professor__user')
    else:
        aulas = Aula.objects.filter(
            disciplina__professor__user=request.user
        ).select_related('disciplina__professor__user', 'sala')
        disciplinas = Disciplina.objects.filter(
            professor__user=request.user, ativa=True
        ).select_related('professor__user')

    salas = Sala.objects.filter(ativa=True).order_by('predio', 'nome')

    if request.method == 'POST':
        action = request.POST.get('action', '')

        # ── Criar aula ──────────────────────────────────────────────
        if action == 'criar':
            errors = []
            disciplina_id  = request.POST.get('disciplina', '').strip()
            sala_id        = request.POST.get('sala', '').strip()
            data           = request.POST.get('data', '').strip()
            horario_inicio = request.POST.get('horario_inicio', '').strip()
            horario_fim    = request.POST.get('horario_fim', '').strip()
            descricao      = request.POST.get('descricao', '').strip()
            lat_raw        = request.POST.get('latitude', '').strip()
            lon_raw        = request.POST.get('longitude', '').strip()
            raio_raw       = request.POST.get('raio_permitido', '50').strip()

            latitude = longitude = None
            try:
                if lat_raw:
                    latitude = Decimal(lat_raw)
                if lon_raw:
                    longitude = Decimal(lon_raw)
            except InvalidOperation:
                errors.append('Coordenadas GPS inválidas.')

            try:
                raio_permitido = int(raio_raw) if raio_raw else 50
            except ValueError:
                raio_permitido = 50

            if not disciplina_id:
                errors.append('Selecione uma disciplina.')
            if not sala_id:
                errors.append('Selecione uma sala.')
            if not data:
                errors.append('Informe a data da aula.')
            if not horario_inicio or not horario_fim:
                errors.append('Informe os horários de início e fim.')
            if horario_inicio and horario_fim and horario_inicio >= horario_fim:
                errors.append('O horário de início deve ser anterior ao horário de fim.')

            if not errors:
                try:
                    disciplina = disciplinas.get(id=disciplina_id)
                    sala = salas.get(id=sala_id)
                    Aula.objects.create(
                        disciplina=disciplina,
                        sala=sala,
                        data=data,
                        horario_inicio=horario_inicio,
                        horario_fim=horario_fim,
                        latitude=latitude,
                        longitude=longitude,
                        raio_permitido=raio_permitido,
                        descricao=descricao,
                    )
                    return JsonResponse({'success': True, 'message': 'Aula criada com sucesso!'})
                except Disciplina.DoesNotExist:
                    errors.append('Disciplina não encontrada ou sem permissão.')
                except Sala.DoesNotExist:
                    errors.append('Sala não encontrada.')
                except Exception as e:
                    errors.append(f'Erro ao criar aula: {e}')

            return JsonResponse({'success': False, 'errors': errors})

        # ── Gerar QR Code (AJAX) ─────────────────────────────────────
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            aula_id = request.POST.get('aula_id')
            try:
                aula = aulas.get(id=aula_id)
                QRCodeService.generate(aula, request=request)
                aula.refresh_from_db()
                return JsonResponse({
                    'success': True,
                    'qrcode_url': aula.qrcode_imagem.url if aula.qrcode_imagem else None,
                    'message': 'QR Code gerado com sucesso!',
                })
            except Aula.DoesNotExist:
                return JsonResponse({'success': False, 'message': 'Aula não encontrada'}, status=404)
            except Exception as e:
                return JsonResponse({'success': False, 'message': str(e)}, status=500)

    context = {
        'aulas': aulas,
        'total': aulas.count(),
        'disciplinas': disciplinas,
        'salas': salas,
    }
    return render(request, 'core/gerenciar_aulas.html', context)


@login_required
def criar_aula(request):
    if not (request.user.is_admin or request.user.is_professor):
        return redirect('dashboard')

    from apps.courses.models import Aula, Disciplina, Sala
    from decimal import Decimal, InvalidOperation

    if request.user.is_admin:
        disciplinas = Disciplina.objects.select_related('professor__user').filter(ativa=True)
    else:
        disciplinas = Disciplina.objects.filter(
            professor__user=request.user, ativa=True
        ).select_related('professor__user')

    salas = Sala.objects.filter(ativa=True).order_by('predio', 'nome')

    errors = []

    if request.method == 'POST':
        disciplina_id = request.POST.get('disciplina')
        sala_id = request.POST.get('sala')
        data = request.POST.get('data')
        horario_inicio = request.POST.get('horario_inicio')
        horario_fim = request.POST.get('horario_fim')
        descricao = request.POST.get('descricao', '')
        lat_raw = request.POST.get('latitude', '').strip()
        lon_raw = request.POST.get('longitude', '').strip()
        raio_raw = request.POST.get('raio_permitido', '50').strip()

        latitude = None
        longitude = None
        try:
            if lat_raw:
                latitude = Decimal(lat_raw)
            if lon_raw:
                longitude = Decimal(lon_raw)
        except InvalidOperation:
            errors.append('Coordenadas GPS inválidas.')

        try:
            raio_permitido = int(raio_raw) if raio_raw else 50
        except ValueError:
            raio_permitido = 50

        if not disciplina_id:
            errors.append('Selecione uma disciplina.')
        if not sala_id:
            errors.append('Selecione uma sala.')
        if not data:
            errors.append('Informe a data da aula.')
        if not horario_inicio or not horario_fim:
            errors.append('Informe os horários de início e fim.')
        if horario_inicio and horario_fim and horario_inicio >= horario_fim:
            errors.append('O horário de início deve ser anterior ao horário de fim.')

        if not errors:
            try:
                disciplina = disciplinas.get(id=disciplina_id)
                sala = salas.get(id=sala_id)
                Aula.objects.create(
                    disciplina=disciplina,
                    sala=sala,
                    data=data,
                    horario_inicio=horario_inicio,
                    horario_fim=horario_fim,
                    latitude=latitude,
                    longitude=longitude,
                    raio_permitido=raio_permitido,
                    descricao=descricao,
                )
                return redirect('gerenciar_aulas')
            except Disciplina.DoesNotExist:
                errors.append('Disciplina não encontrada.')
            except Sala.DoesNotExist:
                errors.append('Sala não encontrada.')
            except Exception as e:
                errors.append(f'Erro ao criar aula: {e}')

    context = {
        'disciplinas': disciplinas,
        'salas': salas,
        'errors': errors,
        'post': request.POST if request.method == 'POST' else {},
    }
    return render(request, 'core/criar_aula.html', context)


@login_required
def gerenciar_presencas(request):
    from apps.attendance.models import Presenca
    
    if request.user.is_student:
        presencas = Presenca.objects.filter(aluno__user=request.user).select_related(
            'aula__disciplina', 'aula__sala', 'aluno__user'
        ).order_by('-horario_registro')
    elif request.user.is_professor:
        presencas = Presenca.objects.filter(
            aula__disciplina__professor__user=request.user
        ).select_related('aula__disciplina', 'aula__sala', 'aluno__user').order_by('-horario_registro')
    elif request.user.is_admin:
        presencas = Presenca.objects.select_related(
            'aula__disciplina', 'aula__sala', 'aluno__user'
        ).order_by('-horario_registro')
    else:
        return redirect('dashboard')
    
    context = {
        'presencas': presencas,
        'total': presencas.count(),
    }
    return render(request, 'core/gerenciar_presencas.html', context)