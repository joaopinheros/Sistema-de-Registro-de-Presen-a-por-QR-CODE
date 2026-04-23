from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import StudentViewSet, ProfessorViewSet, CurrentUserView

router = DefaultRouter()
router.register('students', StudentViewSet, basename='student')
router.register('professors', ProfessorViewSet, basename='professor')
router.register('user', CurrentUserView, basename='current-user')

urlpatterns = [
    path('', include(router.urls)),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
