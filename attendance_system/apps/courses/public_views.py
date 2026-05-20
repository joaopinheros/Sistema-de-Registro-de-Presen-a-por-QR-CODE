from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET
from django.db.models import Count


@require_GET
@cache_page(60 * 5)
def public_disciplinas(request):
    from apps.courses.models import Disciplina
    qs = (
        Disciplina.objects
        .filter(ativa=True)
        .select_related('professor__user')
        .annotate(total_alunos=Count('alunos', distinct=True))
        .order_by('nome')
    )
    results = [
        {
            'id': d.id,
            'nome': d.nome,
            'codigo': d.codigo,
            'semestre': d.semestre,
            'professor': d.professor.user.get_full_name(),
            'total_alunos': d.total_alunos,
        }
        for d in qs
    ]
    return JsonResponse({'count': len(results), 'results': results})


@require_GET
@cache_page(60 * 5)
def public_professores(request):
    from apps.accounts.models import Professor
    qs = Professor.objects.select_related('user').order_by('user__first_name')
    results = [
        {
            'id': p.id,
            'nome': p.user.get_full_name(),
            'email': p.user.email,
            'departamento': p.departamento or '',
        }
        for p in qs
    ]
    return JsonResponse({'count': len(results), 'results': results})


@require_GET
@cache_page(60 * 5)
def public_aulas(request):
    from apps.courses.models import Aula
    qs = (
        Aula.objects
        .filter(ativa=True)
        .select_related('disciplina', 'sala')
        .order_by('-data', '-horario_inicio')[:200]
    )
    results = [
        {
            'id': a.id,
            'disciplina': a.disciplina.nome,
            'sala': a.sala.nome,
            'data': str(a.data),
            'horario_inicio': str(a.horario_inicio),
            'horario_fim': str(a.horario_fim),
        }
        for a in qs
    ]
    return JsonResponse({'count': len(results), 'results': results})
