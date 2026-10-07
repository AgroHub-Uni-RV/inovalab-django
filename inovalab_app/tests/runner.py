from django.core.management import call_command
from django.test.runner import DiscoverRunner


class SeededRunner(DiscoverRunner):
    """Tests exercise the same explicit bootstrap used for fresh installations."""
    def setup_databases(self, **kwargs):
        result = super().setup_databases(**kwargs)
        for connection, old_name, destroy in result:
            if destroy:
                call_command('seed_inovalab', database=connection.alias, verbosity=0)
        return result
