from functools import wraps
from django.shortcuts import render, redirect
from django.utils import timezone
from django.db.models import Count, Q
from django.http import JsonResponse
from django.views.decorators.http import require_GET


def professor_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not (request.user.is_professor or request.user.is_admin):
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def _disciplinas_do_professor(user):
    from apps.courses.models import Disciplina
    if user.is_admin:
        return Disciplina.objects.select_related('professor__user').filter(ativa=True)
    return Disciplina.objects.filter(
        professor__user=user, ativa=True
    ).select_related('professor__user')


@professor_required
def painel_professor_dashboard(request):
    from apps.courses.models import Aula
    from apps.attendance.models import Presenca

    disciplinas = _disciplinas_do_professor(request.user).annotate(
        total_aulas=Count('aulas'),
        total_alunos=Count('alunos'),
    )

    aulas_hoje = Aula.objects.filter(
        disciplina__in=disciplinas,
        data=timezone.localdate(),
    ).select_related('disciplina', 'sala').order_by('horario_inicio')

    presencas_recentes = Presenca.objects.filter(
        aula__disciplina__in=disciplinas,
        status='presente',
    ).select_related('aluno__user', 'aula__disciplina').order_by('-horario_registro')[:10]

    stats = {
        'disciplinas': disciplinas.count(),
        'aulas_hoje': aulas_hoje.count(),
        'total_presencas': Presenca.objects.filter(
            aula__disciplina__in=disciplinas, status='presente'
        ).count(),
    }

    return render(request, 'professor_panel/dashboard.html', {
        'disciplinas': disciplinas,
        'aulas_hoje': aulas_hoje,
        'presencas_recentes': presencas_recentes,
        'stats': stats,
    })


@professor_required
def painel_professor_aulas(request):
    from apps.courses.models import Aula

    disciplinas = _disciplinas_do_professor(request.user)
    filtro_disc = request.GET.get('disciplina', '')

    aulas = Aula.objects.filter(
        disciplina__in=disciplinas
    ).select_related('disciplina__professor__user', 'sala').order_by('-data', '-horario_inicio')

    if filtro_disc:
        aulas = aulas.filter(disciplina_id=filtro_disc)

    return render(request, 'professor_panel/minhas_aulas.html', {
        'aulas': aulas,
        'total': aulas.count(),
        'disciplinas': disciplinas,
        'filtro_disc': filtro_disc,
    })


@professor_required
def painel_professor_disciplinas(request):
    disciplinas = _disciplinas_do_professor(request.user).annotate(
        total_alunos=Count('alunos', distinct=True),
    )

    return render(request, 'professor_panel/minhas_disciplinas.html', {
        'disciplinas': disciplinas,
        'total': disciplinas.count(),
    })


@professor_required
def disciplina_alunos_api(request, disc_id):
    from apps.courses.models import Disciplina

    disc = Disciplina.objects.filter(id=disc_id).first()
    if not disc:
        return JsonResponse({'error': 'Disciplina não encontrada.'}, status=404)

    if not request.user.is_admin and disc.professor.user != request.user:
        return JsonResponse({'error': 'Acesso negado.'}, status=403)

    rows = disc.alunos.select_related('user').order_by('user__first_name').values(
        'matricula', 'curso', 'user__first_name', 'user__last_name'
    )
    alunos = [{'nome': f"{r['user__first_name']} {r['user__last_name']}".strip(),
               'matricula': r['matricula'], 'curso': r['curso'] or ''} for r in rows]
    return JsonResponse({'alunos': alunos, 'disciplina': disc.nome, 'total': len(alunos)})


@professor_required
def painel_professor_presencas(request):
    from apps.attendance.models import Presenca

    disciplinas = _disciplinas_do_professor(request.user)
    filtro_disc = request.GET.get('disciplina', '')
    filtro_status = request.GET.get('status', '')

    presencas = Presenca.objects.filter(
        aula__disciplina__in=disciplinas
    ).select_related(
        'aluno__user', 'aula__disciplina', 'aula__sala'
    ).order_by('-horario_registro')

    if filtro_disc:
        presencas = presencas.filter(aula__disciplina_id=filtro_disc)
    if filtro_status:
        presencas = presencas.filter(status=filtro_status)

    return render(request, 'professor_panel/presencas.html', {
        'presencas': presencas,
        'total': presencas.count(),
        'disciplinas': disciplinas,
        'filtro_disc': filtro_disc,
        'filtro_status': filtro_status,
    })


# ─────────────────────────────────────────
# DADOS PARA GRÁFICOS — Dashboard Professor
# ─────────────────────────────────────────

@professor_required
def dashboard_dados_graficos(request):
    from apps.attendance.models import Presenca
    from datetime import timedelta

    disciplinas = _disciplinas_do_professor(request.user)

    # 1. Presenças por disciplina — percentual (barras)
    disc_stats = disciplinas.annotate(
        total_aulas=Count('aulas', distinct=True),
        total_alunos=Count('alunos', distinct=True),
        total_presencas=Count(
            'aulas__presenças', distinct=True,
            filter=Q(**{'aulas__presenças__status': 'presente'})
        ),
    )
    presencas_por_disc = []
    for d in disc_stats:
        total_possivel = d.total_aulas * d.total_alunos
        perc = round(d.total_presencas / total_possivel * 100, 1) if total_possivel > 0 else 0.0
        presencas_por_disc.append({'nome': d.codigo, 'percentual': perc})

    # 2. Evolução semanal — últimas 4 semanas (linha)
    hoje = timezone.localdate()
    evolucao = []
    for i in range(3, -1, -1):
        fim = hoje - timedelta(weeks=i)
        inicio = fim - timedelta(days=6)
        count = Presenca.objects.filter(
            aula__disciplina__in=disciplinas,
            status='presente',
            horario_registro__date__gte=inicio,
            horario_registro__date__lte=fim,
        ).count()
        evolucao.append({'semana': inicio.strftime('%d/%m'), 'total': count})

    return JsonResponse({
        'presencas_por_disciplina': {
            'labels': [d['nome'] for d in presencas_por_disc],
            'data': [d['percentual'] for d in presencas_por_disc],
        },
        'evolucao_semanal': {
            'labels': [e['semana'] for e in evolucao],
            'data': [e['total'] for e in evolucao],
        },
    })
