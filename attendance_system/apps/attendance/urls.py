from django.urls import path
from .web_views import presenca_scan

urlpatterns = [
    path('', presenca_scan, name='presenca_scan'),
]
