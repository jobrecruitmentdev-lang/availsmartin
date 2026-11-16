import os
import sys
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'availsmart.settings')

import django
django.setup()

from django.test import Client
from accounts.models import User, Address, EmailOTP
from catalog.models import Product, Category
from cart.models import Cart, CartItem
from orders.models import Order
from django.urls import reverse

client = Client(SERVER_NAME='availsmart.in', HTTP_HOST='availsmart.in', secure=True)

print("--- TESTING CHECKOUT OTP FLOW ---")
test_email = "testotp_checkout_flow@availsmart.in"
User.objects.filter(email=test_email).delete()
EmailOTP.objects.filter(email=test_email).delete()

user = User.objects.create_user(
    email=test_email,
    password='StrongPassword123!',
    name='Checkout Tester',
    is_active=True
)

address = Address.objects.create(
    user=user,
    full_name='Checkout Tester',
    phone='9876543210',
    address_line1='123 Royal Palace Road',
    city='Mumbai',
    state='Maharashtra',
    pincode='400001',
    is_default=True
)

from catalog.models import ProductVariant

var = ProductVariant.objects.filter(is_active=True, stock_quantity__gt=0).first()
assert var is not None, "ProductVariant should exist in database"

cart, _ = Cart.objects.get_or_create(user=user)
CartItem.objects.all().filter(cart=cart).delete()
CartItem.objects.create(
    cart=cart,
    variant=var,
    quantity=1
)

client.force_login(user)

# 1. Send checkout OTP
send_resp = client.post(reverse('orders:send_order_otp'), HTTP_X_REQUESTED_WITH='XMLHttpRequest', secure=True)
print(f"send_order_otp response status: {send_resp.status_code}")
assert send_resp.status_code == 200
data = send_resp.json()
assert data.get('status') == 'success'
print("PASS: send_order_otp dispatched successfully via Hostinger SMTP!")

otp_obj = EmailOTP.objects.filter(email=test_email, purpose='order_confirmation', is_used=False).first()
assert otp_obj is not None
print(f"PASS: Order confirmation OTP generated: {otp_obj.otp_code}")

# 2. Place order without OTP -> Rejected!
no_otp_resp = client.post(reverse('orders:place_order'), {
    'address_id': str(address.id),
    'payment_method': 'cod',
    'otp_code': ''
}, secure=True, follow=False)
assert no_otp_resp.status_code == 302
assert no_otp_resp.url == reverse('orders:checkout')
print("PASS: Order placement WITHOUT OTP was blocked successfully!")

# 3. Place order with WRONG OTP -> Rejected!
wrong_otp_resp = client.post(reverse('orders:place_order'), {
    'address_id': str(address.id),
    'payment_method': 'cod',
    'otp_code': '000000'
}, secure=True, follow=False)
assert wrong_otp_resp.status_code == 302
assert wrong_otp_resp.url == reverse('orders:checkout')
print("PASS: Order placement with WRONG OTP was blocked successfully!")

# 4. Place order with CORRECT OTP -> Succeeded!
correct_otp_resp = client.post(reverse('orders:place_order'), {
    'address_id': str(address.id),
    'payment_method': 'cod',
    'otp_code': otp_obj.otp_code
}, secure=True, follow=False)
assert correct_otp_resp.status_code == 302
assert 'order-success' in correct_otp_resp.url or 'success' in correct_otp_resp.url or '/orders/' in correct_otp_resp.url
print(f"PASS: Order placed successfully with valid OTP! Redirect: {correct_otp_resp.url}")

# Verify order in DB
order = Order.objects.filter(user=user).order_by('-created_at').first()
assert order is not None
print(f"PASS: Order created in DB: Order ID #{order.order_number}, Total: Rs.{order.total}")

# Clean up
order.items.all().delete()
order.delete()
user.delete()
EmailOTP.objects.filter(email=test_email).delete()

print("\n--- ALL CHECKOUT OTP TESTS PASSED 100%! ---")
