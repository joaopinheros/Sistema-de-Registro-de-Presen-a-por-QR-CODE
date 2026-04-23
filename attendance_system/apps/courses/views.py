from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import Sala, Disciplina, Aula
from .serializers import (
    SalaSerializer, DisciplinaSerializer, DisciplinaListSerializer,
    AulaSerializer, AulaCreateSerializer
)
from apps.accounts.permissions import IsAdminUser, IsProfessorOrAdmin
from .services import QRCodeService


class SalaViewSet(viewsets.ModelViewSet):
    queryset = Sala.objects.all()
    serializer_class = SalaSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['predio', 'ativa']
    search_fields = ['nome', 'predio']
    ordering_fields = ['predio', 'nome']

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsAdminUser()]


class DisciplinaViewSet(viewsets.ModelViewSet):
    queryset = Disciplina.objects.select_related('professor__user').all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['semestre', 'ano', 'ativa', 'professor']
    search_fields = ['nome', 'codigo', 'professor__user__first_name']
    ordering_fields = ['nome', 'codigo', 'ano', 'semestre']

    def get_serializer_class(self):
        if self.action == 'list':
            return DisciplinaListSerializer
        return DisciplinaSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsProfessorOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.is_professor:
            return Disciplina.objects.filter(professor__user=user).select_related('professor__user')
        return Disciplina.objects.select_related('professor__user').all()


class AulaViewSet(viewsets.ModelViewSet):
    queryset = Aula.objects.select_related('disciplina__professor__user', 'sala').all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['disciplina', 'sala', 'data', 'ativa']
    search_fields = ['disciplina__nome', 'disciplina__codigo', 'sala__nome']
    ordering_fields = ['data', 'horario_inicio']

    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return AulaCreateSerializer
        return AulaSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        return [IsProfessorOrAdmin()]

    def get_queryset(self):
        user = self.request.user
        if user.is_professor:
            return Aula.objects.filter(
                disciplina__professor__user=user
            ).select_related('disciplina__professor__user', 'sala')
        if user.is_student:
            return Aula.objects.filter(ativa=True).select_related('disciplina__professor__user', 'sala')
        return Aula.objects.select_related('disciplina__professor__user', 'sala').all()

    def perform_create(self, serializer):
        aula = serializer.save()
        # Auto-generate QR Code on creation
        QRCodeService.generate(aula)

    @action(detail=True, methods=['post'], permission_classes=[IsProfessorOrAdmin])
    def gerar_qrcode(self, request, pk=None):
        aula = self.get_object()
        try:
            qr_path = QRCodeService.generate(aula)
            serializer = AulaSerializer(aula, context={'request': request})
            return Response({
                'detail': 'QR Code gerado com sucesso.',
                'aula': serializer.data,
            })
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=True, methods=['get'], permission_classes=[IsProfessorOrAdmin])
    def qrcode(self, request, pk=None):
        aula = self.get_object()
        if not aula.qrcode_imagem:
            QRCodeService.generate(aula)
            aula.refresh_from_db()
        serializer = AulaSerializer(aula, context={'request': request})
        return Response(serializer.data)
