from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'admin', 'Administrador'
        PROFESSOR = 'professor', 'Professor'
        STUDENT = 'aluno', 'Aluno'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.STUDENT,
        verbose_name='Perfil',
    )
    email = models.EmailField(unique=True, verbose_name='E-mail')

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'Usuário'
        verbose_name_plural = 'Usuários'
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return f'{self.get_full_name()} ({self.get_role_display()})'

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_professor(self):
        return self.role == self.Role.PROFESSOR

    @property
    def is_student(self):
        return self.role == self.Role.STUDENT


class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    matricula = models.CharField(max_length=20, unique=True ,verbose_name='Matrícula')
    curso = models.CharField(max_length=100, verbose_name='Curso')

    class Meta:
        verbose_name = 'Aluno'
        verbose_name_plural = 'Alunos'
        ordering = ['user__first_name']

    def __str__(self):
        return f'{self.user.get_full_name()} - {self.matricula}'

    @property
    def nome(self):
        return self.user.get_full_name()

    @property
    def email(self):
        return self.user.email


class Professor(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='professor_profile')
    departamento = models.CharField(max_length=100, verbose_name='Departamento')

    class Meta:
        verbose_name = 'Professor'
        verbose_name_plural = 'Professores'
        ordering = ['user__first_name']

    def __str__(self):
        return f'Prof. {self.user.get_full_name()} - {self.departamento}'

    @property
    def nome(self):
        return self.user.get_full_name()

    @property
    def email(self):
        return self.user.email
