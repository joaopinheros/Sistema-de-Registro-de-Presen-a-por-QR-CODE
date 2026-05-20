"""
Celery tasks para o sistema de frequência.

Broker : RabbitMQ  (CELERY_BROKER_URL)
Backend: Redis     (CELERY_RESULT_BACKEND)
"""
from celery import shared_task
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Task 1 — Registro de presença assíncrono
# ─────────────────────────────────────────────────────────────────────────────
@shared_task(bind=True, max_retries=3, name='attendance.registrar_presenca')
def registrar_presenca_task(self, aluno_id, aula_id, latitude, longitude, ip, token):
    """
    Executa todas as validações e cria o registro de Presença de forma
    assíncrona, consumindo mensagens da fila RabbitMQ.

    Em caso de erro transitório, retenta até 3 vezes com intervalo de 5s.
    """
    from django.core.cache import cache
    from django.utils import timezone
    from apps.attendance.models import Presenca
    from apps.courses.models import Aula
    from apps.accounts.models import Student
    from apps.attendance.validators import (
        validate_aula_token,
        validate_aula_schedule,
        validate_university_network,
        validate_geolocation,
        checar_presenca_cache,
        marcar_presenca_cache,
    )

    try:
        # 0. Verificar cache Redis antes de qualquer query
        if checar_presenca_cache(aula_id, aluno_id):
            logger.info(f"[task] Duplicata bloqueada por Redis: aluno={aluno_id} aula={aula_id}")
            return {'status': 'duplicado', 'message': 'Presença já registrada (cache Redis).'}

        aluno = Student.objects.get(id=aluno_id)
        aula = Aula.objects.select_related('sala').get(id=aula_id, ativa=True)

        # 0b. Verificar banco de dados
        if Presenca.objects.filter(
            aluno=aluno, aula=aula, status=Presenca.Status.PRESENTE
        ).exists():
            marcar_presenca_cache(aula_id, aluno_id)
            return {'status': 'duplicado', 'message': 'Presença já registrada (banco).'}

        # 1. Validar token QR (Redis → DB)
        if not validate_aula_token(aula, token):
            return {'status': 'erro', 'message': 'Token inválido ou QR Code expirado.'}

        # 2. Validar horário
        ok, msg = validate_aula_schedule(aula)
        if not ok:
            return {'status': 'erro', 'message': msg}

        # 3. Validar rede universitária
        validado_rede = validate_university_network(ip)
        if not validado_rede:
            errors = [f'IP não autorizado: {ip}']
            Presenca.objects.update_or_create(
                aluno=aluno, aula=aula,
                defaults={
                    'ip_registrado': ip, 'latitude': latitude, 'longitude': longitude,
                    'status': Presenca.Status.NEGADO,
                    'motivo_negacao': '; '.join(errors),
                    'validado_rede': False, 'validado_geo': False,
                }
            )
            registrar_auditoria_task.delay(
                aluno.user_id, 'PRESENÇA_NEGADA', '; '.join(errors)
            )
            return {'status': 'negado', 'message': errors[0]}

        # 4. Validar geolocalização
        geo_ref = aula if aula.latitude is not None else aula.sala
        validado_geo, distance = validate_geolocation(latitude, longitude, geo_ref)
        if not validado_geo:
            msg = f'Fora do raio permitido ({geo_ref.raio_permitido}m). Distância: {distance:.0f}m.'
            Presenca.objects.update_or_create(
                aluno=aluno, aula=aula,
                defaults={
                    'ip_registrado': ip, 'latitude': latitude, 'longitude': longitude,
                    'status': Presenca.Status.NEGADO,
                    'motivo_negacao': msg,
                    'validado_rede': True, 'validado_geo': False,
                }
            )
            registrar_auditoria_task.delay(aluno.user_id, 'PRESENÇA_NEGADA', msg)
            return {'status': 'negado', 'message': msg}

        # 5. Criar/atualizar presença
        presenca, created = Presenca.objects.update_or_create(
            aluno=aluno, aula=aula,
            defaults={
                'ip_registrado': ip,
                'latitude': latitude,
                'longitude': longitude,
                'status': Presenca.Status.PRESENTE,
                'motivo_negacao': '',
                'validado_rede': True,
                'validado_geo': True,
                'horario_registro': timezone.now(),
            }
        )

        # 6. Marcar no Redis (previne duplicatas futuras)
        marcar_presenca_cache(aula_id, aluno_id)

        # 7. Auditoria assíncrona
        registrar_auditoria_task.delay(
            aluno.user_id, 'PRESENÇA_REGISTRADA',
            f'Aula {aula_id} | task={self.request.id}'
        )

        logger.info(f"[task] Presença {'criada' if created else 'atualizada'}: aluno={aluno_id} aula={aula_id}")
        return {'status': 'sucesso', 'presenca_id': presenca.id, 'criada': created}

    except (Student.DoesNotExist, Aula.DoesNotExist) as exc:
        logger.error(f"[task] Objeto não encontrado: {exc}")
        return {'status': 'erro', 'message': str(exc)}
    except Exception as exc:
        logger.error(f"[task] Erro inesperado, tentativa {self.request.retries + 1}: {exc}")
        raise self.retry(exc=exc, countdown=5)


# ─────────────────────────────────────────────────────────────────────────────
# Task 2 — Registro de auditoria assíncrono
# ─────────────────────────────────────────────────────────────────────────────
@shared_task(name='audit.registrar_auditoria')
def registrar_auditoria_task(user_id, acao, detalhes):
    """
    Cria um registro no AuditLog de forma assíncrona para não bloquear
    a requisição principal.
    """
    from apps.audit.models import AuditLog
    from apps.accounts.models import User
    try:
        user = User.objects.get(id=user_id) if user_id else None
        AuditLog.objects.create(
            usuario=user,
            acao=acao,
            detalhe=detalhes,
        )
        logger.info(f"[task] Auditoria registrada: {acao} | user={user_id}")
    except Exception as exc:
        logger.error(f"[task] Erro ao registrar auditoria: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# Task 3 — Relatório de frequência por disciplina
# ─────────────────────────────────────────────────────────────────────────────
@shared_task(name='reports.gerar_relatorio_frequencia')
def gerar_relatorio_frequencia_task(disciplina_id):
    """
    Calcula frequência de cada aluno em uma disciplina.
    Retorna dict com resultado — pode ser encaminhado por email futuramente.
    """
    from apps.courses.models import Disciplina
    from apps.attendance.models import Presenca
    from django.db.models import Count, Q

    try:
        disc = Disciplina.objects.prefetch_related('alunos__user', 'aulas').get(id=disciplina_id)
        total_aulas = disc.aulas.count()

        relatorio = {
            'disciplina': disc.nome,
            'codigo': disc.codigo,
            'total_aulas': total_aulas,
            'alunos': [],
        }

        for aluno in disc.alunos.select_related('user').all():
            presencas = Presenca.objects.filter(
                aluno=aluno, aula__disciplina=disc, status='presente'
            ).count()
            percentual = round(presencas / total_aulas * 100, 1) if total_aulas > 0 else 0.0
            relatorio['alunos'].append({
                'nome': aluno.user.get_full_name(),
                'matricula': aluno.matricula,
                'presencas': presencas,
                'total_aulas': total_aulas,
                'percentual': percentual,
                'aprovado': percentual >= 75.0,
            })

        relatorio['alunos'].sort(key=lambda x: x['percentual'], reverse=True)
        logger.info(f"[task] Relatório gerado para disciplina {disciplina_id}: {len(relatorio['alunos'])} alunos")
        return relatorio

    except Disciplina.DoesNotExist:
        return {'erro': f'Disciplina {disciplina_id} não encontrada.'}
    except Exception as exc:
        logger.error(f"[task] Erro ao gerar relatório: {exc}")
        return {'erro': str(exc)}
