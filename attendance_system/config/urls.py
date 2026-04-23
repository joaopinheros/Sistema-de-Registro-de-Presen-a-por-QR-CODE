from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('allauth.urls')),
    path('', RedirectView.as_view(url='/dashboard/', permanent=False)),
    path('dashboard/', include('apps.core.urls')),
    path('presenca/', include('apps.attendance.urls')),
    # REST API
    path('api/', include([
        path('auth/', include('apps.accounts.api_urls')),
        path('courses/', include('apps.courses.api_urls')),
        path('attendance/', include('apps.attendance.api_urls')),
    ])),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
