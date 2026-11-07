"""
URL configuration for AvailSmart project.
Routes user panel at '/' and secret admin panel at '/benzo/'.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from orders import views as order_views
from catalog import views as catalog_views

urlpatterns = [
    # SEO & Crawlers
    path('robots.txt', catalog_views.robots_txt_view, name='robots_txt'),
    path('sitemap.xml', catalog_views.sitemap_xml_view, name='sitemap_xml'),

    # Secret Custom AvailSmart Admin Panel (Cloaked at /benzo/)
    path('benzo/', include('dashboard.urls', namespace='dashboard')),
    
    # Internal Django admin (backup/system)
    path('django-admin/', admin.site.urls),
    
    # E-commerce core apps
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('cart/', include('cart.urls', namespace='cart')),
    path('checkout/', order_views.checkout_view, name='checkout_direct'),
    path('orders/', include('orders.urls', namespace='orders')),
    path('', include('catalog.urls', namespace='catalog')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
