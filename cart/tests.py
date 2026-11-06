import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from accounts.models import User
from catalog.models import Category, Brand, Product, ProductColor, ProductVariant
from cart.models import Cart, CartItem, Coupon


class CartPhase5Tests(TestCase):
    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(
            email='cartuser@test.com',
            name='Cart Tester',
            password='TestPassword123'
        )

        self.category = Category.objects.create(name='Tech', slug='tech', is_active=True)
        self.brand = Brand.objects.create(name='Apple', slug='apple', is_active=True)

        self.product = Product.objects.create(
            name='AirPods Pro 2',
            slug='airpods-pro-2',
            category=self.category,
            brand=self.brand,
            base_price=Decimal('24900.00'),
            discount_price=Decimal('19900.00'),
            sku='APP-2-BASE',
            is_active=True
        )
        self.color = ProductColor.objects.create(product=self.product, color_name='White', color_hex='#FFFFFF')
        self.variant = ProductVariant.objects.create(
            product=self.product,
            product_color=self.color,
            size='Standard',
            sku='APP-2-WHT',
            stock_quantity=10,
            is_active=True
        )

        # Coupons
        self.coupon_percent = Coupon.objects.create(
            code='SAVE10',
            discount_type='percent',
            value=Decimal('10.00'),
            min_order=Decimal('1000.00'),
            expiry=timezone.now() + timedelta(days=7),
            is_active=True
        )
        self.coupon_expired = Coupon.objects.create(
            code='OLD50',
            discount_type='percent',
            value=Decimal('50.00'),
            min_order=Decimal('0.00'),
            expiry=timezone.now() - timedelta(days=1),
            is_active=True
        )

    def test_add_to_cart_requires_login(self):
        """Unauthenticated guest cannot add items to cart."""
        res = self.client.post(
            reverse('cart:add_variant', kwargs={'variant_id': self.variant.id}),
            {'quantity': 1},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res.status_code, 401)
        data = json.loads(res.content)
        self.assertEqual(data['status'], 'unauthenticated')

    def test_add_to_cart_authenticated(self):
        """Authenticated user adds item to cart and cart total is updated."""
        self.client.login(email='cartuser@test.com', password='TestPassword123')
        res = self.client.post(
            reverse('cart:add_variant', kwargs={'variant_id': self.variant.id}),
            {'quantity': 2},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['cart_count'], 2)

        cart = Cart.objects.get(user=self.user)
        self.assertEqual(cart.total_items, 2)
        self.assertEqual(cart.subtotal, Decimal('39800.00'))

    def test_update_quantity(self):
        """Increment and decrement update item quantities and price totals."""
        self.client.login(email='cartuser@test.com', password='TestPassword123')
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)

        # Increment
        res1 = self.client.post(
            reverse('cart:update_quantity', kwargs={'item_id': item.id}),
            {'action': 'increment'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res1.status_code, 200)
        data1 = json.loads(res1.content)
        self.assertEqual(data1['quantity'], 3)
        self.assertEqual(data1['subtotal'], '59700.00')

        # Decrement
        res2 = self.client.post(
            reverse('cart:update_quantity', kwargs={'item_id': item.id}),
            {'action': 'decrement'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res2.status_code, 200)
        data2 = json.loads(res2.content)
        self.assertEqual(data2['quantity'], 2)

    def test_remove_cart_item(self):
        """Item is completely removed from cart."""
        self.client.login(email='cartuser@test.com', password='TestPassword123')
        cart = Cart.objects.create(user=self.user)
        item = CartItem.objects.create(cart=cart, variant=self.variant, quantity=1)

        res = self.client.post(
            reverse('cart:remove_item', kwargs={'item_id': item.id}),
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        self.assertTrue(data['is_empty'])
        self.assertEqual(cart.items.count(), 0)

    def test_apply_valid_coupon(self):
        """Valid coupon applies percentage discount to subtotal."""
        self.client.login(email='cartuser@test.com', password='TestPassword123')
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=1)  # Subtotal 19900

        res = self.client.post(
            reverse('cart:apply_coupon'),
            {'code': 'SAVE10'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['discount'], '1990.00')  # 10% of 19900
        self.assertEqual(data['total'], '17910.00')

    def test_apply_expired_coupon(self):
        """Expired coupon returns an error."""
        self.client.login(email='cartuser@test.com', password='TestPassword123')
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=1)

        res = self.client.post(
            reverse('cart:apply_coupon'),
            {'code': 'OLD50'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.content)
        self.assertIn('expired', data['message'])

    def test_cart_drawer_api(self):
        """Mini cart drawer API returns JSON representation of cart contents."""
        self.client.login(email='cartuser@test.com', password='TestPassword123')
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=1)

        res = self.client.get(reverse('cart:drawer_data'))
        self.assertEqual(res.status_code, 200)
        data = json.loads(res.content)
        self.assertEqual(data['cart_count'], 1)
        self.assertEqual(len(data['items']), 1)
        self.assertEqual(data['items'][0]['name'], 'AirPods Pro 2')
