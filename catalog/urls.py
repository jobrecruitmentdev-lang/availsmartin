from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.home_view, name='home'),
    path('story/', views.story_view, name='story'),
    path('support/contact/', views.contact_view, name='contact'),
    path('support/faqs/', views.faqs_view, name='faqs'),
    path('legal/privacy/', views.privacy_view, name='privacy'),
    path('legal/terms/', views.terms_view, name='terms'),
    path('catalog/', views.catalog_view, name='listing'),
    path('catalog/category/<slug:slug>/', views.catalog_view, name='category_listing'),
    path('catalog/search/', views.search_view, name='search'),
    path('catalog/search/autocomplete/', views.search_autocomplete_view, name='search_autocomplete'),
    path('product/<slug:slug>/', views.product_detail_view, name='product_detail'),
    path('product/<slug:slug>/review/', views.add_review_view, name='add_review'),
    # Catch-all for category slug shortcut e.g. /catalog/smartphones/
    path('catalog/<slug:slug>/', views.catalog_view, name='category_slug_shortcut'),
]
