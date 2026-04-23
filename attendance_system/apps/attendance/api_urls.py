from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views, web_views

router = DefaultRouter()
router.register('', views.PresencaViewSet, basename='presenca')

urlpatterns = [
    path('', include(router.urls)),
]
