# ================================================
# VALIDAÇÕES DE PRESENÇA — CONFIGURAÇÃO ATUAL
# ================================================
# ATIVAS:
#   ✓ Token QR Code (Redis + banco)
#   ✓ Autenticação do aluno
#   ✓ Duplo registro bloqueado
#   ✓ Janela de horário da aula
#   ✓ Rede institucional (IP)
#
# DESATIVADAS:
#   ✗ Geolocalização (comentada, código mantido)
#
# PARA PRODUÇÃO:
#   - Atualizar ALLOWED_IP_RANGES no .env
#     com o range de IP real da faculdade
#   - Reativar geolocalização se necessário
# ================================================

import ipaddress
import math
import logging
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache

logger = logging.getLogger(__name__)

# ── Chaves Redis ──────────────────────────────────────────────────────────────
PRESENCA_CACHE_KEY = 'presenca:{aula_id}:{aluno_id}'
QRCODE_TOKEN_CACHE_KEY = 'qrcode:token:{token}'
PRESENCA_CACHE_TTL = 86400   # 24 horas


def get_client_ip(request):
    """Extract real client IP from request headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    
    logger.info(f"IP do cliente: {ip}")
    return ip


def ip_permitido(ip, ranges):
    """Verifica se o IP está em algum dos ranges (CIDR ou exato)."""
    try:
        addr = ipaddress.ip_address(ip)
        for r in ranges:
            try:
                if addr in ipaddress.ip_network(r, strict=False):
                    return True
            except ValueError:
                if str(addr) == r:
                    return True
        return False
    except ValueError:
        return False


def validate_university_network(ip_str):
    """Check if IP belongs to the allowed network ranges (settings.ALLOWED_IP_RANGES)."""
    if not ip_str:
        logger.warning("IP vazio")
        return False
    logger.info(f"Validando IP: {ip_str} contra ALLOWED_IP_RANGES={settings.ALLOWED_IP_RANGES}")
    result = ip_permitido(ip_str, settings.ALLOWED_IP_RANGES)
    if result:
        logger.info(f"IP {ip_str} validado")
    else:
        logger.warning(f"IP {ip_str} NÃO validado em nenhuma rede permitida")
    return result


def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance in meters between two geographic coordinates."""
    R = 6371000  # Earth radius in meters
    phi1 = math.radians(float(lat1))
    phi2 = math.radians(float(lat2))
    dphi = math.radians(float(lat2) - float(lat1))
    dlambda = math.radians(float(lon2) - float(lon1))

    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def validate_geolocation(student_lat, student_lon, location):
    """Check if student is within allowed radius of the classroom location.

    location must expose .latitude, .longitude, .raio_permitido
    (accepts Aula or Sala instances).
    """
    if student_lat is None or student_lon is None:
        logger.warning("Geolocalização vazia")
        return False, 0
    if location.latitude is None or location.longitude is None:
        logger.warning("Localização da aula não definida")
        return False, 0
    distance = haversine_distance(
        student_lat, student_lon,
        location.latitude, location.longitude
    )
    logger.info(f"Distância calculada: {distance:.2f}m, Raio permitido: {location.raio_permitido}m")
    return distance <= location.raio_permitido, distance


def validate_aula_token(aula, token):
    """Validate QR Code token — checks Redis first, falls back to DB."""
    redis_key = QRCODE_TOKEN_CACHE_KEY.format(token=token)
    cached_aula_id = cache.get(redis_key)
    if cached_aula_id is not None:
        result = (cached_aula_id == aula.id)
        logger.info(f"Validação de token via Redis: {result} (aula_id={cached_aula_id})")
        return result

    result = (aula.token_qrcode == token)
    if result:
        # Cachear token com TTL baseado na duração da aula
        from datetime import datetime, date as date_cls
        start = datetime.combine(date_cls.today(), aula.horario_inicio)
        end = datetime.combine(date_cls.today(), aula.horario_fim)
        ttl = max(60, int((end - start).total_seconds()))
        cache.set(redis_key, aula.id, timeout=ttl)
        logger.info(f"Token cacheado no Redis com TTL={ttl}s")
    logger.info(f"Validação de token via DB: {result}")
    return result


def marcar_presenca_cache(aula_id, aluno_id):
    """Seta chave Redis indicando presença já registrada (TTL 24h)."""
    key = PRESENCA_CACHE_KEY.format(aula_id=aula_id, aluno_id=aluno_id)
    cache.set(key, 1, timeout=PRESENCA_CACHE_TTL)
    logger.info(f"Presença cacheada: {key}")


def checar_presenca_cache(aula_id, aluno_id):
    """Retorna True se presença já está registrada no Redis."""
    key = PRESENCA_CACHE_KEY.format(aula_id=aula_id, aluno_id=aluno_id)
    hit = cache.get(key) is not None
    if hit:
        logger.info(f"Cache hit de presença duplicada: {key}")
    return hit


def validate_aula_schedule(aula, tolerance_minutes=15):
    """Check if current time is within the class schedule (with tolerance)."""
    from datetime import timedelta
    now = timezone.localtime(timezone.now())
    today = now.date()
    current_time = now.time()

    if aula.data != today:
        logger.warning(f"Aula não é hoje. Data da aula: {aula.data}, Hoje: {today}")
        return False, 'A aula não é hoje.'

    from datetime import datetime, date
    start_dt = datetime.combine(date.today(), aula.horario_inicio)
    end_dt = datetime.combine(date.today(), aula.horario_fim)

    # Allow registering up to tolerance_minutes before start
    window_start = start_dt - timedelta(minutes=tolerance_minutes)
    # Allow registering up to tolerance_minutes after end
    window_end = end_dt + timedelta(minutes=tolerance_minutes)

    now_naive = now.replace(tzinfo=None)
    logger.info(f"Horário agora: {now_naive}, Janela: {window_start} até {window_end}")
    
    if window_start <= now_naive <= window_end:
        logger.info("Horário válido para registrar presença")
        return True, 'OK'
    if now_naive < window_start:
        return False, f'A aula começa às {aula.horario_inicio.strftime("%H:%M")}.'
    return False, f'O registro de presença encerrou às {aula.horario_fim.strftime("%H:%M")}.'


class AttendanceValidator:
    """Orchestrates all presence validations."""

    def __init__(self, request, aula, token, student_lat=None, student_lon=None,
                 aluno_id=None, ip=None):
        self.request = request
        self.aula = aula
        self.token = token
        self.student_lat = student_lat
        self.student_lon = student_lon
        self.aluno_id = aluno_id
        self.errors = []
        # Aceita IP direto (tasks Celery) ou extrai do request
        self.ip = ip if ip is not None else get_client_ip(request)
        self.validado_rede = False
        self.validado_geo = False
        logger.info(f"=== INICIANDO VALIDAÇÃO DE PRESENÇA ===")
        logger.info(f"IP: {self.ip}, Aula: {aula}, Token: {token[:10]}...")

    def run(self):
        # Etapa 0 — cache Redis: rejeita imediatamente se presença já registrada
        if self.aluno_id is not None:
            if checar_presenca_cache(self.aula.id, self.aluno_id):
                self.errors.append('Presença já registrada (cache Redis).')
                return False

        logger.info("--- ETAPA 1: Validar Token ---")
        # 1. Token
        if not validate_aula_token(self.aula, self.token):
            self.errors.append('Token inválido ou QR Code expirado.')
            logger.error("Token inválido")
            return False

        logger.info("--- ETAPA 2: Validar Horário ---")
        # 2. Schedule
        ok, msg = validate_aula_schedule(self.aula)
        if not ok:
            self.errors.append(msg)
            logger.error(f"Horário inválido: {msg}")
            return False

        logger.info("--- ETAPA 3: Validar Rede ---")
        # 3. Network
        self.validado_rede = validate_university_network(self.ip)
        if not self.validado_rede:
            self.errors.append(
                f'Acesso negado: você não está conectado à rede da universidade (IP: {self.ip}).'
            )
            logger.error(f"IP não autorizado: {self.ip}")
            return False

        # GEOLOCALIZAÇÃO DESATIVADA TEMPORARIAMENTE
        # Reativar removendo este comentário quando necessário
        # logger.info("--- ETAPA 4: Validar Geolocalização ---")
        # # Prefer coordinates captured at aula creation; fall back to sala when absent.
        # if self.aula.latitude is not None and self.aula.longitude is not None:
        #     geo_ref = self.aula
        # else:
        #     geo_ref = self.aula.sala
        # geo_ok, distance = validate_geolocation(self.student_lat, self.student_lon, geo_ref)
        # self.validado_geo = geo_ok
        # if not geo_ok:
        #     self.errors.append(
        #         f'Você está fora do raio permitido da aula '
        #         f'({geo_ref.raio_permitido}m). Distância medida: {distance:.0f}m.'
        #     )
        #     return False
        self.validado_geo = False

        logger.info("TODAS AS VALIDAÇÕES PASSARAM")
        return True