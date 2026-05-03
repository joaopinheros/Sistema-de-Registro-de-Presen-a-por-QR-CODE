"""
Management command: python manage.py seed_demo

Creates demo users, a classroom, discipline and a lesson for testing.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from apps.accounts.models import Student, Professor
from apps.courses.models import Sala, Disciplina, Aula
from datetime import date, time

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed database with demo data for development/testing'

    def handle(self, *args, **kwargs):
        self.stdout.write('🌱  Seeding demo data...')

        # ── Superuser / Admin ──
        admin_user, created = User.objects.get_or_create(
            email='admin@sistema.edu',
            defaults={
                'username': 'admin@sistema.edu',
                'first_name': 'Admin',
                'last_name': 'Sistema',
                'role': User.Role.ADMIN,
                'is_staff': True,
                'is_superuser': True,
            }
        )
        if created:
            admin_user.set_password('Admin@1234')
            admin_user.save()
            self.stdout.write(self.style.SUCCESS('  ✔ Admin criado: admin@sistema.edu / Admin@1234'))
        else:
            self.stdout.write('  → Admin já existe')

        # ── Professor ──
        # Signal já cria o Professor automaticamente ao criar o User
        prof_user, created = User.objects.get_or_create(
            email='prof@sistema.edu',
            defaults={
                'username': 'prof@sistema.edu',
                'first_name': 'Carlos',
                'last_name': 'Andrade',
                'role': User.Role.PROFESSOR,
            }
        )
        if created:
            prof_user.set_password('Prof@1234')
            prof_user.save()
            self.stdout.write(self.style.SUCCESS('  ✔ Professor criado: prof@sistema.edu / Prof@1234'))
        else:
            self.stdout.write('  → Professor já existe')

        # Garante que o perfil existe e atualiza departamento
        prof, _ = Professor.objects.get_or_create(user=prof_user)
        if not prof.departamento:
            prof.departamento = 'Ciência da Computação'
            prof.save()

        # ── Student ──
        # Signal já cria o Student automaticamente ao criar o User
        aluno_user, created = User.objects.get_or_create(
            email='aluno@sistema.edu',
            defaults={
                'username': 'aluno@sistema.edu',
                'first_name': 'Maria',
                'last_name': 'Silva',
                'role': User.Role.STUDENT,
            }
        )
        if created:
            aluno_user.set_password('Aluno@1234')
            aluno_user.save()
            self.stdout.write(self.style.SUCCESS('  ✔ Aluno criado: aluno@sistema.edu / Aluno@1234'))
        else:
            self.stdout.write('  → Aluno já existe')

        # Garante que o perfil existe e atualiza matrícula/curso
        aluno, _ = Student.objects.get_or_create(user=aluno_user)
        if not aluno.matricula:
            aluno.matricula = '2024001'
            aluno.curso = 'Ciência da Computação'
            aluno.save()

        # ── Sala ──
        sala, _ = Sala.objects.get_or_create(
            nome='Lab 101',
            defaults={
                'predio': 'Bloco A',
                'latitude': -18.20111283477218,
                'longitude': -43.57767167057169,
                'raio_permitido': 10000,
                'capacidade': 30,
    }
)
        # ── Disciplina ──
        disciplina, _ = Disciplina.objects.get_or_create(
            codigo='CC001',
            defaults={
                'nome': 'Sistemas Distribuídos',
                'professor': prof,
                'semestre': '5',
                'ano': date.today().year,
            }
        )

        # ── Aula (hoje) ──
        aula, created = Aula.objects.get_or_create(
            disciplina=disciplina,
            sala=sala,
            data=date.today(),
            defaults={
                'horario_inicio': time(8, 0),
                'horario_fim': time(23, 59),
                'descricao': 'Aula demo — criada pelo seed',
            }
        )
        if created:
            from apps.courses.services import QRCodeService
            try:
                QRCodeService.generate(aula)
            except Exception as e:
                self.stdout.write(self.style.WARNING(f'  ⚠ QR Code não gerado: {e}'))
            self.stdout.write(self.style.SUCCESS(f'  ✔ Aula criada para hoje (ID={aula.id})'))
            self.stdout.write(f'     URL presença: {aula.presenca_url}')
        else:
            self.stdout.write(f'  → Aula de hoje já existe (ID={aula.id})')
            self.stdout.write(f'     URL presença: {aula.presenca_url}')

        self.stdout.write(self.style.SUCCESS('\n✅  Seed concluído!'))
        self.stdout.write('\nCredenciais:')
        self.stdout.write('  Admin     → admin@sistema.edu / Admin@1234')
        self.stdout.write('  Professor → prof@sistema.edu  / Prof@1234')
        self.stdout.write('  Aluno     → aluno@sistema.edu / Aluno@1234')