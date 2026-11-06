from django.urls import path
from . import views

app_name = 'cart'

urlpatterns = [
    path('', views.cart_detail_view, name='index'),
    path('add/<int:variant_id>/', views.add_to_cart_view, name='add_variant'),
    path('add/', views.add_to_cart_view, name='add_quick'),
    path('update/<int:item_id>/', views.update_quantity_view, name='update_quantity'),
    path('remove/<int:item_id>/', views.remove_cart_item_view, name='remove_item'),
    path('coupon/apply/', views.apply_coupon_view, name='apply_coupon'),
    path('coupon/remove/', views.remove_coupon_view, name='remove_coupon'),
    path('drawer/', views.cart_drawer_data_view, name='drawer_data'),
    path('wishlist/', views.wishlist_view, name='wishlist'),
    path('wishlist/toggle/<int:product_id>/', views.toggle_wishlist_view, name='toggle_wishlist'),
]
