from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from accounts.models import EmailOTP, Address
from catalog.models import Category, Product, ProductColor, ProductVariant
from cart.models import Cart, CartItem
from orders.models import Order

User = get_user_model()


class OTPAuthenticationFlowTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.reg_data = {
            'name': 'Aarav Patel',
            'email': 'aarav.patel@example.com',
            'phone': '9876543210',
            'password': 'SecureCeramicPassword123!',
            'confirm_password': 'SecureCeramicPassword123!',
            'terms': True
        }

        # Setup product for checkout test
        self.cat = Category.objects.create(name='Bespoke Vases', slug='bespoke-vases')
        self.prod = Product.objects.create(
            name='Terracotta Artisan Vase',
            slug='terracotta-artisan-vase',
            category=self.cat,
            base_price=Decimal('2499.00')
        )
        self.color = ProductColor.objects.create(product=self.prod, color_name='Terracotta', color_hex='#C2714F')
        self.variant = ProductVariant.objects.create(
            product=self.prod,
            product_color=self.color,
            sku='VASE-TERRA-01',
            price=Decimal('2499.00'),
            stock_quantity=10
        )

    def test_registration_requires_email_otp_verification(self):
        """User registration creates inactive account and dispatches 6-digit OTP."""
        res = self.client.post(reverse('accounts:register'), self.reg_data)
        self.assertEqual(res.status_code, 302)
        self.assertRedirects(res, reverse('accounts:verify_email'))

        # User is created but inactive
        user = User.objects.filter(email='aarav.patel@example.com').first()
        self.assertIsNotNone(user)
        self.assertFalse(user.is_active)

        # 6-digit OTP is generated in EmailOTP
        otp_obj = EmailOTP.objects.filter(email=user.email, purpose='registration').first()
        self.assertIsNotNone(otp_obj)
        self.assertEqual(len(otp_obj.otp_code), 6)
        self.assertTrue(otp_obj.otp_code.isdigit())

        # Submitting wrong OTP fails
        res_wrong = self.client.post(reverse('accounts:verify_email'), {'otp_code': '000000'})
        self.assertEqual(res_wrong.status_code, 200)
        user.refresh_from_db()
        self.assertFalse(user.is_active)

        # Submitting correct OTP activates account and logs user in
        res_correct = self.client.post(reverse('accounts:verify_email'), {'otp_code': otp_obj.otp_code})
        self.assertEqual(res_correct.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_order_confirmation_with_email_otp(self):
        """Order placement verifies 6-digit confirmation OTP before finalizing order."""
        # Create verified customer
        user = User.objects.create_user(
            email='checkout.user@example.com',
            name='Priya Sharma',
            password='Password123!'
        )
        address = Address.objects.create(
            user=user,
            full_name='Priya Sharma',
            phone='9876543210',
            address_line1='Flat 101, Palm Grove',
            city='Mumbai',
            state='Maharashtra',
            pincode='400001',
            is_default=True
        )

        self.client.force_login(user)

        # Add item to cart
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=1)

        # Request order OTP via /orders/send-otp/
        res_send = self.client.post(reverse('orders:send_order_otp'), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res_send.status_code, 200)
        data = res_send.json()
        self.assertEqual(data['status'], 'success')

        # Verify OTP was created in database
        otp_record = EmailOTP.objects.filter(email=user.email, purpose='order_confirmation').first()
        self.assertIsNotNone(otp_record)
        self.assertEqual(len(otp_record.otp_code), 6)

        # Submitting with wrong OTP is rejected
        res_fail = self.client.post(reverse('orders:place_order'), {
            'address_id': address.id,
            'payment_method': 'cod',
            'otp_code': '999999'
        })
        self.assertEqual(res_fail.status_code, 302)
        self.assertEqual(Order.objects.filter(user=user).count(), 0)

        # Submitting with correct OTP succeeds
        res_success = self.client.post(reverse('orders:place_order'), {
            'address_id': address.id,
            'payment_method': 'cod',
            'otp_code': otp_record.otp_code
        })
        self.assertEqual(res_success.status_code, 302)
        self.assertEqual(Order.objects.filter(user=user).count(), 1)

        order = Order.objects.filter(user=user).first()
        self.assertEqual(order.total, Decimal('2499.00'))
        self.assertEqual(cart.items.count(), 0)

        # Stock quantity was decremented from 10 to 9
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 9)
