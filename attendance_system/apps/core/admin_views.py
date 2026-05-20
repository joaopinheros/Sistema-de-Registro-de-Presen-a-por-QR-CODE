from functools import wraps
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods, require_POST, require_GET
from django.contrib.auth.hashers import make_password


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_admin:
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


# ─────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────

@admin_required
def painel_admin_dashboard(request):
    from apps.accounts.models import Student, Professor, User
    from apps.courses.models import Aula, Disciplina, Sala
    from apps.attendance.models import Presenca
    from apps.audit.models import AuditLog

    stats = {
        'usuarios': User.objects.count(),
        'alunos': Student.objects.count(),
        'professores': Professor.objects.count(),
        'disciplinas': Disciplina.objects.filter(ativa=True).count(),
        'salas': Sala.objects.filter(ativa=True).count(),
        'aulas_hoje': Aula.objects.filter(data=timezone.localdate()).count(),
        'presencas_hoje': Presenca.objects.filter(
            horario_registro__date=timezone.localdate()
        ).count(),
        'presencas_total': Presenca.objects.filter(status='presente').count(),
    }
    aulas_recentes = Aula.objects.select_related(
        'disciplina__professor__user', 'sala'
    ).order_by('-criada_em')[:8]
    audit_recente = AuditLog.objects.select_related('usuario').order_by('-timestamp')[:10]

    return render(request, 'admin_panel/dashboard.html', {
        'stats': stats,
        'aulas_recentes': aulas_recentes,
        'audit_recente': audit_recente,
    })


# ─────────────────────────────────────────
# USUÁRIOS
# ─────────────────────────────────────────

@admin_required
def painel_admin_usuarios(request):
    from apps.accounts.models import User

    if request.method == 'POST':
        action = request.POST.get('action', '')
        if action == 'deletar':
            return _deletar_usuario(request)
        return _criar_usuario(request)

    filtro = request.GET.get('role', '')
    q = request.GET.get('q', '').strip()

    usuarios = User.objects.all().order_by('first_name', 'last_name')
    if filtro:
        usuarios = usuarios.filter(role=filtro)
    if q:
        usuarios = usuarios.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
        )

    return render(request, 'admin_panel/usuarios.html', {
        'usuarios': usuarios,
        'total': usuarios.count(),
        'filtro': filtro,
        'q': q,
    })


def _criar_usuario(request):
    from apps.accounts.models import User, Student, Professor
    from apps.accounts.signals import create_profile
    from django.db.models.signals import post_save

    role = request.POST.get('role', '').strip()
    nome = request.POST.get('nome', '').strip()
    email = request.POST.get('email', '').strip().lower()
    senha = request.POST.get('senha', '').strip()

    if not all([role, nome, email, senha]):
        return JsonResponse({'success': False, 'error': 'Preencha todos os campos obrigatórios.'})

    if role not in ('aluno', 'professor', 'admin'):
        return JsonResponse({'success': False, 'error': 'Perfil inválido.'})

    if User.objects.filter(email=email).exists():
        return JsonResponse({'success': False, 'error': 'E-mail já cadastrado.'})

    partes = nome.split(' ', 1)
    first_name = partes[0]
    last_name = partes[1] if len(partes) > 1 else ''

    # Validate role-specific fields before touching the DB
    if role == 'aluno':
        matricula = request.POST.get('matricula', '').strip()
        curso = request.POST.get('curso', '').strip()
        if not matricula:
            return JsonResponse({'success': False, 'error': 'Matrícula é obrigatória.'})
        if not curso:
            return JsonResponse({'success': False, 'error': 'Curso é obrigatório.'})
        if User.objects.filter(username=matricula).exists():
            return JsonResponse({'success': False, 'error': 'Matrícula já cadastrada.'})
        if Student.objects.filter(matricula=matricula).exists():
            return JsonResponse({'success': False, 'error': 'Matrícula já cadastrada.'})
    elif role == 'professor':
        departamento = request.POST.get('departamento', '').strip()
        if not departamento:
            return JsonResponse({'success': False, 'error': 'Departamento é obrigatório para professores.'})

    try:
        # Disconnect signal so it doesn't create a bare Student/Professor with
        # empty matricula before we can populate the real values.
        post_save.disconnect(create_profile, sender=User)
        try:
            with transaction.atomic():
                if role == 'aluno':
                    user = User.objects.create(
                        username=matricula, email=email,
                        first_name=first_name, last_name=last_name,
                        role='aluno', password=make_password(senha),
                    )
                    Student.objects.create(user=user, matricula=matricula, curso=curso)

                elif role == 'professor':
                    user = User.objects.create(
                        username=email, email=email,
                        first_name=first_name, last_name=last_name,
                        role='professor', password=make_password(senha),
                    )
                    Professor.objects.create(user=user, departamento=departamento)

                else:  # admin
                    user = User.objects.create(
                        username=email, email=email,
                        first_name=first_name, last_name=last_name,
                        role='admin', is_staff=True, password=make_password(senha),
                    )
        finally:
            post_save.connect(create_profile, sender=User)

        return JsonResponse({
            'success': True,
            'message': f'Usuário {nome} criado com sucesso!',
            'usuario': {
                'id': user.id,
                'nome': user.get_full_name(),
                'email': user.email,
                'role': user.role,
                'role_display': user.get_role_display(),
                'ativo': user.is_active,
                'data_cadastro': user.date_joined.strftime('%d/%m/%Y'),
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Erro ao criar usuário: {e}'})


def _deletar_usuario(request):
    from apps.accounts.models import User

    user_id = request.POST.get('user_id', '').strip()
    if not user_id:
        return JsonResponse({'success': False, 'error': 'ID do usuário não informado.'})

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Usuário não encontrado.'})

    if user == request.user:
        return JsonResponse({'success': False, 'error': 'Você não pode remover sua própria conta.'})

    nome = user.get_full_name() or user.username
    user.delete()
    return JsonResponse({'success': True, 'message': f'Usuário "{nome}" removido com sucesso!'})


# ─────────────────────────────────────────
# SALAS
# ─────────────────────────────────────────

@admin_required
def painel_admin_salas(request):
    from apps.courses.models import Sala

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'criar':
            return _criar_sala(request)

        if action == 'toggle_ativa':
            sala_id = request.POST.get('sala_id')
            sala = get_object_or_404(Sala, id=sala_id)
            sala.ativa = not sala.ativa
            sala.save()
            return JsonResponse({'success': True, 'ativa': sala.ativa})

        if action == 'deletar':
            return _deletar_sala(request)

    salas = Sala.objects.all().order_by('predio', 'nome')
    return render(request, 'admin_panel/salas.html', {
        'salas': salas,
        'total': salas.count(),
    })


def _criar_sala(request):
    from apps.courses.models import Sala

    nome = request.POST.get('nome', '').strip()
    predio = request.POST.get('predio', '').strip()
    capacidade = request.POST.get('capacidade', '40').strip()
    raio = request.POST.get('raio_permitido', '50').strip()

    if not nome or not predio:
        return JsonResponse({'success': False, 'error': 'Nome e prédio são obrigatórios.'})

    try:
        sala = Sala.objects.create(
            nome=nome,
            predio=predio,
            capacidade=int(capacidade) if capacidade else 40,
            raio_permitido=int(raio) if raio else 50,
            # latitude/longitude left NULL until GPS is captured when creating an aula
        )
        return JsonResponse({
            'success': True,
            'message': f'Sala "{nome}" criada com sucesso!',
            'sala': {
                'id': sala.id,
                'nome': sala.nome,
                'predio': sala.predio,
                'capacidade': sala.capacidade,
                'raio_permitido': sala.raio_permitido,
                'ativa': sala.ativa,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Erro ao criar sala: {e}'})


def _deletar_sala(request):
    from apps.courses.models import Sala, Aula

    sala_id = request.POST.get('sala_id')
    sala = get_object_or_404(Sala, id=sala_id)

    aulas_futuras = Aula.objects.filter(sala=sala, data__gte=timezone.localdate())
    if aulas_futuras.exists():
        return JsonResponse({
            'success': False,
            'error': f'Esta sala tem {aulas_futuras.count()} aula(s) futura(s) vinculada(s). Remova-as antes de deletar a sala.'
        })

    nome = sala.nome
    sala.delete()
    return JsonResponse({'success': True, 'message': f'Sala "{nome}" deletada com sucesso!'})


# ─────────────────────────────────────────
# DISCIPLINAS
# ─────────────────────────────────────────

@admin_required
def painel_admin_disciplinas(request):
    from apps.courses.models import Disciplina

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'criar':
            return _criar_disciplina(request)
        if action == 'toggle_ativa':
            disc_id = request.POST.get('disciplina_id')
            disc = get_object_or_404(Disciplina, id=disc_id)
            disc.ativa = not disc.ativa
            disc.save()
            return JsonResponse({'success': True, 'ativa': disc.ativa})
        if action == 'deletar':
            return _deletar_disciplina(request)

    from apps.accounts.models import Professor
    disciplinas = Disciplina.objects.select_related('professor__user').annotate(
        total_aulas=Count('aulas', distinct=True),
        total_alunos=Count('alunos', distinct=True),
        total_presencas=Count('aulas__presenças', distinct=True,
                              filter=Q(**{'aulas__presenças__status': 'presente'})),
    ).order_by('nome')
    professores = Professor.objects.select_related('user').order_by('user__first_name')

    return render(request, 'admin_panel/disciplinas.html', {
        'disciplinas': disciplinas,
        'total': disciplinas.count(),
        'professores': professores,
    })


def _criar_disciplina(request):
    from apps.courses.models import Disciplina
    from apps.accounts.models import Professor

    nome = request.POST.get('nome', '').strip()
    codigo = request.POST.get('codigo', '').strip().upper()
    professor_id = request.POST.get('professor', '').strip()
    semestre = request.POST.get('semestre', '').strip()
    ano = request.POST.get('ano', str(timezone.localdate().year)).strip()
    descricao = request.POST.get('descricao', '').strip()

    if not all([nome, codigo, professor_id, semestre]):
        return JsonResponse({'success': False, 'error': 'Nome, código, professor e semestre são obrigatórios.'})

    if Disciplina.objects.filter(codigo=codigo).exists():
        return JsonResponse({'success': False, 'error': f'Código "{codigo}" já está em uso.'})

    try:
        professor = Professor.objects.get(id=professor_id)
        disc = Disciplina.objects.create(
            nome=nome,
            codigo=codigo,
            professor=professor,
            semestre=semestre,
            ano=int(ano) if ano else timezone.localdate().year,
            descricao=descricao,
        )
        return JsonResponse({
            'success': True,
            'message': f'Disciplina "{nome}" criada com sucesso!',
            'disciplina': {
                'id': disc.id,
                'nome': disc.nome,
                'codigo': disc.codigo,
                'professor': professor.user.get_full_name(),
                'semestre': disc.semestre,
                'ano': disc.ano,
                'ativa': disc.ativa,
            }
        })
    except Professor.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Professor não encontrado.'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Erro ao criar disciplina: {e}'})


def _deletar_disciplina(request):
    from apps.courses.models import Disciplina, Aula

    disc_id = request.POST.get('disciplina_id')
    disc = get_object_or_404(Disciplina, id=disc_id)

    aulas_futuras = Aula.objects.filter(disciplina=disc, data__gte=timezone.localdate())
    if aulas_futuras.exists():
        return JsonResponse({
            'success': False,
            'error': f'Esta disciplina tem {aulas_futuras.count()} aula(s) futura(s). Remova-as antes de deletar.'
        })

    nome = disc.nome
    disc.delete()
    return JsonResponse({'success': True, 'message': f'Disciplina "{nome}" deletada com sucesso!'})


# ─────────────────────────────────────────
# VINCULAR ALUNOS (AJAX)
# ─────────────────────────────────────────

@admin_required
def painel_admin_vincular(request):
    from apps.courses.models import Disciplina
    disciplinas = Disciplina.objects.filter(ativa=True).select_related('professor__user').order_by('nome')
    return render(request, 'admin_panel/vincular_alunos.html', {'disciplinas': disciplinas})


@admin_required
def vincular_api(request):
    """AJAX API for vincular alunos operations."""
    from apps.courses.models import Disciplina
    from apps.accounts.models import Student

    action = request.GET.get('action') or request.POST.get('action')

    if action == 'enrolled':
        disc_id = request.GET.get('disciplina')
        if not disc_id:
            return JsonResponse({'error': 'disciplina é obrigatório'}, status=400)
        disc = get_object_or_404(Disciplina, id=disc_id)
        alunos = list(disc.alunos.select_related('user').order_by('user__first_name').values(
            'id', 'matricula', 'curso', 'user__first_name', 'user__last_name', 'user__email'
        ))
        for a in alunos:
            a['nome'] = f"{a.pop('user__first_name')} {a.pop('user__last_name')}".strip()
            a['email'] = a.pop('user__email')
        return JsonResponse({'alunos': alunos, 'disciplina': {'id': disc.id, 'nome': disc.nome, 'codigo': disc.codigo}})

    if action == 'buscar':
        q = request.GET.get('q', '').strip()
        disc_id = request.GET.get('disciplina')
        enrolled_ids = set()
        if disc_id:
            try:
                disc = Disciplina.objects.get(id=disc_id)
                enrolled_ids = set(disc.alunos.values_list('id', flat=True))
            except Disciplina.DoesNotExist:
                pass
        alunos = Student.objects.select_related('user').filter(
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(matricula__icontains=q)
        ).order_by('user__first_name')[:20]
        data = [{
            'id': a.id,
            'nome': a.user.get_full_name(),
            'matricula': a.matricula,
            'curso': a.curso,
            'enrolled': a.id in enrolled_ids,
        } for a in alunos]
        return JsonResponse({'alunos': data})

    if request.method == 'POST':
        disc_id = request.POST.get('disciplina')
        aluno_id = request.POST.get('aluno')
        disc = get_object_or_404(Disciplina, id=disc_id)
        aluno = get_object_or_404(Student, id=aluno_id)

        if action == 'adicionar':
            disc.alunos.add(aluno)
            return JsonResponse({'success': True, 'message': f'{aluno.user.get_full_name()} adicionado à disciplina.'})

        if action == 'remover':
            disc.alunos.remove(aluno)
            return JsonResponse({'success': True, 'message': f'{aluno.user.get_full_name()} removido da disciplina.'})

    return JsonResponse({'error': 'Ação inválida'}, status=400)


# ─────────────────────────────────────────
# RELATÓRIOS
# ─────────────────────────────────────────

@admin_required
def painel_admin_relatorios(request):
    from apps.courses.models import Disciplina
    from apps.attendance.models import Presenca

    disciplinas = Disciplina.objects.filter(ativa=True).select_related(
        'professor__user'
    ).annotate(
        total_aulas=Count('aulas'),
        total_presentes=Count('aulas__presenças', filter=Q(**{'aulas__presenças__status': 'presente'})),
        total_negados=Count('aulas__presenças', filter=Q(**{'aulas__presenças__status': 'negado'})),
    ).order_by('nome')

    presencas_recentes = Presenca.objects.select_related(
        'aluno__user', 'aula__disciplina', 'aula__sala'
    ).order_by('-horario_registro')[:20]

    return render(request, 'admin_panel/relatorios.html', {
        'disciplinas': disciplinas,
        'presencas_recentes': presencas_recentes,
    })


# ─────────────────────────────────────────
# DISCIPLINAS — APIs de detalhe
# ─────────────────────────────────────────

@admin_required
def disciplina_alunos_api(request, disc_id):
    from apps.courses.models import Disciplina
    disc = get_object_or_404(Disciplina, id=disc_id)
    rows = disc.alunos.select_related('user').order_by('user__first_name').values(
        'matricula', 'curso', 'user__first_name', 'user__last_name'
    )
    alunos = [{'nome': f"{r['user__first_name']} {r['user__last_name']}".strip(),
               'matricula': r['matricula'], 'curso': r['curso'] or ''} for r in rows]
    return JsonResponse({'alunos': alunos, 'disciplina': disc.nome, 'total': len(alunos)})


@admin_required
def disciplina_presencas_api(request, disc_id):
    from apps.courses.models import Disciplina
    from apps.attendance.models import Presenca
    disc = get_object_or_404(Disciplina, id=disc_id)
    qs = Presenca.objects.filter(
        aula__disciplina=disc, status='presente'
    ).select_related('aluno__user', 'aula').order_by('-aula__data', '-horario_registro')
    data = [{
        'aluno': p.aluno.user.get_full_name(),
        'matricula': p.aluno.matricula,
        'aula_data': p.aula.data.strftime('%d/%m/%Y'),
        'aula_hora': p.aula.horario_inicio.strftime('%H:%M'),
        'horario': p.horario_registro.strftime('%d/%m/%Y %H:%M'),
    } for p in qs]
    return JsonResponse({'presencas': data, 'disciplina': disc.nome, 'total': len(data)})


# ─────────────────────────────────────────
# EDIÇÃO — USUÁRIOS
# ─────────────────────────────────────────

@admin_required
def editar_usuario(request, user_id):
    from apps.accounts.models import User, Student, Professor
    user = get_object_or_404(User, id=user_id)

    if request.method == 'GET':
        data = {
            'id': user.id,
            'nome': user.get_full_name(),
            'email': user.email,
            'role': user.role,
            'is_active': user.is_active,
        }
        if user.role == 'aluno':
            try:
                s = user.student_profile
                data['matricula'] = s.matricula
                data['curso'] = s.curso or ''
            except Exception:
                data['matricula'] = ''
                data['curso'] = ''
        elif user.role == 'professor':
            try:
                data['departamento'] = user.professor_profile.departamento or ''
            except Exception:
                data['departamento'] = ''
        return JsonResponse(data)

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        email = request.POST.get('email', '').strip().lower()
        is_active = request.POST.get('is_active') == '1'
        senha = request.POST.get('senha', '').strip()

        if not nome or not email:
            return JsonResponse({'success': False, 'error': 'Nome e e-mail são obrigatórios.'})
        if User.objects.filter(email=email).exclude(id=user.id).exists():
            return JsonResponse({'success': False, 'error': 'E-mail já está em uso por outro usuário.'})

        partes = nome.split(' ', 1)
        try:
            with transaction.atomic():
                user.first_name = partes[0]
                user.last_name = partes[1] if len(partes) > 1 else ''
                user.email = email
                user.is_active = is_active
                if senha:
                    user.password = make_password(senha)
                user.save()

                if user.role == 'aluno':
                    matricula = request.POST.get('matricula', '').strip()
                    curso = request.POST.get('curso', '').strip()
                    if not matricula:
                        return JsonResponse({'success': False, 'error': 'Matrícula é obrigatória.'})
                    if Student.objects.filter(matricula=matricula).exclude(user=user).exists():
                        return JsonResponse({'success': False, 'error': 'Matrícula já cadastrada por outro aluno.'})
                    s = user.student_profile
                    s.matricula = matricula
                    s.curso = curso
                    s.save()
                elif user.role == 'professor':
                    departamento = request.POST.get('departamento', '').strip()
                    if not departamento:
                        return JsonResponse({'success': False, 'error': 'Departamento é obrigatório.'})
                    p = user.professor_profile
                    p.departamento = departamento
                    p.save()

            return JsonResponse({'success': True, 'message': 'Alterações salvas com sucesso!',
                                 'usuario': {'id': user.id, 'nome': user.get_full_name(),
                                             'email': user.email, 'is_active': user.is_active}})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'error': 'Método não permitido.'}, status=405)


# ─────────────────────────────────────────
# EDIÇÃO — SALAS
# ─────────────────────────────────────────

@admin_required
def editar_sala(request, sala_id):
    from apps.courses.models import Sala
    sala = get_object_or_404(Sala, id=sala_id)

    if request.method == 'GET':
        return JsonResponse({
            'id': sala.id, 'nome': sala.nome,
            'predio': sala.predio, 'raio_permitido': sala.raio_permitido,
        })

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        predio = request.POST.get('predio', '').strip()
        raio = request.POST.get('raio_permitido', '').strip()
        if not nome or not predio:
            return JsonResponse({'success': False, 'error': 'Nome e prédio são obrigatórios.'})
        try:
            sala.nome = nome
            sala.predio = predio
            if raio:
                sala.raio_permitido = int(raio)
            sala.save()
            return JsonResponse({'success': True, 'message': f'Sala "{nome}" atualizada com sucesso!',
                                 'sala': {'id': sala.id, 'nome': sala.nome,
                                          'predio': sala.predio, 'raio_permitido': sala.raio_permitido}})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'error': 'Método não permitido.'}, status=405)


# ─────────────────────────────────────────
# EDIÇÃO — DISCIPLINAS
# ─────────────────────────────────────────

@admin_required
def editar_disciplina(request, disc_id):
    from apps.courses.models import Disciplina
    from apps.accounts.models import Professor
    disc = get_object_or_404(Disciplina, id=disc_id)

    if request.method == 'GET':
        return JsonResponse({
            'id': disc.id, 'nome': disc.nome, 'codigo': disc.codigo,
            'professor_id': disc.professor.id,
            'semestre': disc.semestre, 'ano': disc.ano,
            'descricao': disc.descricao or '',
        })

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        codigo = request.POST.get('codigo', '').strip().upper()
        professor_id = request.POST.get('professor', '').strip()
        semestre = request.POST.get('semestre', '').strip()
        ano = request.POST.get('ano', '').strip()

        if not all([nome, codigo, professor_id, semestre]):
            return JsonResponse({'success': False, 'error': 'Nome, código, professor e semestre são obrigatórios.'})
        if Disciplina.objects.filter(codigo=codigo).exclude(id=disc.id).exists():
            return JsonResponse({'success': False, 'error': f'Código "{codigo}" já está em uso por outra disciplina.'})
        try:
            professor = Professor.objects.get(id=professor_id)
            disc.nome = nome
            disc.codigo = codigo
            disc.professor = professor
            disc.semestre = semestre
            if ano:
                disc.ano = int(ano)
            disc.save()
            return JsonResponse({'success': True, 'message': 'Alterações salvas com sucesso!',
                                 'disciplina': {'id': disc.id, 'nome': disc.nome, 'codigo': disc.codigo,
                                                'professor': professor.user.get_full_name(),
                                                'semestre': disc.semestre, 'ano': disc.ano}})
        except Professor.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Professor não encontrado.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'error': 'Método não permitido.'}, status=405)


# ─────────────────────────────────────────
# DADOS PARA GRÁFICOS — Dashboard Admin
# ─────────────────────────────────────────

@admin_required
@require_GET
def dashboard_dados_graficos(request):
    from apps.accounts.models import Student, Professor, User
    from apps.courses.models import Disciplina
    from apps.attendance.models import Presenca

    # 1. Distribuição de usuários (pizza)
    admins_count = User.objects.filter(role='admin').count()
    profs_count = Professor.objects.count()
    alunos_count = Student.objects.count()

    # 2. Top 10 disciplinas com mais presenças (barras)
    top_disc = (
        Disciplina.objects
        .annotate(
            total_presencas=Count(
                'aulas__presenças', distinct=True,
                filter=Q(**{'aulas__presenças__status': 'presente'})
            )
        )
        .order_by('-total_presencas')[:10]
    )
    top_disciplinas = [
        {'nome': d.codigo, 'total': d.total_presencas}
        for d in top_disc
    ]

    # 3. Média geral de frequência
    disc_stats = (
        Disciplina.objects.filter(ativa=True)
        .annotate(
            total_aulas=Count('aulas', distinct=True),
            total_alunos=Count('alunos', distinct=True),
            total_presencas=Count(
                'aulas__presenças', distinct=True,
                filter=Q(**{'aulas__presenças__status': 'presente'})
            ),
        )
    )
    total_possivel = sum(d.total_aulas * d.total_alunos for d in disc_stats)
    total_presencas = sum(d.total_presencas for d in disc_stats)
    media_frequencia = round(total_presencas / total_possivel * 100, 1) if total_possivel > 0 else 0.0

    return JsonResponse({
        'distribuicao_usuarios': {
            'labels': ['Alunos', 'Professores', 'Admins'],
            'data': [alunos_count, profs_count, admins_count],
        },
        'top_disciplinas': {
            'labels': [d['nome'] for d in top_disciplinas],
            'data': [d['total'] for d in top_disciplinas],
        },
        'media_frequencia': media_frequencia,
    })
