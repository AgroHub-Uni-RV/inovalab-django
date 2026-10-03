import codecs
from decimal import Decimal, InvalidOperation

from django.conf import settings
from rest_framework.exceptions import ParseError
from rest_framework.parsers import JSONParser
from rest_framework.utils import json


class DecimalJSONParser(JSONParser):
    """Preserve the client's decimal digits until the serializer validates them."""

    def parse(self, stream, media_type=None, parser_context=None):
        encoding = (parser_context or {}).get('encoding', settings.DEFAULT_CHARSET)
        try:
            decoded_stream = codecs.getreader(encoding)(stream)
            parse_constant = json.strict_constant if self.strict else None
            return json.load(decoded_stream, parse_float=Decimal, parse_constant=parse_constant)
        except (ValueError, InvalidOperation) as error:
            raise ParseError('Informe um corpo JSON válido.') from error
