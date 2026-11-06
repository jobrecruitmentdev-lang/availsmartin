import os
import sys

# Set up paths and environment
app_dir = os.path.dirname(__file__)
sys.path.insert(0, app_dir)

os.environ['DJANGO_SETTINGS_MODULE'] = 'availsmart.settings'

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
