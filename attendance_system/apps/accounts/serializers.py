from rest_framework import serializers
from .models import User, Student, Professor


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'username', 'first_name', 'last_name', 'role', 'is_active']
        read_only_fields = ['id']


class StudentSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = Student
        fields = ['id', 'nome', 'matricula', 'email', 'curso', 'user']
        read_only_fields = ['id', 'nome', 'email']


class StudentWriteSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = Student
        fields = ['matricula', 'curso', 'first_name', 'last_name', 'email', 'password']

    def create(self, validated_data):
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=User.Role.STUDENT,
        )
        student = Student.objects.create(user=user, **validated_data)
        return student

    def update(self, instance, validated_data):
        instance.matricula = validated_data.get('matricula', instance.matricula)
        instance.curso = validated_data.get('curso', instance.curso)
        instance.save()
        return instance


class ProfessorSerializer(serializers.ModelSerializer):
    nome = serializers.CharField(source='user.get_full_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    user = UserSerializer(read_only=True)

    class Meta:
        model = Professor
        fields = ['id', 'nome', 'email', 'departamento', 'user']
        read_only_fields = ['id', 'nome', 'email']


class ProfessorWriteSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})

    class Meta:
        model = Professor
        fields = ['departamento', 'first_name', 'last_name', 'email', 'password']

    def create(self, validated_data):
        first_name = validated_data.pop('first_name')
        last_name = validated_data.pop('last_name')
        email = validated_data.pop('email')
        password = validated_data.pop('password')
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            role=User.Role.PROFESSOR,
        )
        professor = Professor.objects.create(user=user, **validated_data)
        return professor

    def update(self, instance, validated_data):
        instance.departamento = validated_data.get('departamento', instance.departamento)
        instance.save()
        return instance
