from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Count, Q


@login_required
def dashboard(request):
    user = request.user
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
