from io import BytesIO

from django.http import FileResponse, Http404, HttpResponse
from PIL import Image, ImageOps

from accounts.agrohub.client import AgroHubClient, AgroHubError


def profile_photo_response(user):
    if user.agrohub_id is not None:
        if not user.agrohub_foto_url:
            raise Http404
        try:
            raw = AgroHubClient().picture(user.agrohub_foto_url)
            with Image.open(BytesIO(raw)) as photo:
                if photo.format not in ('JPEG', 'PNG', 'WEBP') or photo.width*photo.height > 16_000_000:
                    raise Http404
                photo = ImageOps.exif_transpose(photo).convert('RGBA')
                photo.thumbnail((512, 512))
                out = BytesIO()
                photo.save(out, 'WEBP', quality=85)
            response = HttpResponse(out.getvalue(), content_type='image/webp')
        except (AgroHubError, OSError, ValueError, Image.DecompressionBombError):
            raise Http404 from None
    else:
        if not user.foto:
            raise Http404
        try:
            response = FileResponse(user.foto.open('rb'), content_type='image/webp')
        except OSError:
            raise Http404 from None
    response['X-Content-Type-Options'] = 'nosniff'
    return response
