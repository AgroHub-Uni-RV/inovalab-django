from django.test.client import closing_iterator_wrapper


def close_response(response):
    """Use the test client's signal-safe close; TestCase owns its transaction."""
    for _ in closing_iterator_wrapper((), response.close):
        pass
