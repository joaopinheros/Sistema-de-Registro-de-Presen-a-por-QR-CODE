#!/bin/bash

set -e

VERDE='\033[0;32m'
AMARELO='\033[1;33m'
VERMELHO='\033[0;31m'
NC='\033[0m'

echo -e "${VERDE}========================================${NC}"
echo -e "${VERDE}   Sistema de Presença por QR Code      ${NC}"
echo -e "${VERDE}   Setup automático                     ${NC}"
echo -e "${VERDE}========================================${NC}"
echo ""

# ── 1. Verificar Docker ──────────────────────────────────────────────────────
echo -e "${AMARELO}[1/6] Verificando Docker...${NC}"
if ! command -v docker &> /dev/null; then
    echo -e "${VERMELHO}Docker não encontrado. Instale em: https://docs.docker.com/get-docker/${NC}"
    exit 1
fi
if ! docker info &> /dev/null; then
    echo -e "${VERMELHO}Docker não está rodando. Inicie o Docker e tente novamente.${NC}"
    exit 1
fi
echo -e "${VERDE}✓ Docker OK${NC}"

# ── 2. Verificar Python ──────────────────────────────────────────────────────
echo -e "${AMARELO}[2/6] Verificando Python...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo -e "${VERMELHO}Python não encontrado. Instale Python 3.10+ e tente novamente.${NC}"
    exit 1
fi
echo -e "${VERDE}✓ Python OK ($($PYTHON --version))${NC}"

# ── 3. Criar .env se não existir ─────────────────────────────────────────────
echo -e "${AMARELO}[3/6] Configurando .env...${NC}"
if [ ! -f ".env" ]; then
    cat > .env << 'EOF'
SECRET_KEY=django-insecure-dev-key-apenas-para-testes-locais
DEBUG=True
ALLOWED_HOSTS=*

DB_NAME=attendance_db
DB_USER=postgres
DB_PASSWORD=4790
DB_HOST=localhost
DB_PORT=5432

REDIS_URL=redis://localhost:6380/0
RABBITMQ_URL=amqp://guest:guest@localhost:5672/

SYSTEM_BASE_URL=http://localhost:8000
CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:8000

UNIVERSITY_IP_RANGES=::/0,0.0.0.0/0
EOF
    echo -e "${VERDE}✓ .env criado com configurações padrão${NC}"
else
    echo -e "${VERDE}✓ .env já existe${NC}"
fi

# ── 4. Subir banco e redis com Docker ────────────────────────────────────────
echo -e "${AMARELO}[4/6] Subindo banco de dados e Redis...${NC}"
docker compose down --remove-orphans 2>/dev/null || true
docker compose up -d db redis

echo -n "   Aguardando PostgreSQL ficar pronto"
for i in $(seq 1 30); do
    if docker compose exec -T db pg_isready -U postgres &> /dev/null; then
        echo -e " ${VERDE}✓${NC}"
        break
    fi
    echo -n "."
    sleep 2
    if [ $i -eq 30 ]; then
        echo -e " ${VERMELHO}timeout${NC}"
        echo -e "${VERMELHO}Banco demorou demais. Tente: docker compose up -d${NC}"
        exit 1
    fi
done

# ── 5. Criar venv e instalar dependências ────────────────────────────────────
echo -e "${AMARELO}[5/6] Instalando dependências Python...${NC}"
if [ ! -d ".venv" ]; then
    $PYTHON -m venv .venv
    echo -e "${VERDE}✓ Virtualenv criado${NC}"
fi

if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    VENV_PYTHON=".venv/Scripts/python"
    VENV_PIP=".venv/Scripts/pip"
else
    VENV_PYTHON=".venv/bin/python"
    VENV_PIP=".venv/bin/pip"
fi

$VENV_PIP install --quiet --upgrade pip
$VENV_PIP install --quiet -r requirements.txt
echo -e "${VERDE}✓ Dependências instaladas${NC}"

# ── 6. Migrations, static e seed ─────────────────────────────────────────────
echo -e "${AMARELO}[6/6] Preparando banco de dados...${NC}"
mkdir -p static staticfiles media

$VENV_PYTHON manage.py migrate --run-syncdb 2>&1 | tail -3

# Cria tabela de cache (fallback se Redis não estiver disponível)
$VENV_PYTHON manage.py createcachetable 2>/dev/null || true

echo -e "${VERDE}✓ Migrations aplicadas${NC}"

$VENV_PYTHON manage.py collectstatic --noinput --clear -v 0 2>/dev/null || true
echo -e "${VERDE}✓ Static files coletados${NC}"

# Criar dados de demonstração
$VENV_PYTHON manage.py seed_demo

echo ""
echo -e "${VERDE}========================================${NC}"
echo -e "${VERDE}   Setup concluído com sucesso!         ${NC}"
echo -e "${VERDE}========================================${NC}"
echo ""
echo -e "  Para rodar o servidor:"
echo -e "  ${AMARELO}.venv/bin/python manage.py runserver${NC}"
echo ""
echo -e "  Credenciais:"
echo -e "  Admin:     ${AMARELO}admin@sistema.edu / Admin@1234${NC}"
echo -e "  Professor: ${AMARELO}prof@sistema.edu / Prof@1234${NC}"
echo -e "  Aluno:     ${AMARELO}aluno@sistema.edu / Aluno@1234${NC}"
echo ""