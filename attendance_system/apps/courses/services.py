import qrcode
import io
from django.core.files.base import ContentFile
from django.conf import settings


class QRCodeService:
    @staticmethod
    def generate(aula):
        """Generate QR Code image for a given Aula instance."""
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
        aula.qrcode_imagem.save(filename, ContentFile(buffer.read()), save=True)

        return aula.qrcode_imagem.path
