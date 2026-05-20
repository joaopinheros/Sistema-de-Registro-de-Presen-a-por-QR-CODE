from rest_framework import serializers
from .models import Sala, Disciplina, Aula


class SalaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sala
        fields = ['id', 'nome', 'predio', 'latitude', 'longitude', 'raio_permitido', 'capacidade', 'ativa']


class DisciplinaSerializer(serializers.ModelSerializer):
    professor_nome = serializers.CharField(source='professor.nome', read_only=True)

    class Meta:
        model = Disciplina
        fields = ['id', 'nome', 'codigo', 'professor', 'professor_nome', 'semestre', 'ano', 'descricao', 'ativa']


class DisciplinaListSerializer(serializers.ModelSerializer):
    professor_nome = serializers.CharField(source='professor.nome', read_only=True)

    class Meta:
        model = Disciplina
        fields = ['id', 'nome', 'codigo', 'professor_nome', 'semestre', 'ano', 'ativa']


class AulaSerializer(serializers.ModelSerializer):
    disciplina_nome = serializers.CharField(source='disciplina.nome', read_only=True)
    disciplina_codigo = serializers.CharField(source='disciplina.codigo', read_only=True)
    sala_nome = serializers.CharField(source='sala.nome', read_only=True)
    sala_predio = serializers.CharField(source='sala.predio', read_only=True)
    esta_ativa = serializers.BooleanField(read_only=True)
    presenca_url = serializers.CharField(read_only=True)
    qrcode_url = serializers.SerializerMethodField()

    class Meta:
        model = Aula
        fields = [
            'id', 'disciplina', 'disciplina_nome', 'disciplina_codigo',
            'sala', 'sala_nome', 'sala_predio',
            'data', 'horario_inicio', 'horario_fim',
            'latitude', 'longitude', 'raio_permitido',
            'token_qrcode', 'qrcode_url', 'presenca_url',
            'descricao', 'ativa', 'esta_ativa', 'criada_em',
        ]
        read_only_fields = ['id', 'token_qrcode', 'criada_em']

    def get_qrcode_url(self, obj):
        request = self.context.get('request')
        if obj.qrcode_imagem and request:
            return request.build_absolute_uri(obj.qrcode_imagem.url)
        return None


class AulaCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Aula
        fields = [
            'disciplina', 'sala', 'data', 'horario_inicio', 'horario_fim',
            'latitude', 'longitude', 'raio_permitido', 'descricao', 'ativa',
        ]

    def validate(self, attrs):
        if attrs.get('horario_inicio') and attrs.get('horario_fim'):
            if attrs['horario_inicio'] >= attrs['horario_fim']:
                raise serializers.ValidationError(
                    'O horário de início deve ser anterior ao horário de fim.'
                )
        return attrs
