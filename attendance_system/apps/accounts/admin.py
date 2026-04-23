from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Student, Professor


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ['email', 'first_name', 'last_name', 'role', 'is_active', 'date_joined']
    list_filter = ['role', 'is_active', 'is_staff']
    search_fields = ['email', 'first_name', 'last_name', 'username']
    ordering = ['first_name', 'last_name']
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Perfil', {'fields': ('role',)}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Perfil', {'fields': ('email', 'role')}),
    )


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ['matricula', 'nome', 'email', 'curso']
    search_fields = ['user__first_name', 'user__last_name', 'matricula', 'curso']
    list_filter = ['curso']


@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ['nome', 'email', 'departamento']
    search_fields = ['user__first_name', 'user__last_name', 'departamento']
    list_filter = ['departamento']
