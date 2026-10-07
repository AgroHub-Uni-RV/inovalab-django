from io import BytesIO
import warnings

from PIL import Image, UnidentifiedImageError
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile


def validated_image(upload):
    if not isinstance(upload, UploadedFile):
        raise ValidationError({'banner_img': 'Envie um arquivo WebP.'})
    upload.seek(0)
    data = upload.read(5 * 1024 * 1024 + 1)
    upload.seek(0)
    if not data or len(data) > 5 * 1024 * 1024:
        raise ValidationError({'banner_img': 'A imagem deve ter até 5 MiB.'})
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                if image.format != 'WEBP' or getattr(image, 'is_animated', False):
                    raise ValidationError({'banner_img': 'Use uma imagem WebP estática.'})
                if image.width > 4096 or image.height > 4096:
                    raise ValidationError({'banner_img': 'Use dimensões de até 4096 × 4096 pixels.'})
                image.load()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise ValidationError({'banner_img': 'O arquivo não é uma imagem WebP válida.'}) from error
    return ContentFile(data)
