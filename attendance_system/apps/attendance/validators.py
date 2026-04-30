import ipaddress
import math
import logging
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def get_client_ip(request):
    """Extract real client IP from request headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', '')
    
    logger.info(f"IP do cliente: {ip}")
    return ip


def validate_university_network(ip_str):
    """Check if IP belongs to the university network ranges."""
    if not ip_str:
        logger.warning("IP vazio")
        return False
    
    logger.info(f"Validando IP: {ip_str}")
    logger.info(f"IP ranges configurados: {settings.UNIVERSITY_IP_RANGES}")
    
    try:
        client_ip = ipaddress.ip_address(ip_str)
        logger.info(f"IP convertido para: {client_ip}")
        
        for cidr in settings.UNIVERSITY_IP_RANGES:
            cidr_limpo = cidr.strip()
            logger.info(f"Testando contra range: {cidr_limpo}")
            try:
                network = ipaddress.ip_network(cidr_limpo, strict=False)
                if client_ip in network:
                    logger.info(f"IP {ip_str} validado na rede {cidr_limpo}")
                    return True
            except ValueError as e:
                logger.error(f"Erro ao processar CIDR {cidr_limpo}: {e}")
        
        logger.warning(f"IP {ip_str} NÃO validado em nenhuma rede")
        return False
    except ValueError as e:
        logger.error(f"Erro ao converter IP {ip_str}: {e}")
        return False


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


def validate_geolocation(student_lat, student_lon, sala):
    """Check if student is within allowed radius of the classroom."""
    if student_lat is None or student_lon is None:
        logger.warning("Geolocalização vazia")
        return False, 0
    distance = haversine_distance(
        student_lat, student_lon,
        sala.latitude, sala.longitude
    )
    logger.info(f"Distância calculada: {distance:.2f}m, Raio permitido: {sala.raio_permitido}m")
    return distance <= sala.raio_permitido, distance


def validate_aula_token(aula, token):
    """Validate that the QR Code token matches the aula."""
    result = aula.token_qrcode == token
    logger.info(f"Validação de token: {result}")
    return result


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

    def __init__(self, request, aula, token, student_lat=None, student_lon=None):
        self.request = request
        self.aula = aula
        self.token = token
        self.student_lat = student_lat
        self.student_lon = student_lon
        self.errors = []
        self.ip = get_client_ip(request)
        self.validado_rede = False
        self.validado_geo = False
        logger.info(f"=== INICIANDO VALIDAÇÃO DE PRESENÇA ===")
        logger.info(f"IP: {self.ip}, Aula: {aula}, Token: {token[:10]}...")

    def run(self):
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

        logger.info("--- ETAPA 4: Validar Geolocalização ---")
        # 4. Geolocation
        geo_ok, distance = validate_geolocation(
            self.student_lat, self.student_lon, self.aula.sala
        )
        self.validado_geo = geo_ok
        if not geo_ok:
            self.errors.append(
                f'Você está fora do raio permitido da sala '
                f'({self.aula.sala.raio_permitido}m). '
                f'Distância medida: {distance:.0f}m.'
            )
            logger.error(f"Geolocalização inválida: {distance:.2f}m")
            return False
            


        logger.info("TODAS AS VALIDAÇÕES PASSARAM")
        return True