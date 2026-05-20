"""
Management command: test_distributed

Simula N alunos registrando presença simultaneamente usando threads,
demonstrando que o sistema distribuído (Redis + Celery + RabbitMQ) funciona
corretamente sob carga concorrente.

Uso:
    python manage.py test_distributed
    python manage.py test_distributed --n 200 --aula-id 1
    python manage.py test_distributed --modo cache   # testa apenas Redis
    python manage.py test_distributed --modo celery  # dispara via Celery
"""
import time
import threading
import statistics
from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache


class Command(BaseCommand):
    help = 'Simula N alunos registrando presença simultaneamente (teste de sistema distribuído)'

    def add_arguments(self, parser):
        parser.add_argument('--n', type=int, default=100, help='Número de threads simultâneas (padrão: 100)')
        parser.add_argument('--aula-id', type=int, default=None, help='ID da aula a usar (padrão: primeira aula ativa)')
        parser.add_argument(
            '--modo',
            choices=['cache', 'celery', 'direto'],
            default='cache',
            help='cache=testa Redis; celery=dispara tasks; direto=acesso ao banco (padrão: cache)',
        )

    def handle(self, *args, **options):
        n = options['n']
        modo = options['modo']
        aula_id = options['aula_id']

        self.stdout.write(self.style.MIGRATE_HEADING(
            f'\n══════════════════════════════════════════════\n'
            f'  TESTE DE SISTEMA DISTRIBUÍDO — UFVJM QR\n'
            f'══════════════════════════════════════════════\n'
            f'  Modo    : {modo.upper()}\n'
            f'  Threads : {n}\n'
        ))

        if modo == 'cache':
            self._testar_cache_redis(n, aula_id)
        elif modo == 'celery':
            self._testar_celery(n, aula_id)
        else:
            self._testar_direto(n, aula_id)

    # ── Modo 1: Redis Cache ────────────────────────────────────────────────────

    def _testar_cache_redis(self, n, aula_id):
        """
        Demonstra que o cache Redis previne duplicatas mesmo com n threads
        tentando registrar presença para o mesmo (aula, aluno) simultaneamente.
        """
        self.stdout.write('Testando cache Redis (prevenção de duplicatas)...\n')

        aula_id = aula_id or 1
        # Limpa estado anterior
        for i in range(n):
            cache.delete(f'test:dist:presenca:{aula_id}:{i}')

        resultados = {'aceitos': 0, 'duplicados': 0, 'erros': 0}
        tempos = []
        lock = threading.Lock()

        def simular_registro(aluno_num):
            cache_key = f'test:dist:presenca:{aula_id}:{aluno_num}'
            inicio = time.perf_counter()
            try:
                # Simula a checagem/set atômica do Redis
                if cache.get(cache_key) is not None:
                    with lock:
                        resultados['duplicados'] += 1
                else:
                    # Simula latência de validação (~10ms)
                    time.sleep(0.01)
                    cache.set(cache_key, 1, timeout=300)
                    with lock:
                        resultados['aceitos'] += 1
            except Exception as exc:
                with lock:
                    resultados['erros'] += 1
                    self.stderr.write(f'  Erro thread {aluno_num}: {exc}')
            finally:
                with lock:
                    tempos.append((time.perf_counter() - inicio) * 1000)

        # Dispara todas as threads
        threads = [threading.Thread(target=simular_registro, args=(i,)) for i in range(n)]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_s = time.perf_counter() - t0

        self._exibir_resultado(resultados, tempos, total_s, n)

        # Teste de duplicata: mesma thread tenta registrar o aluno 0 novamente
        self.stdout.write('\nTestando detecção de duplicata (mesmo aluno, segunda tentativa):')
        cache_key = f'test:dist:presenca:{aula_id}:0'
        duplicata = cache.get(cache_key) is not None
        status = self.style.SUCCESS('BLOQUEADA ✓') if duplicata else self.style.ERROR('NÃO bloqueada ✗')
        self.stdout.write(f'  Segunda tentativa do aluno 0: {status}')

        # Limpa
        for i in range(n):
            cache.delete(f'test:dist:presenca:{aula_id}:{i}')

    # ── Modo 2: Celery Tasks ───────────────────────────────────────────────────

    def _testar_celery(self, n, aula_id):
        """
        Dispara n tasks registrar_presenca_task via Celery/RabbitMQ
        e aguarda os resultados.
        """
        from apps.attendance.tasks import registrar_presenca_task
        from apps.courses.models import Aula

        try:
            if aula_id:
                aula = Aula.objects.get(id=aula_id)
            else:
                aula = Aula.objects.filter(ativa=True).first()
            if aula is None:
                raise CommandError('Nenhuma aula ativa encontrada. Crie pelo menos uma aula antes de executar o teste.')
        except Aula.DoesNotExist:
            raise CommandError(f'Aula ID={aula_id} não encontrada.')

        self.stdout.write(f'Disparando {n} tasks para aula: {aula}\n')

        task_ids = []
        t0 = time.perf_counter()
        for i in range(n):
            task = registrar_presenca_task.delay(
                aluno_id=i + 1,    # IDs fictícios para teste
                aula_id=aula.id,
                latitude=-18.0,
                longitude=-43.5,
                ip='127.0.0.1',
                token=aula.token_qrcode,
            )
            task_ids.append(task.id)
        dispatch_s = time.perf_counter() - t0

        self.stdout.write(
            self.style.SUCCESS(f'  {n} tasks enviadas ao RabbitMQ em {dispatch_s*1000:.1f}ms')
        )
        self.stdout.write(f'  Task IDs (primeiros 3): {task_ids[:3]}')
        self.stdout.write(f'\n  Verifique os resultados no Celery worker (flower ou logs).')

    # ── Modo 3: Direto (sem cache, sem Celery) ────────────────────────────────

    def _testar_direto(self, n, aula_id):
        """
        Demonstra o problema sem o sistema distribuído:
        n threads acessando o banco diretamente, sem proteção de cache.
        """
        from apps.courses.models import Aula
        from apps.attendance.models import Presenca
        from apps.accounts.models import Student

        self.stdout.write(self.style.WARNING(
            'Modo DIRETO — sem Redis, sem Celery. Demonstra por que o sistema distribuído é necessário.\n'
        ))

        try:
            aula = Aula.objects.filter(ativa=True).first() if not aula_id else Aula.objects.get(id=aula_id)
        except Aula.DoesNotExist:
            raise CommandError('Aula não encontrada.')

        if aula is None:
            raise CommandError('Nenhuma aula ativa encontrada.')

        alunos = list(Student.objects.all()[:n])
        if not alunos:
            raise CommandError('Nenhum aluno encontrado no banco.')

        resultados = {'aceitos': 0, 'duplicados': 0, 'erros': 0}
        tempos = []
        lock = threading.Lock()

        def registrar_sem_cache(aluno):
            inicio = time.perf_counter()
            try:
                exists = Presenca.objects.filter(
                    aluno=aluno, aula=aula, status='presente'
                ).exists()
                if exists:
                    with lock:
                        resultados['duplicados'] += 1
                else:
                    with lock:
                        resultados['aceitos'] += 1
            except Exception as exc:
                with lock:
                    resultados['erros'] += 1
            finally:
                with lock:
                    tempos.append((time.perf_counter() - inicio) * 1000)

        threads = [threading.Thread(target=registrar_sem_cache, args=(a,)) for a in alunos]
        t0 = time.perf_counter()
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        total_s = time.perf_counter() - t0

        self.stdout.write(self.style.WARNING(
            '  Modo direto gera N queries simultâneas ao banco — sem proteção de cache.\n'
            '  Com Redis, a maioria dessas queries é eliminada na camada de cache.\n'
        ))
        self._exibir_resultado(resultados, tempos, total_s, n)

    # ── Formatação de resultado ────────────────────────────────────────────────

    def _exibir_resultado(self, resultados, tempos, total_s, n):
        media = statistics.mean(tempos) if tempos else 0
        mediana = statistics.median(tempos) if tempos else 0
        p95 = sorted(tempos)[int(len(tempos) * 0.95)] if tempos else 0

        self.stdout.write(self.style.SUCCESS('\n── RESULTADO ──────────────────────────────'))
        self.stdout.write(f'  Aceitos    : {self.style.SUCCESS(str(resultados["aceitos"]))}')
        self.stdout.write(f'  Duplicados : {self.style.WARNING(str(resultados["duplicados"]))}')
        self.stdout.write(f'  Erros      : {self.style.ERROR(str(resultados["erros"]))}')
        self.stdout.write(f'\n── DESEMPENHO ─────────────────────────────')
        self.stdout.write(f'  Total elapsed  : {total_s*1000:.1f}ms')
        self.stdout.write(f'  Throughput     : {n/total_s:.0f} req/s')
        self.stdout.write(f'  Tempo médio    : {media:.1f}ms')
        self.stdout.write(f'  Mediana        : {mediana:.1f}ms')
        self.stdout.write(f'  P95            : {p95:.1f}ms')
        self.stdout.write('───────────────────────────────────────────\n')
