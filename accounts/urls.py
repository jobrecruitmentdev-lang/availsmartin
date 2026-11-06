from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('verify-email/', views.verify_email_otp_view, name='verify_email'),
    path('resend-otp/', views.resend_otp_view, name='resend_otp'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('forgot-password/', views.forgot_password_view, name='forgot_password'),
    path('reset-password/<str:uidb64>/<str:token>/', views.reset_password_view, name='reset_password'),
    
    # Customer Profile & Address Book
    path('profile/', views.profile_view, name='profile'),
    path('addresses/', views.address_list_view, name='addresses'),
    path('addresses/add/', views.address_add_view, name='address_add'),
    path('addresses/<int:address_id>/edit/', views.address_edit_view, name='address_edit'),
    path('addresses/<int:address_id>/delete/', views.address_delete_view, name='address_delete'),
    path('addresses/<int:address_id>/default/', views.address_set_default_view, name='address_set_default'),
]
