from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from apps.courses.public_views import public_disciplinas, public_professores, public_aulas

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('dashboard/', include('apps.core.urls')),
    path('painel-admin/', include('apps.core.admin_urls')),
    path('painel-professor/', include('apps.core.professor_urls')),
    path('presenca/', include('apps.attendance.urls')),
    # REST API — autenticada
    path('api/', include([
        path('auth/', include('apps.accounts.api_urls')),
        path('courses/', include('apps.courses.api_urls')),
        path('attendance/', include('apps.attendance.api_urls')),
    ])),
    # API Pública — sem autenticação, com cache Redis 5 min
    path('api/public/', include([
        path('disciplinas/', public_disciplinas, name='public_disciplinas'),
        path('professores/', public_professores, name='public_professores'),
        path('aulas/', public_aulas, name='public_aulas'),
    ])),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
