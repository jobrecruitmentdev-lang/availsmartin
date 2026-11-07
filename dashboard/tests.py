from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from decimal import Decimal
from accounts.models import User
from catalog.models import Category, Brand, Product, ProductColor, ProductImage, ProductVariant, Review, Banner
from cart.models import Coupon
from orders.models import Order, OrderItem


class AdminPanelCrudTests(TestCase):
    def setUp(self):
        self.client = Client()
        # 1. Staff Admin
        self.admin = User.objects.create_superuser(
            email='admin@availsmart.com',
            name='Avail Admin',
            password='AdminPassword@123'
        )
        # 2. Customer
        self.customer = User.objects.create_user(
            email='customer@example.com',
            name='Test Customer',
            password='CustomerPassword@123'
        )
        # 3. Sample Category & Brand
        self.category = Category.objects.create(name='Electronics', slug='electronics', is_active=True)
        self.brand = Brand.objects.create(name='Sony', slug='sony', is_active=True)

        # Log in as admin
        self.client.login(email='admin@availsmart.com', password='AdminPassword@123')

    def test_dashboard_overview_metrics(self):
        response = self.client.get(reverse('dashboard:index'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Operations Overview')
        self.assertContains(response, 'salesTrendsChart')
        self.assertIn('chart_labels_json', response.context)
        self.assertIn('chart_sales_json', response.context)

    def test_non_staff_blocked(self):
        customer_client = Client()
        customer_client.login(email='customer@example.com', password='CustomerPassword@123')
        response = customer_client.get(reverse('dashboard:index'))
        self.assertRedirects(response, '/benzo/login/?next=/benzo/')

    def test_category_crud(self):
        # 1. Add Category
        add_res = self.client.post(reverse('dashboard:category_add'), {
            'name': 'Wireless Audio',
            'parent': self.category.id,
            'description': 'Headphones and speakers',
            'sort_order': 1,
            'is_active': True,
        }, follow=True)
        self.assertEqual(add_res.status_code, 200)
        subcat = Category.objects.get(name='Wireless Audio')
        self.assertEqual(subcat.parent, self.category)

        # 2. Edit Category
        edit_res = self.client.post(reverse('dashboard:category_edit', args=[subcat.id]), {
            'name': 'Wireless Audio & Hi-Fi',
            'parent': self.category.id,
            'description': 'Updated description',
            'sort_order': 2,
            'is_active': True,
        }, follow=True)
        self.assertEqual(edit_res.status_code, 200)
        subcat.refresh_from_db()
        self.assertEqual(subcat.name, 'Wireless Audio & Hi-Fi')

        # 3. Delete Category
        del_res = self.client.post(reverse('dashboard:category_delete', args=[subcat.id]), follow=True)
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(Category.objects.filter(name='Wireless Audio & Hi-Fi').exists())

    def test_brand_crud(self):
        # 1. Add Brand
        add_res = self.client.post(reverse('dashboard:brand_add'), {
            'name': 'Samsung',
            'is_active': True
        }, follow=True)
        self.assertEqual(add_res.status_code, 200)
        samsung = Brand.objects.get(name='Samsung')

        # 2. Edit Brand
        edit_res = self.client.post(reverse('dashboard:brand_edit', args=[samsung.id]), {
            'name': 'Samsung Electronics',
            'is_active': True
        }, follow=True)
        self.assertEqual(edit_res.status_code, 200)
        samsung.refresh_from_db()
        self.assertEqual(samsung.name, 'Samsung Electronics')

        # 3. Delete Brand
        del_res = self.client.post(reverse('dashboard:brand_delete', args=[samsung.id]), follow=True)
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(Brand.objects.filter(name='Samsung Electronics').exists())

    def test_product_create_with_dynamic_colors_images_variants_and_specs(self):
        # Fake image file
        image_content = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        dummy_img1 = SimpleUploadedFile("angle1.gif", image_content, content_type="image/gif")
        dummy_img2 = SimpleUploadedFile("angle2.gif", image_content, content_type="image/gif")

        post_data = {
            'name': 'WH-1000XM5 Noise Cancelling Headphones',
            'category': self.category.id,
            'brand': self.brand.id,
            'base_price': '29990.00',
            'discount_price': '24990.00',
            'sku': 'SONY-XM5-TEST',
            'weight': '0.25',
            'weight_unit': 'kg',
            'length': '20',
            'width': '18',
            'height': '8',
            'material': 'Recycled Plastic & Leatherette',
            'tags': 'headphones, wireless, sony',
            'short_description': 'Industry leading noise canceling headphones',
            'full_description': '30 hours battery, dual processors, 8 microphones.',
            'is_featured': True,
            'is_active': True,
            'meta_title': 'Sony WH-1000XM5 Buy Online',
            'meta_description': 'Best ANC headphones',
            # Dynamic Specifications
            'spec_keys[]': ['Driver Size', 'Battery Life'],
            'spec_values[]': ['30mm Carbon Fiber', '30 Hours'],
            # Dynamic Colors (2 Colors)
            'color_count': 2,
            # Color 0: Silver
            'color_name_0': 'Platinum Silver',
            'color_hex_0': '#E2E8F0',
            'color_images_0': [dummy_img1],
            'primary_image_0': '0',
            'variant_size_0[]': ['Standard'],
            'variant_sku_0[]': ['SONY-XM5-SLV'],
            'variant_price_0[]': ['24990.00'],
            'variant_stock_0[]': ['30'],
            # Color 1: Black
            'color_name_1': 'Midnight Black',
            'color_hex_1': '#111827',
            'color_images_1': [dummy_img2],
            'primary_image_1': '0',
            'variant_size_1[]': ['Standard'],
            'variant_sku_1[]': ['SONY-XM5-BLK'],
            'variant_price_1[]': ['24990.00'],
            'variant_stock_1[]': ['45'],
        }

        response = self.client.post(reverse('dashboard:product_add'), post_data, follow=True)
        self.assertEqual(response.status_code, 200)

        # Verify created product
        product = Product.objects.get(sku='SONY-XM5-TEST')
        self.assertEqual(product.name, 'WH-1000XM5 Noise Cancelling Headphones')
        self.assertEqual(product.discount_percent, 17)  # (29990 - 24990) / 29990 = ~16.67% -> 17%
        self.assertEqual(product.specifications.count(), 2)
        self.assertEqual(product.colors.count(), 2)
        self.assertEqual(product.variants.count(), 2)
        self.assertEqual(product.total_stock, 75)

    def test_product_bulk_actions(self):
        prod1 = Product.objects.create(
            name='Prod 1', slug='prod-1', category=self.category, base_price=Decimal('100'), sku='P1', is_active=True
        )
        prod2 = Product.objects.create(
            name='Prod 2', slug='prod-2', category=self.category, base_price=Decimal('200'), sku='P2', is_active=True
        )

        # Deactivate
        self.client.post(reverse('dashboard:product_bulk_action'), {
            'bulk_action': 'deactivate',
            'selected_products[]': [prod1.id, prod2.id]
        }, follow=True)
        prod1.refresh_from_db()
        prod2.refresh_from_db()
        self.assertFalse(prod1.is_active)
        self.assertFalse(prod2.is_active)

        # Delete
        self.client.post(reverse('dashboard:product_bulk_action'), {
            'bulk_action': 'delete',
            'selected_products[]': [prod1.id]
        }, follow=True)
        self.assertFalse(Product.objects.filter(id=prod1.id).exists())
        self.assertTrue(Product.objects.filter(id=prod2.id).exists())

    def test_orders_management(self):
        order = Order.objects.create(
            user=self.customer,
            shipping_address_snapshot={'full_name': 'Test Customer', 'city': 'Bengaluru', 'pincode': '560103'},
            subtotal=Decimal('5000.00'),
            total=Decimal('5000.00'),
            payment_method='cod',
            payment_status='pending',
            order_status='pending'
        )

        # 1. View detail
        detail_res = self.client.get(reverse('dashboard:order_detail', args=[order.id]))
        self.assertEqual(detail_res.status_code, 200)
        self.assertContains(detail_res, order.order_number)

        # 2. Update status & tracking
        status_res = self.client.post(reverse('dashboard:order_change_status', args=[order.id]), {
            'order_status': 'shipped',
            'payment_status': 'completed',
            'shipping_partner': 'BlueDart',
            'tracking_number': 'BLU123456789'
        }, follow=True)
        self.assertEqual(status_res.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.order_status, 'shipped')
        self.assertEqual(order.shipping_partner, 'BlueDart')
        self.assertIsNotNone(order.shipped_at)

        # 3. Printable Invoice
        inv_res = self.client.get(reverse('dashboard:order_invoice', args=[order.id]))
        self.assertEqual(inv_res.status_code, 200)
        self.assertContains(inv_res, 'Tax Invoice')

    def test_reviews_moderation(self):
        product = Product.objects.create(
            name='Review Test Prod', slug='review-test', category=self.category, base_price=Decimal('500'), sku='REV1'
        )
        review = Review.objects.create(
            user=self.customer,
            product=product,
            rating=5,
            comment='Superb sound quality!',
            is_approved=False
        )

        # 1. Approve review
        approve_res = self.client.post(reverse('dashboard:review_approve', args=[review.id]), follow=True)
        self.assertEqual(approve_res.status_code, 200)
        review.refresh_from_db()
        self.assertTrue(review.is_approved)

        # 2. Delete review
        del_res = self.client.post(reverse('dashboard:review_delete', args=[review.id]), follow=True)
        self.assertEqual(del_res.status_code, 200)
        self.assertFalse(Review.objects.filter(id=review.id).exists())

    def test_coupons_and_banners_crud(self):
        # 1. Coupon create & delete
        c_res = self.client.post(reverse('dashboard:coupon_add'), {
            'code': 'TEST25',
            'discount_type': 'percent',
            'value': '25.00',
            'min_order': '500.00',
            'expiry': '2027-12-31T23:59',
            'usage_limit': 100,
            'is_active': True,
        }, follow=True)
        self.assertEqual(c_res.status_code, 200)
        coupon = Coupon.objects.get(code='TEST25')
        self.assertEqual(coupon.value, Decimal('25.00'))

        # Delete coupon
        self.client.post(reverse('dashboard:coupon_delete', args=[coupon.id]), follow=True)
        self.assertFalse(Coupon.objects.filter(code='TEST25').exists())

        # 2. Banner create & delete
        from io import BytesIO
        from PIL import Image
        buf = BytesIO()
        Image.new('RGB', (200, 100), color='#047857').save(buf, format='PNG')
        buf.seek(0)
        banner_img = SimpleUploadedFile("banner.png", buf.read(), content_type="image/png")
        b_res = self.client.post(reverse('dashboard:banner_add'), {
            'title': 'Test Promotional Banner',
            'subtitle': 'Big discounts',
            'image': banner_img,
            'link': '/catalog/',
            'sort_order': 0,
            'is_active': True,
        }, follow=True)
        self.assertEqual(b_res.status_code, 200)
        banner = Banner.objects.get(title='Test Promotional Banner')

        # Delete banner
        self.client.post(reverse('dashboard:banner_delete', args=[banner.id]), follow=True)
        self.assertFalse(Banner.objects.filter(title='Test Promotional Banner').exists())
