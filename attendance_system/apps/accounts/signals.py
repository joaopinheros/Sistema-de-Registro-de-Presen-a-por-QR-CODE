from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import User, Student, Professor


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """Auto-create Student or Professor profile on user creation."""
    if created:
        if instance.role == User.Role.STUDENT:
            Student.objects.get_or_create(user=instance, defaults={'matricula': '', 'curso': ''})
        elif instance.role == User.Role.PROFESSOR:
            Professor.objects.get_or_create(user=instance, defaults={'departamento': ''})
