def minute_value(value, original=None):
    """Edita em minutos sem alterar a precisão de um horário que foi mantido."""
    if value is None:
        return None
    value = value.replace(second=0, microsecond=0)
    if original is not None and value == original.replace(second=0, microsecond=0):
        return original
    return value
