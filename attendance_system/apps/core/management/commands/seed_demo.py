"""
Management command: python manage.py seed_demo

Creates demo users, a classroom, discipline and a lesson for testing.
"""
import os
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
        if not User.objects.filter(email='admin@sistema.edu').exists():
            admin = User.objects.create_superuser(
                username='admin@sistema.edu',
                email='admin@sistema.edu',
                password='Admin@1234',
                first_name='Admin',
                last_name='Sistema',
                role=User.Role.ADMIN,
            )
            self.stdout.write(self.style.SUCCESS('  ✔ Admin criado: admin@sistema.edu / Admin@1234'))
        else:
            admin = User.objects.get(email='admin@sistema.edu')

        # ── Professor ──
        if not User.objects.filter(email='prof@sistema.edu').exists():
            prof_user = User.objects.create_user(
                username='prof@sistema.edu',
                email='prof@sistema.edu',
                password='Prof@1234',
                first_name='Carlos',
                last_name='Andrade',
                role=User.Role.PROFESSOR,
            )
            prof = Professor.objects.create(user=prof_user, departamento='Ciência da Computação')
            self.stdout.write(self.style.SUCCESS('  ✔ Professor criado: prof@sistema.edu / Prof@1234'))
        else:
            prof = Professor.objects.get(user__email='prof@sistema.edu')

        # ── Student ──
        if not User.objects.filter(email='aluno@sistema.edu').exists():
            aluno_user = User.objects.create_user(
                username='aluno@sistema.edu',
                email='aluno@sistema.edu',
                password='Aluno@1234',
                first_name='Maria',
                last_name='Silva',
                role=User.Role.STUDENT,
            )
            Student.objects.create(
                user=aluno_user,
                matricula='2024001',
                curso='Ciência da Computação',
            )
            self.stdout.write(self.style.SUCCESS('  ✔ Aluno criado: aluno@sistema.edu / Aluno@1234'))

        # ── Sala ──
        sala, _ = Sala.objects.get_or_create(
            nome='Lab 101',
            defaults={
                'predio': 'Bloco A',
                'latitude': -19.9167,
                'longitude': -43.9345,
                'raio_permitido': 50,
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
                'horario_fim': time(10, 0),
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

        self.stdout.write(self.style.SUCCESS('\n✅  Seed concluído!'))
        self.stdout.write('\nCredenciais:')
        self.stdout.write('  Admin    → admin@sistema.edu / Admin@1234')
        self.stdout.write('  Professor → prof@sistema.edu  / Prof@1234')
        self.stdout.write('  Aluno    → aluno@sistema.edu / Aluno@1234')
