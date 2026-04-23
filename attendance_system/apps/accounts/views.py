from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import User, Student, Professor
from .serializers import (
    StudentSerializer, StudentWriteSerializer,
    ProfessorSerializer, ProfessorWriteSerializer,
    UserSerializer,
)
from apps.accounts.permissions import IsAdminOrSelf, IsAdminUser


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student.objects.select_related('user').all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['curso']
    search_fields = ['user__first_name', 'user__last_name', 'matricula', 'curso']
    ordering_fields = ['user__first_name', 'matricula']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return StudentWriteSerializer
        return StudentSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        user = self.request.user
        if user.is_student:
            return Student.objects.filter(user=user)
        return Student.objects.select_related('user').all()


class ProfessorViewSet(viewsets.ModelViewSet):
    queryset = Professor.objects.select_related('user').all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['departamento']
    search_fields = ['user__first_name', 'user__last_name', 'departamento']
    ordering_fields = ['user__first_name', 'departamento']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return ProfessorWriteSerializer
        return ProfessorSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUser()]

    def get_queryset(self):
        user = self.request.user
        if user.is_professor:
            return Professor.objects.filter(user=user)
        return Professor.objects.select_related('user').all()


class CurrentUserView(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def me(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)
