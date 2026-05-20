# FrequênciaQR — UFVJM

> Sistema web de registro de frequência por QR Code para a Universidade Federal dos Vales do Jequitinhonha e Mucuri.

## Sobre

O professor gera um QR Code para cada aula. O aluno escaneia com o celular, confirma a presença em um clique e o registro é validado em tempo real. A validação garante que o aluno está na rede institucional e dentro da janela de horário da aula.

## Tecnologias

- **Django 5.1** + Django REST Framework
- **PostgreSQL 16** — banco principal
- **Redis 7** — cache de sessões, deduplicação de presenças e tokens QR
- **RabbitMQ 3** + **Celery 5** — fila de tarefas assíncronas
- **django-allauth** — autenticação com e-mail/senha
- **Whitenoise** — servir arquivos estáticos
- **Docker + Nginx** — orquestração e proxy reverso

## Funcionalidades

- Autenticação com e-mail ou usuário (django-allauth)
- Três perfis de acesso: **Admin**, **Professor** e **Aluno**
- Geração de QR Code por aula com token único
- URL do QR Code gerada automaticamente do request (funciona em localhost e Cloudflare Tunnel sem configuração)
- Fluxo mobile-first: escanear → tela de confirmação → registrar com um toque
- Validação de IP por range CIDR configurável (`ALLOWED_IP_RANGES`)
- Validação de janela de horário da aula (±15 min de tolerância)
- Deduplicação via Redis — duplo registro bloqueado antes de chegar ao banco
- Cache de token QR no Redis com TTL igual à duração da aula
- Tarefas assíncronas via Celery (registro, auditoria, relatórios)
- **Painel Admin**: gestão de usuários, salas, disciplinas, vínculos aluno-disciplina, relatórios
- **Painel Professor**: aulas, disciplinas, presenças
- Dashboard com gráficos (Chart.js): presença por disciplina, evolução semanal, distribuição de usuários
- API REST com autenticação JWT e filtros
- Trilha de auditoria com sinais Django (`post_save`/`post_delete`)
- Arquitetura preparada para microserviços (4 serviços + nginx no Docker Compose)

## Como rodar

### Pré-requisitos

- Python 3.10+
- Docker e Docker Compose

### Setup rápido (desenvolvimento)

```bash
git clone <repositório>
cd attendance_system

# Sobe PostgreSQL + Redis, cria venv, instala deps,
# roda migrations e popula dados de demonstração
bash setup.sh

# Inicia o servidor
.venv/bin/python manage.py runserver
```

Acesse `http://localhost:8000` com as credenciais de demo:

| Perfil    | E-mail                  | Senha      |
|-----------|-------------------------|------------|
| Admin     | admin@sistema.edu       | Admin@1234 |
| Professor | prof@sistema.edu        | Prof@1234  |
| Aluno     | aluno@sistema.edu       | Aluno@1234 |

### Com Docker (stack completa)

```bash
cp .env.example .env          # ajuste as variáveis se necessário
docker compose up -d          # sobe todos os serviços

docker compose exec auth-service python manage.py migrate
docker compose exec auth-service python manage.py seed_demo
docker compose exec auth-service python manage.py collectstatic --noinput
```

Acesse `http://localhost` (porta 80, via Nginx).

## Variáveis de ambiente

Copie `.env.example` para `.env` e ajuste conforme o ambiente.

| Variável             | Descrição                                                     |
|----------------------|---------------------------------------------------------------|
| `SECRET_KEY`         | Chave secreta Django — troque em produção                     |
| `DEBUG`              | `True` em dev, `False` em produção                           |
| `DB_NAME/USER/PASS`  | Credenciais do PostgreSQL                                     |
| `DB_HOST`            | Host do banco (`localhost` local, `db` no Docker)            |
| `REDIS_URL`          | URL do Redis (`redis://localhost:6380/0` local)               |
| `RABBITMQ_URL`       | URL do RabbitMQ (`amqp://guest:guest@localhost:5672/`)        |
| `ALLOWED_IP_RANGES`  | IPs/CIDRs permitidos para registro de presença (ver abaixo)  |
| `SYSTEM_BASE_URL`    | URL base usada como fallback em management commands           |

## Observações de uso

- **`ALLOWED_IP_RANGES`**: em desenvolvimento aceita `127.0.0.1` e redes privadas. Para produção, configure com o range de IP real da rede da UFVJM (ex: `200.131.0.0/16`). Suporta IPv4, IPv6 e notação CIDR.
- **URL do QR Code**: gerada automaticamente via `request.build_absolute_uri()` — funciona em `localhost`, Cloudflare Tunnel ou qualquer domínio sem configuração adicional. `SYSTEM_BASE_URL` é usado apenas como fallback em scripts sem request (ex: `seed_demo`).
- **Geolocalização**: validação de coordenadas GPS está implementada porém desativada. Para reativar, descomente o bloco indicado em `apps/attendance/validators.py`.
- **Celery**: necessário apenas para o endpoint `/presenca/registrar-async/`. O fluxo principal (`/presenca/registrar/`) é síncrono e funciona sem o worker rodando.

## Licença

MIT
