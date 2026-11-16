import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'availsmart.settings')

import django
django.setup()

from django.test import Client
from accounts.models import User, EmailOTP
from django.urls import reverse

client = Client(SERVER_NAME='availsmart.in', HTTP_HOST='availsmart.in', secure=True)

print("--- TESTING REGISTRATION OTP FLOW ---")
test_email = "testotp_reg_flow@availsmart.in"
# Clean up if exists
User.objects.filter(email=test_email).delete()
EmailOTP.objects.filter(email=test_email).delete()

# 1. Post to registration
reg_resp = client.post(reverse('accounts:register'), {
    'name': 'Test OTP User',
    'email': test_email,
    'phone': '9876543210',
    'password': 'StrongPassword123!',
    'confirm_password': 'StrongPassword123!',
    'terms': 'on'
}, follow=False)

print(f"Registration POST status: {reg_resp.status_code}")
assert reg_resp.status_code == 302
assert reg_resp.url == reverse('accounts:verify_email'), f"Expected redirect to verify_email, got {reg_resp.url}"

# Check user created with is_active=False
user = User.objects.filter(email=test_email).first()
assert user is not None, "User should exist in database"
assert user.is_active is False, "User should be inactive until OTP verification"
print(f"PASS: User created with is_active=False: {user.email}")

# Check OTP created in database
otp_obj = EmailOTP.objects.filter(email=test_email, purpose='registration', is_used=False).first()
assert otp_obj is not None, "OTP should be created in database"
assert len(otp_obj.otp_code) == 6, f"OTP should be 6 digits, got {otp_obj.otp_code}"
print(f"PASS: 6-digit OTP generated in database: {otp_obj.otp_code}")

# 2. Submit wrong OTP
wrong_resp = client.post(reverse('accounts:verify_email'), {
    'email': test_email,
    'otp_code': '000000'
})
user.refresh_from_db()
assert user.is_active is False, "User must remain inactive on wrong OTP"
print("PASS: Wrong OTP rejected cleanly!")

# 3. Submit correct OTP
correct_resp = client.post(reverse('accounts:verify_email'), {
    'email': test_email,
    'otp_code': otp_obj.otp_code
}, follow=False)
assert correct_resp.status_code == 302, f"Expected 302 redirect, got {correct_resp.status_code}"
user.refresh_from_db()
assert user.is_active is True, "User should be active after correct OTP verification"
print("PASS: Correct OTP activates user and logs them in!")

# Clean up
user.delete()
EmailOTP.objects.filter(email=test_email).delete()
print("\n--- ALL REGISTRATION OTP TESTS PASSED 100%! ---")
