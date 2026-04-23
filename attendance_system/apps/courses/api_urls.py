from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SalaViewSet, DisciplinaViewSet, AulaViewSet

router = DefaultRouter()
router.register('salas', SalaViewSet, basename='sala')
router.register('disciplinas', DisciplinaViewSet, basename='disciplina')
router.register('aulas', AulaViewSet, basename='aula')

urlpatterns = [
    path('', include(router.urls)),
]
