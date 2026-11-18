import os
import sys
import traceback

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'availsmart.settings')

import django
django.setup()

from django.test import RequestFactory
from catalog.views import catalog_view

rf = RequestFactory()
request = rf.get('/catalog/', HTTP_HOST='availsmart.in')

# Setup session and user
from django.contrib.sessions.backends.db import SessionStore
request.session = SessionStore()
from django.contrib.auth.models import AnonymousUser
request.user = AnonymousUser()

try:
    response = catalog_view(request)
    print("STATUS:", response.status_code)
    if hasattr(response, 'render'):
        response.render()
        print("Render successful! Length:", len(response.content))
except Exception as e:
    print("EXCEPTION OCCURRED IN catalog_view:")
    traceback.print_exc()
