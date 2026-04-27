#!/usr/bin/env bash
# ============================================================
#  FrequênciaQR — Script de instalação e inicialização
#  Testado em Ubuntu 22.04 / 24.04
# ============================================================
set -e

echo "=============================================="
echo "  FrequênciaQR — Setup"
echo "=============================================="

# 1. Python venv
if [ ! -d ".venv" ]; then
  echo "[1/6] Criando ambiente virtual Python..."
  python3 -m venv .venv
fi
source .venv/bin/activate

# 2. Dependências
echo "[2/6] Instalando dependências Python..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt gunicorn

# 3. .env
if [ ! -f ".env" ]; then
  echo "[3/6] Criando arquivo .env a partir do exemplo..."
  cp .env.example .env
  echo "  ⚠  IMPORTANTE: Configure o banco de dados no arquivo .env antes de rodar novamente o script."
else
  echo "[3/6] Arquivo .env já existe."
fi

# 4. Banco de dados
echo "[4/6] Aplicando migrações..."
python manage.py migrate --run-syncdb

# 5. Dados demo
echo "[5/6] Inserindo dados de demonstração..."
python manage.py seed_demo

# 6. Estáticos
echo "[6/6] Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

echo ""
echo "=============================================="
echo "  ✅  Instalação concluída!"
echo "=============================================="
echo ""
echo "  Para iniciar o servidor de desenvolvimento:"
echo "    source .venv/bin/activate"
echo "    python manage.py runserver"
echo ""
echo "  Credenciais padrão:"
echo "    Admin     → admin@sistema.edu / Admin@1234"
echo "    Professor → prof@sistema.edu  / Prof@1234"
echo "    Aluno     → aluno@sistema.edu / Aluno@1234"
echo ""
echo "  Para subir com Docker Compose:"
echo "    docker compose up --build"
echo ""
