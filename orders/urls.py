from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('checkout/', views.checkout_view, name='checkout'),
    path('send-otp/', views.send_order_otp_view, name='send_order_otp'),
    path('place/', views.place_order_view, name='place_order'),
    path('success/<str:order_number>/', views.order_success_view, name='order_success'),
    path('my-orders/', views.order_list_view, name='my_orders'),
    path('returns/', views.returns_policy_view, name='returns_policy'),
    path('track/', views.track_order_view, name='track_order'),
    path('<str:order_number>/', views.order_detail_view, name='order_detail'),
    path('<str:order_number>/cancel/', views.cancel_order_view, name='cancel_order'),
]
