from rest_framework import serializers
from .models import Presenca


class PresencaSerializer(serializers.ModelSerializer):
    aluno_nome = serializers.CharField(source='aluno.nome', read_only=True)
    aluno_matricula = serializers.CharField(source='aluno.matricula', read_only=True)
    aula_str = serializers.SerializerMethodField()
    disciplina_nome = serializers.CharField(source='aula.disciplina.nome', read_only=True)
    disciplina_codigo = serializers.CharField(source='aula.disciplina.codigo', read_only=True)
    data_aula = serializers.DateField(source='aula.data', read_only=True)

    class Meta:
        model = Presenca
        fields = [
            'id', 'aluno', 'aluno_nome', 'aluno_matricula',
            'aula', 'aula_str', 'disciplina_nome', 'disciplina_codigo', 'data_aula',
            'horario_registro', 'ip_registrado',
            'latitude', 'longitude',
            'status', 'motivo_negacao',
            'validado_rede', 'validado_geo',
        ]
        read_only_fields = [
            'id', 'horario_registro', 'ip_registrado',
            'validado_rede', 'validado_geo', 'motivo_negacao',
        ]

    def get_aula_str(self, obj):
        return str(obj.aula)


class PresencaRegistroSerializer(serializers.Serializer):
    """Used by students to register attendance via QR Code scan."""
    aula_id = serializers.IntegerField()
    token = serializers.CharField(max_length=128)
    latitude = serializers.DecimalField(max_digits=10, decimal_places=8, required=False, allow_null=True)
    longitude = serializers.DecimalField(max_digits=11, decimal_places=8, required=False, allow_null=True)


class PresencaUpdateSerializer(serializers.ModelSerializer):
    """Professor can update attendance status."""
    class Meta:
        model = Presenca
        fields = ['status', 'motivo_negacao']
