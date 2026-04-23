import ipaddress
import math
from django.conf import settings
from django.utils import timezone


def get_client_ip(request):
    """Extract real client IP from request headers."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def validate_university_network(ip_str):
    """Check if IP belongs to the university network ranges."""
    if not ip_str:
        return False
    try:
        client_ip = ipaddress.ip_address(ip_str)
        for cidr in settings.UNIVERSITY_IP_RANGES:
            network = ipaddress.ip_network(cidr.strip(), strict=False)
            if client_ip in network:
                return True
    except ValueError:
        pass
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
        return False, 0
    distance = haversine_distance(
        student_lat, student_lon,
        sala.latitude, sala.longitude
    )
    return distance <= sala.raio_permitido, distance


def validate_aula_token(aula, token):
    """Validate that the QR Code token matches the aula."""
    return aula.token_qrcode == token


def validate_aula_schedule(aula, tolerance_minutes=15):
    """Check if current time is within the class schedule (with tolerance)."""
    from datetime import timedelta
    now = timezone.localtime(timezone.now())
    today = now.date()
    current_time = now.time()

    if aula.data != today:
        return False, 'A aula não é hoje.'

    from datetime import datetime, date
    start_dt = datetime.combine(date.today(), aula.horario_inicio)
    end_dt = datetime.combine(date.today(), aula.horario_fim)

    # Allow registering up to tolerance_minutes before start
    window_start = start_dt - timedelta(minutes=tolerance_minutes)
    # Allow registering up to tolerance_minutes after end
    window_end = end_dt + timedelta(minutes=tolerance_minutes)

    now_naive = now.replace(tzinfo=None)
    if window_start <= now_naive <= window_end:
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

    def run(self):
        # 1. Token
        if not validate_aula_token(self.aula, self.token):
            self.errors.append('Token inválido ou QR Code expirado.')
            return False

        # 2. Schedule
        ok, msg = validate_aula_schedule(self.aula)
        if not ok:
            self.errors.append(msg)
            return False

        # 3. Network
        self.validado_rede = validate_university_network(self.ip)
        if not self.validado_rede:
            self.errors.append(
                f'Acesso negado: você não está conectado à rede da universidade (IP: {self.ip}).'
            )
            return False

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
            return False

        return True
