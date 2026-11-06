import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from io import BytesIO
from PIL import Image

from accounts.models import User
from catalog.models import (
    Category, Brand, Product, ProductColor,
    ProductImage, ProductVariant, ProductSpecification,
    Review, Banner
)
from cart.models import Cart, CartItem, Wishlist


def create_test_image_file():
    file = BytesIO()
    image = Image.new('RGB', (100, 100), color=(4, 120, 87))
    image.save(file, 'PNG')
    file.seek(0)
    return SimpleUploadedFile("test_prod.png", file.read(), content_type="image/png")


class CatalogPhase4Tests(TestCase):
    def setUp(self):
        self.client = Client()

        # Users
        self.customer = User.objects.create_user(
            email='shopper@test.com',
            name='Test Shopper',
            password='ShopperPass123'
        )

        # Categories
        self.cat_electronics = Category.objects.create(name='Electronics', slug='electronics', is_active=True)
        self.cat_audio = Category.objects.create(name='Audio', slug='audio', parent=self.cat_electronics, is_active=True)
        self.cat_fashion = Category.objects.create(name='Fashion', slug='fashion', is_active=True)

        # Brands
        self.brand_sony = Brand.objects.create(name='Sony', slug='sony', is_active=True)
        self.brand_nike = Brand.objects.create(name='Nike', slug='nike', is_active=True)

        # Banners
        self.banner = Banner.objects.create(title='Summer Kickoff', link='/catalog/', sort_order=1, is_active=True)

        # Product 1: Sony Headphones (Audio -> Electronics)
        self.prod_headphones = Product.objects.create(
            name='Sony WH-1000XM5 Wireless Headphones',
            slug='sony-wh-1000xm5',
            category=self.cat_audio,
            brand=self.brand_sony,
            short_description='Flagship noise cancelling headphones',
            full_description='Industry-leading noise cancelation with two processors and 8 microphones.',
            base_price=Decimal('29990.00'),
            discount_price=Decimal('24990.00'),
            sku='SONY-XM5-BASE',
            is_featured=True,
            is_active=True,
            rating_avg=Decimal('4.80'),
            rating_count=12
        )
        self.col_black = ProductColor.objects.create(product=self.prod_headphones, color_name='Midnight Black', color_hex='#111111')
        self.col_silver = ProductColor.objects.create(product=self.prod_headphones, color_name='Platinum Silver', color_hex='#E5E7EB')

        self.img_black = ProductImage.objects.create(
            product_color=self.col_black,
            image=create_test_image_file(),
            is_primary=True
        )

        self.var_black = ProductVariant.objects.create(
            product=self.prod_headphones,
            product_color=self.col_black,
            size='Standard',
            sku='SONY-XM5-BLK',
            stock_quantity=15,
            is_active=True
        )
        self.var_silver = ProductVariant.objects.create(
            product=self.prod_headphones,
            product_color=self.col_silver,
            size='Standard',
            sku='SONY-XM5-SLV',
            stock_quantity=8,
            is_active=True
        )

        ProductSpecification.objects.create(product=self.prod_headphones, key='Battery Life', value='30 Hours')
        ProductSpecification.objects.create(product=self.prod_headphones, key='Weight', value='250 grams')

        # Product 2: Nike Sneakers (Fashion)
        self.prod_sneakers = Product.objects.create(
            name='Nike Air Max Tailwind Pulse',
            slug='nike-air-max-tailwind',
            category=self.cat_fashion,
            brand=self.brand_nike,
            short_description='Comfortable retro running sneakers',
            full_description='Breathable mesh upper with Air cushioning unit.',
            base_price=Decimal('7999.00'),
            discount_price=None,
            sku='NIKE-AM-BASE',
            is_featured=False,
            is_active=True,
            rating_avg=Decimal('4.20'),
            rating_count=5
        )
        self.col_white = ProductColor.objects.create(product=self.prod_sneakers, color_name='Summit White', color_hex='#FFFFFF')
        self.var_size_8 = ProductVariant.objects.create(
            product=self.prod_sneakers,
            product_color=self.col_white,
            size='UK 8',
            sku='NIKE-AM-WHT-8',
            stock_quantity=0,  # Out of stock
            is_active=True
        )
        self.var_size_9 = ProductVariant.objects.create(
            product=self.prod_sneakers,
            product_color=self.col_white,
            size='UK 9',
            sku='NIKE-AM-WHT-9',
            stock_quantity=4,  # In stock
            is_active=True
        )

    def test_home_view(self):
        """Home page renders successfully with banners, categories, and product highlights."""
        response = self.client.get(reverse('catalog:home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Smart Picks for Every Lifestyle')
        self.assertContains(response, 'Sony WH-1000XM5')
        self.assertIn('featured_products', response.context)
        self.assertIn('categories', response.context)
        self.assertIn('best_deals', response.context)

    def test_catalog_listing_unfiltered(self):
        """Catalog page lists all active products with pagination count."""
        response = self.client.get(reverse('catalog:listing'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sony WH-1000XM5')
        self.assertContains(response, 'Nike Air Max')
        self.assertEqual(response.context['total_count'], 2)

    def test_catalog_category_filtering(self):
        """Selecting a parent category includes products in that category and all its children."""
        # Electronics is parent of Audio -> Should find Sony Headphones
        response = self.client.get(f"{reverse('catalog:listing')}?category=electronics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 1)
        self.assertContains(response, 'Sony WH-1000XM5')
        self.assertNotContains(response, 'Nike Air Max')

        # Fashion category should find only Nike
        response_fashion = self.client.get(f"{reverse('catalog:listing')}?category=fashion")
        self.assertEqual(response_fashion.context['total_count'], 1)
        self.assertContains(response_fashion, 'Nike Air Max')

    def test_catalog_brand_filtering(self):
        """Filtering by brand slug returns only that brand's items."""
        response = self.client.get(f"{reverse('catalog:listing')}?brand=sony")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 1)
        self.assertContains(response, 'Sony WH-1000XM5')

    def test_catalog_price_filtering(self):
        """Price range filters products by effective selling price."""
        # Headphones cost 24990, Sneakers cost 7999
        response = self.client.get(f"{reverse('catalog:listing')}?min_price=1000&max_price=10000")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 1)
        self.assertContains(response, 'Nike Air Max')
        self.assertNotContains(response, 'Sony WH-1000XM5')

    def test_catalog_in_stock_filtering(self):
        """In-stock filter returns only products with variants having stock > 0."""
        response = self.client.get(f"{reverse('catalog:listing')}?in_stock=1")
        self.assertEqual(response.status_code, 200)
        # Both have at least one in-stock variant
        self.assertEqual(response.context['total_count'], 2)

    def test_catalog_ajax_filtering(self):
        """AJAX request returns JSON payload containing rendered HTML grid and count."""
        response = self.client.get(
            f"{reverse('catalog:listing')}?brand=sony&ajax=1",
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['total_count'], 1)
        self.assertIn('html', data)
        self.assertIn('Sony WH-1000XM5', data['html'])

    def test_search_autocomplete(self):
        """Autocomplete API returns matched products, categories, and brands as JSON."""
        response = self.client.get(f"{reverse('catalog:search_autocomplete')}?q=sony")
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(len(data['products']), 1)
        self.assertEqual(data['products'][0]['name'], 'Sony WH-1000XM5 Wireless Headphones')
        self.assertEqual(len(data['brands']), 1)
        self.assertEqual(data['brands'][0]['name'], 'Sony')

    def test_search_view(self):
        """Full search results page searches text fields and tags."""
        response = self.client.get(f"{reverse('catalog:search')}?q=headphones")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_count'], 1)
        self.assertContains(response, 'Sony WH-1000XM5')

    def test_product_detail_view(self):
        """Product detail page loads with gallery data, variant matrices, and specs."""
        response = self.client.get(reverse('catalog:product_detail', kwargs={'slug': 'sony-wh-1000xm5'}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Sony WH-1000XM5 Wireless Headphones')
        self.assertContains(response, 'Battery Life')
        self.assertContains(response, '30 Hours')
        self.assertIn('colors_json', response.context)
        self.assertIn('variants_json', response.context)

    def test_review_submission_unauthenticated(self):
        """Guest user cannot submit review directly without authentication."""
        url = reverse('catalog:add_review', kwargs={'slug': 'sony-wh-1000xm5'})
        response = self.client.post(url, {'rating': 5, 'comment': 'Terrific sound!'}, follow=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_review_submission_authenticated(self):
        """Authenticated user submits review, created with is_approved=False for moderation."""
        self.client.login(email='shopper@test.com', password='ShopperPass123')
        url = reverse('catalog:add_review', kwargs={'slug': 'sony-wh-1000xm5'})
        response = self.client.post(url, {'rating': 5, 'comment': 'Best ANC in the business!'}, follow=True)
        self.assertEqual(response.status_code, 200)
        review = Review.objects.filter(product=self.prod_headphones, user=self.customer).first()
        self.assertIsNotNone(review)
        self.assertEqual(review.rating, 5)
        self.assertFalse(review.is_approved)  # Must be moderated

    def test_quick_add_to_cart_requires_login(self):
        """Guest adding to cart via AJAX gets 401 unauthenticated with redirect URL."""
        response = self.client.post(
            reverse('cart:add_quick'),
            {'product_id': self.prod_headphones.id, 'quantity': 1},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 401)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'unauthenticated')
        self.assertIn('/accounts/login/', data['redirect_url'])

    def test_add_to_cart_authenticated(self):
        """Authenticated customer can add variant to cart."""
        self.client.login(email='shopper@test.com', password='ShopperPass123')
        response = self.client.post(
            reverse('cart:add_variant', kwargs={'variant_id': self.var_black.id}),
            {'quantity': 2},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['cart_count'], 2)
        cart = Cart.objects.get(user=self.customer)
        self.assertEqual(cart.total_items, 2)

    def test_toggle_wishlist(self):
        """Authenticated customer can add and remove items from wishlist."""
        self.client.login(email='shopper@test.com', password='ShopperPass123')
        url = reverse('cart:toggle_wishlist', kwargs={'product_id': self.prod_headphones.id})
        
        # Add to wishlist
        res1 = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res1.status_code, 200)
        data1 = json.loads(res1.content)
        self.assertEqual(data1['action'], 'added')
        self.assertEqual(data1['wishlist_count'], 1)
        self.assertTrue(Wishlist.objects.filter(user=self.customer, product=self.prod_headphones).exists())

        # Toggle again to remove
        res2 = self.client.post(url, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(res2.status_code, 200)
        data2 = json.loads(res2.content)
        self.assertEqual(data2['action'], 'removed')
        self.assertEqual(data2['wishlist_count'], 0)
        self.assertFalse(Wishlist.objects.filter(user=self.customer, product=self.prod_headphones).exists())
