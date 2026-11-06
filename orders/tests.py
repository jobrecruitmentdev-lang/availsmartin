import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User, Address
from catalog.models import Category, Brand, Product, ProductColor, ProductVariant
from cart.models import Cart, CartItem
from orders.models import Order, OrderItem, Payment


class OrdersPhase5Tests(TestCase):
    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(
            email='orderuser@test.com',
            name='Order Buyer',
            password='BuyerPassword123'
        )

        self.address = Address.objects.create(
            user=self.user,
            full_name='Order Buyer',
            phone='9876543210',
            address_line1='Flat 402, Green Meadows',
            address_line2='Indiranagar',
            city='Bengaluru',
            state='Karnataka',
            pincode='560038',
            country='India',
            address_type='home',
            is_default=True
        )

        self.category = Category.objects.create(name='Gadgets', slug='gadgets', is_active=True)
        self.brand = Brand.objects.create(name='Bose', slug='bose', is_active=True)

        self.product = Product.objects.create(
            name='Bose QuietComfort 45',
            slug='bose-qc45',
            category=self.category,
            brand=self.brand,
            base_price=Decimal('29900.00'),
            discount_price=Decimal('25900.00'),
            sku='BOSE-QC-BASE',
            is_active=True
        )
        self.color = ProductColor.objects.create(product=self.product, color_name='Triple Black', color_hex='#000000')
        self.variant = ProductVariant.objects.create(
            product=self.product,
            product_color=self.color,
            size='Standard',
            sku='BOSE-QC-BLK',
            stock_quantity=5,
            is_active=True
        )

    def test_checkout_redirects_if_cart_empty(self):
        """Visiting checkout with an empty cart redirects to cart view."""
        self.client.login(email='orderuser@test.com', password='BuyerPassword123')
        res = self.client.get(reverse('orders:checkout'))
        self.assertEqual(res.status_code, 302)
        self.assertIn('/cart/', res.url)

    def test_checkout_page_renders_with_items(self):
        """Checkout page displays user's saved addresses and order items."""
        self.client.login(email='orderuser@test.com', password='BuyerPassword123')
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=1)

        res = self.client.get(reverse('orders:checkout'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Flat 402, Green Meadows')
        self.assertContains(res, 'Bose QuietComfort 45')

    def test_place_order_with_existing_address(self):
        """Placing order with saved address creates Order, decrements stock, and empties cart."""
        self.client.login(email='orderuser@test.com', password='BuyerPassword123')
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=2)

        initial_stock = self.variant.stock_quantity  # 5

        res = self.client.post(reverse('orders:place_order'), {
            'address_id': self.address.id,
            'payment_method': 'cod',
            'order_notes': 'Please ring the doorbell'
        })
        self.assertEqual(res.status_code, 302)

        order = Order.objects.filter(user=self.user).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.total, Decimal('51800.00'))  # 25900 * 2
        self.assertEqual(order.payment_method, 'cod')
        self.assertEqual(order.shipping_address_snapshot['city'], 'Bengaluru')

        # Stock should be decremented from 5 to 3
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, initial_stock - 2)

        # Cart should now be empty
        self.assertEqual(cart.items.count(), 0)

        # Payment record should exist
        payment = Payment.objects.filter(order=order).first()
        self.assertIsNotNone(payment)
        self.assertEqual(payment.amount, order.total)

    def test_place_order_with_new_address(self):
        """Placing order with inline new address saves address and places order."""
        self.client.login(email='orderuser@test.com', password='BuyerPassword123')
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(cart=cart, variant=self.variant, quantity=1)

        res = self.client.post(reverse('orders:place_order'), {
            'address_id': 'new',
            'new_full_name': 'New Recipient',
            'new_phone': '9123456789',
            'new_address_line1': 'Tech Park 5B',
            'new_city': 'Pune',
            'new_state': 'Maharashtra',
            'new_pincode': '411001',
            'new_address_type': 'work',
            'save_address': '1',
            'payment_method': 'cod'
        })
        self.assertEqual(res.status_code, 302)

        # Confirm new address saved
        saved_addr = Address.objects.filter(user=self.user, city='Pune').first()
        self.assertIsNotNone(saved_addr)
        self.assertEqual(saved_addr.full_name, 'New Recipient')

        # Confirm order placed with Pune address
        order = Order.objects.filter(user=self.user, shipping_address_snapshot__city='Pune').first()
        self.assertIsNotNone(order)

    def test_order_detail_and_cancellation(self):
        """Customer can view order details and cancel order, restoring stock."""
        self.client.login(email='orderuser@test.com', password='BuyerPassword123')
        
        # Create an order
        order = Order.objects.create(
            user=self.user,
            shipping_address_snapshot={'full_name': 'Test', 'city': 'Delhi'},
            subtotal=Decimal('25900.00'),
            total=Decimal('25900.00'),
            order_status='confirmed'
        )
        OrderItem.objects.create(
            order=order,
            variant=self.variant,
            product_name_snapshot=self.product.name,
            price_snapshot=Decimal('25900.00'),
            quantity=1
        )
        initial_stock = self.variant.stock_quantity

        # Detail view
        detail_res = self.client.get(reverse('orders:order_detail', kwargs={'order_number': order.order_number}))
        self.assertEqual(detail_res.status_code, 200)
        self.assertContains(detail_res, order.order_number)

        # Cancel order
        cancel_res = self.client.post(reverse('orders:cancel_order', kwargs={'order_number': order.order_number}))
        self.assertEqual(cancel_res.status_code, 302)

        order.refresh_from_db()
        self.assertEqual(order.order_status, 'cancelled')

        # Stock restored
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, initial_stock + 1)
