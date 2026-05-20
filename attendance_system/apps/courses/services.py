import qrcode
import io
from django.core.files.base import ContentFile
from django.conf import settings
from django.core.cache import cache


class QRCodeService:
    @staticmethod
    def generate(aula, request=None):
        """Generate QR Code image for a given Aula instance.

        Uses request.build_absolute_uri() when available so the URL works
        automatically in localhost, Cloudflare Tunnel, or any other domain.
        Falls back to settings.SYSTEM_BASE_URL for management commands/tasks.
        Also caches the token→aula_id mapping in Redis so validators
        can verify tokens without hitting the database every time.
        """
        path = f'/presenca/registrar/?id={aula.id}&token={aula.token_qrcode}'
        if request is not None:
            url = request.build_absolute_uri(path)
        else:
            url = aula.presenca_url

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="#1a1a2e", back_color="white")

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)

        filename = f'qrcode_aula_{aula.id}_{aula.token_qrcode[:8]}.png'
        aula.qrcode_imagem.save(
            filename,
            ContentFile(buffer.getvalue()),
            save=True,
        )

        # Cachear token no Redis — TTL baseado na duração da aula
        from datetime import datetime, date as date_cls
        start = datetime.combine(date_cls.today(), aula.horario_inicio)
        end = datetime.combine(date_cls.today(), aula.horario_fim)
        ttl = max(60, int((end - start).total_seconds()))
        redis_key = f'qrcode:token:{aula.token_qrcode}'
        cache.set(redis_key, aula.id, timeout=ttl)

        return aula.qrcode_imagem.path