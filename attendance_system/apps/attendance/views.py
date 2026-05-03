from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.shortcuts import get_object_or_404
from django.utils import timezone

from .models import Presenca
from .serializers import PresencaSerializer, PresencaRegistroSerializer, PresencaUpdateSerializer
from .validators import AttendanceValidator, get_client_ip
from apps.accounts.permissions import IsProfessorOrAdmin, IsStudentUser
from apps.courses.models import Aula
from apps.audit.utils import log_action


class PresencaViewSet(viewsets.ModelViewSet):
    queryset = Presenca.objects.select_related(
        'aluno__user', 'aula__disciplina__professor__user', 'aula__sala'
    ).all()
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['status', 'aula', 'aluno', 'aula__disciplina', 'aula__data']
    search_fields = [
        'aluno__user__first_name', 'aluno__user__last_name',
        'aluno__matricula', 'aula__disciplina__nome',
    ]
    ordering_fields = ['horario_registro', 'status', 'aula__data']

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update']:
            return PresencaUpdateSerializer
        return PresencaSerializer

    def get_permissions(self):
        if self.action == 'registrar':
            return [permissions.IsAuthenticated()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsProfessorOrAdmin()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if user.is_student:
            return Presenca.objects.filter(
                aluno__user=user
            ).select_related('aluno__user', 'aula__disciplina', 'aula__sala')
        if user.is_professor:
            return Presenca.objects.filter(
                aula__disciplina__professor__user=user
            ).select_related('aluno__user', 'aula__disciplina__professor__user', 'aula__sala')
        return self.queryset

    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def registrar(self, request):
        """Student registers attendance by scanning QR Code."""
        user = request.user
        if not user.is_student:
            return Response(
                {'detail': 'Somente alunos podem registrar presença.'},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = PresencaRegistroSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        aula = get_object_or_404(Aula, id=data['aula_id'], ativa=True)

        # Bloqueia só se já tiver PRESENTE — falha anterior não impede nova tentativa
        if Presenca.objects.filter(
            aluno=user.student_profile, aula=aula, status=Presenca.Status.PRESENTE
        ).exists():
            return Response(
                {'detail': 'Presença já registrada para esta aula.'},
                status=status.HTTP_409_CONFLICT
            )

        validator = AttendanceValidator(
            request=request,
            aula=aula,
            token=data['token'],
            student_lat=data.get('latitude'),
            student_lon=data.get('longitude'),
        )

        if validator.run():
            try:
                presenca = Presenca.objects.get(aluno=user.student_profile, aula=aula)
                presenca.ip_registrado = validator.ip
                presenca.latitude = data.get('latitude')
                presenca.longitude = data.get('longitude')
                presenca.status = Presenca.Status.PRESENTE
                presenca.motivo_negacao = ''
                presenca.validado_rede = validator.validado_rede
                presenca.validado_geo = validator.validado_geo
                presenca.horario_registro = timezone.now()
                presenca.save()
            except Presenca.DoesNotExist:
                presenca = Presenca.objects.create(
                    aluno=user.student_profile,
                    aula=aula,
                    ip_registrado=validator.ip,
                    latitude=data.get('latitude'),
                    longitude=data.get('longitude'),
                    status=Presenca.Status.PRESENTE,
                    validado_rede=validator.validado_rede,
                    validado_geo=validator.validado_geo,
                )
            log_action(user, 'PRESENÇA_REGISTRADA', f'Aula ID {aula.id}', request)
            return Response(
                PresencaSerializer(presenca).data,
                status=status.HTTP_201_CREATED
            )
        else:
            try:
                presenca = Presenca.objects.get(aluno=user.student_profile, aula=aula)
                presenca.ip_registrado = validator.ip
                presenca.latitude = data.get('latitude')
                presenca.longitude = data.get('longitude')
                presenca.status = Presenca.Status.NEGADO
                presenca.motivo_negacao = '; '.join(validator.errors)
                presenca.validado_rede = validator.validado_rede
                presenca.validado_geo = validator.validado_geo
                presenca.horario_registro = timezone.now()
                presenca.save()
            except Presenca.DoesNotExist:
                Presenca.objects.create(
                    aluno=user.student_profile,
                    aula=aula,
                    ip_registrado=validator.ip,
                    latitude=data.get('latitude'),
                    longitude=data.get('longitude'),
                    status=Presenca.Status.NEGADO,
                    motivo_negacao='; '.join(validator.errors),
                    validado_rede=validator.validado_rede,
                    validado_geo=validator.validado_geo,
                )
            log_action(user, 'PRESENÇA_NEGADA', '; '.join(validator.errors), request)
            return Response(
                {'detail': 'Presença não registrada.', 'erros': validator.errors},
                status=status.HTTP_403_FORBIDDEN
            )
