"""Minimal separate host: native auth.User, no accounts app or AgroHub settings."""
SECRET_KEY = 'test-host-only'
DEBUG = True
ALLOWED_HOSTS = ['testserver', 'localhost', '127.0.0.1']
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions',
                  'django.contrib.messages', 'django.contrib.staticfiles', 'rest_framework',
                  'inovalab_app.apps.InovalabConfig']
AUTH_USER_MODEL = 'auth.User'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}}
ROOT_URLCONF = 'inovalab_app.tests.host_urls'
LOGIN_URL = '/entrar/'
INOVALAB_HOST_ADAPTER = 'inovalab_app.adapters.django.DjangoHostAdapter'
MIDDLEWARE = ['django.contrib.sessions.middleware.SessionMiddleware',
              'django.contrib.auth.middleware.AuthenticationMiddleware',
              'django.middleware.csrf.CsrfViewMiddleware',
              'django.contrib.messages.middleware.MessageMiddleware',
              'inovalab_app.shared.middleware.InovalabAccessMiddleware']
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'APP_DIRS': True,
              'OPTIONS': {'context_processors': ['django.template.context_processors.request',
                                                'django.contrib.auth.context_processors.auth',
                                                'django.contrib.messages.context_processors.messages',
                                                'inovalab_app.shared.navigation.panel_navigation',
                                                'inovalab_app.adapters.host.identity_context']}}]
USE_TZ = True
TIME_ZONE = 'America/Sao_Paulo'
STATIC_URL = '/static/'
MEDIA_ROOT = ''
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
TEST_RUNNER = 'inovalab_app.tests.runner.SeededRunner'
