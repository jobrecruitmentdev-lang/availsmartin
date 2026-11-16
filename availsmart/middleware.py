import time
from importlib import import_module
from django.conf import settings
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.exceptions import SessionInterrupted
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin
from django.utils.http import http_date


class DualSessionMiddleware(MiddlewareMixin):
    """
    Isolated Multi-Session Engine for AvailSmart.

    100% isolates Secret Admin Dashboard (/benzo/*) from Customer Storefront (/*):
    - Admin routes (/benzo/*): Dedicated cookie 'benzo_admin_session' with Path='/benzo/'.
      The browser's native security layer refuses to send this cookie to any storefront URL.
    - Customer Storefront (/*): Dedicated cookie 'avail_smart_session' with Path='/'.

    Zero session collision, zero automatic crossover across tabs, zero leakage of secret paths.
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        engine = import_module(settings.SESSION_ENGINE)
        self.SessionStore = engine.SessionStore

    def _get_cookie_config(self, request):
        path = request.path_info
        if path.startswith('/benzo'):
            return 'benzo_admin_session', '/benzo/'
        elif path.startswith('/django-admin') or path.startswith('/admin'):
            return 'benzo_admin_session', '/'
        customer_cookie = getattr(settings, 'CUSTOMER_SESSION_COOKIE_NAME', 'avail_smart_session')
        return customer_cookie, '/'

    def process_request(self, request):
        cookie_name, cookie_path = self._get_cookie_config(request)
        session_key = request.COOKIES.get(cookie_name)
        request.session = self.SessionStore(session_key)
        request._session_cookie_name = cookie_name
        request._session_cookie_path = cookie_path

    def process_response(self, request, response):
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            return response

        cookie_name = getattr(request, '_session_cookie_name', None)
        cookie_path = getattr(request, '_session_cookie_path', '/')
        if not cookie_name:
            cookie_name, cookie_path = self._get_cookie_config(request)

        # Silently purge legacy cookies from previous versions if present
        if 'sessionid' in request.COOKIES:
            response.delete_cookie('sessionid', path='/')
        if 'admin_sessionid' in request.COOKIES:
            response.delete_cookie('admin_sessionid', path='/')

        if cookie_name in request.COOKIES and empty:
            response.delete_cookie(
                cookie_name,
                path=cookie_path,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
            need_vary_cookie = True
        else:
            need_vary_cookie = accessed
            if (modified or settings.SESSION_SAVE_EVERY_REQUEST) and not empty:
                if request.session.get_expire_at_browser_close():
                    max_age = None
                    expires = None
                else:
                    max_age = request.session.get_expiry_age()
                    expires_time = time.time() + max_age
                    expires = http_date(expires_time)

                if response.status_code < 500:
                    try:
                        request.session.save()
                    except UpdateError:
                        raise SessionInterrupted(
                            "The request's session was deleted before the "
                            "request completed."
                        )
                    response.set_cookie(
                        cookie_name,
                        request.session.session_key,
                        max_age=max_age,
                        expires=expires,
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        path=cookie_path,
                        secure=settings.SESSION_COOKIE_SECURE or None,
                        httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                        samesite=settings.SESSION_COOKIE_SAMESITE,
                    )
                    need_vary_cookie = True

        if need_vary_cookie:
            patch_vary_headers(response, ("Cookie",))
        return response
