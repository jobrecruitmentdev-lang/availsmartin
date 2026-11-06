import os
import io
import urllib.request
from decimal import Decimal
from PIL import Image, ImageDraw, ImageFont

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import slugify
from django.conf import settings

from accounts.models import User
from catalog.models import (
    Category, Brand, Product, ProductColor, ProductImage,
    ProductVariant, ProductSpecification, Review, Banner
)
from cart.models import Coupon


# Verified high-resolution ceramic photography pool from Unsplash
CERAMIC_PHOTO_POOL = [
    'photo-1610701596007-11502861dcfa',  # Ceramic tableware set on neutral linen
    'photo-1578749556568-bc2c40e68b61',  # Ceramic vases & tableware studio
    'photo-1616401784845-180882ba9ba8',  # Stoneware plate setting
    'photo-1590736969955-71cc94801759',  # Handcrafted ceramic cups
    'photo-1565193566173-7a0ee3dbe261',  # Minimalist white ceramic teapot
    'photo-1514432324607-a09d9b4aefdd',  # Stoneware coffee mug
    'photo-1581783342308-f792dbdd27c5',  # Stack of handmade ceramic plates
    'photo-1544816155-12df9643f363',  # Terracotta pot and earthen bowl
    'photo-1628088062854-d1870b4553da',  # Handmade ceramic bowls and wooden spoons
    'photo-1589365278144-c9e705f843ba',  # Matte black ceramic plates
    'photo-1615486511484-92e172cc4fe0',  # Tableware dining setup
    'photo-1603561591411-07134e71a2a9',  # Ceramic pitcher & mugs
    'photo-1596040033229-a9821ebd058d',  # Speckled stoneware bowl
    'photo-1604014237800-1c9102c219da',  # Glazed dinner plate setting
    'photo-1584269600464-37b1b58a9fe7',  # Artisan clay pottery bowls
    'photo-1577083552431-6e5fd01aa342',  # Stoneware dinnerware on linen
    'photo-1506377247377-2a5b3b417ebb',  # Pour-over ceramic dripper
    'photo-1526434426615-1abe81efcb0b',  # Matte terracotta vase
    'photo-1592150621744-aca64f48394a',  # Ceramic tea ceremony set
    'photo-1517256064527-09c73fc73e38',  # Minimalist cup & saucer
    'photo-1586023492125-27b2c045efd7',  # Ceramic sculptural vase in room
    'photo-1563861826100-9cb868fdbe1c',  # Potter shaping stoneware wheel
    'photo-1612196808214-b8e1d6145a8c',  # Earth-tone stoneware plates
    'photo-1607522370275-f14206abe5d3',  # Deep ceramic noodle bowl
    'photo-1567684014761-b65e2e59b9eb',  # Artisanal stoneware collection
]


def create_pro_fallback_ceramic_image(title, subtitle, bg_color='#FAF8F5', accent_color='#C2714F', width=800, height=1000):
    """
    Generates an artistic 4:5 vertical portrait WebP image with smooth ceramic gradients,
    studio rim-lighting and luxury typography if internet fetch fails.
    """
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Ceramic vase / vessel silhouette in center
    cx, cy = width // 2, height // 2 - 40
    # Soft background studio glow
    draw.ellipse([cx - 220, cy - 220, cx + 220, cy + 220], fill='#F0EBE1', outline='#E6DFD3', width=2)
    # Vessel body
    draw.polygon([
        (cx - 90, cy + 160),
        (cx + 90, cy + 160),
        (cx + 140, cy + 30),
        (cx + 60, cy - 130),
        (cx - 60, cy - 130),
        (cx - 140, cy + 30),
    ], fill=accent_color)
    # Vessel neck & rim
    draw.rectangle([cx - 50, cy - 170, cx + 50, cy - 125], fill=accent_color)
    draw.ellipse([cx - 55, cy - 180, cx + 55, cy - 160], fill='#FAF8F5', outline=accent_color, width=4)
    # Vessel base shadow
    draw.ellipse([cx - 120, cy + 155, cx + 120, cy + 175], fill='#D9D0C3')

    # Border & Studio Branding
    draw.rectangle([25, 25, width - 25, height - 25], outline='#E8E4DC', width=2)
    draw.text((40, 40), "CROOKERIES STUDIO", fill='#8A8477')
    draw.text((40, height - 80), title.upper()[:35], fill='#14241B')
    draw.text((40, height - 55), subtitle[:45], fill='#8A8477')

    buf = io.BytesIO()
    img.save(buf, format='WEBP', quality=85, optimize=True)
    buf.seek(0)
    return ContentFile(buf.read())


def fetch_and_crop_ceramic_image(photo_id, title="Crookeries", subtitle="Artisanal Stoneware", target_w=800, target_h=1000):
    """
    Fetches genuine high-res ceramic photo from Unsplash, crops to 4:5 vertical portrait,
    and returns a ContentFile in WebP format. Falls back gracefully to artistic drawing.
    """
    url = f"https://images.unsplash.com/{photo_id}?w=1000&auto=format&fit=crop&q=80"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status == 200:
                img_data = response.read()
                img = Image.open(io.BytesIO(img_data)).convert('RGB')

                # Crop strictly to 4:5 portrait
                w, h = img.size
                target_ratio = 4.0 / 5.0
                current_ratio = w / h

                if current_ratio > target_ratio:
                    new_w = int(h * target_ratio)
                    left = (w - new_w) // 2
                    img = img.crop((left, 0, left + new_w, h))
                else:
                    new_h = int(w / target_ratio)
                    top = (h - new_h) // 2
                    img = img.crop((0, top, w, top + new_h))

                img = img.resize((target_w, target_h), Image.Resampling.LANCZOS)

                buf = io.BytesIO()
                img.save(buf, format='WEBP', quality=85, optimize=True)
                buf.seek(0)
                return ContentFile(buf.read())
    except Exception as e:
        print(f"  [Fallback Pillow Image Used for {photo_id}]: {e}")

    # Fallback if download times out or 404s
    return create_pro_fallback_ceramic_image(title, subtitle, width=target_w, height=target_h)


class Command(BaseCommand):
    help = 'Seeds database with 28 rich luxury Crookeries ceramic products, categories, artisan brands, 4:5 WebP imagery, variants, and reviews.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("===> Initiating Crookeries Luxury Ceramic Catalog Seeding..."))

        # ---------------------------------------------------------
        # 1. CLEAN PREVIOUS GENERIC PRODUCTS & CATEGORIES
        # ---------------------------------------------------------
        self.stdout.write("1. Cleaning old non-ceramic catalog records...")
        ProductSpecification.objects.all().delete()
        Review.objects.all().delete()
        ProductVariant.objects.all().delete()
        ProductImage.objects.all().delete()
        ProductColor.objects.all().delete()
        Product.objects.all().delete()
        Category.objects.all().delete()
        Brand.objects.all().delete()
        Banner.objects.all().delete()

        # ---------------------------------------------------------
        # 2. SEED REAL ARTISANAL BRANDS
        # ---------------------------------------------------------
        self.stdout.write("2. Seeding Artisanal Pottery Studios & Guilds...")
        brands_data = [
            {'name': 'Khurja Heritage Atelier', 'slug': 'khurja-atelier'},
            {'name': 'Jaipur Clayworks', 'slug': 'jaipur-clayworks'},
            {'name': 'Hasami Studio Guild', 'slug': 'hasami-studio'},
            {'name': 'Nordic Klay Pottery', 'slug': 'nordic-klay'},
            {'name': 'Wabi Earthen Crafts', 'slug': 'wabi-earthen'},
            {'name': 'Terra Oribe Atelier', 'slug': 'terra-oribe'},
        ]
        brand_map = {}
        for b_info in brands_data:
            brand, _ = Brand.objects.get_or_create(
                slug=b_info['slug'],
                defaults={'name': b_info['name'], 'is_active': True}
            )
            brand_map[b_info['slug']] = brand

        # ---------------------------------------------------------
        # 3. SEED REAL CERAMIC CATEGORIES & SUBCATEGORIES
        # ---------------------------------------------------------
        self.stdout.write("3. Seeding Dedicated Ceramic Category Hierarchy...")
        categories_structure = [
            {
                'name': 'Dinnerware & Plates',
                'slug': 'dinnerware-plates',
                'desc': 'Hand-thrown stoneware dinner plates, fluted pasta bowls, raw edge salad plates, and banquet charger platters.',
                'children': [
                    {'name': 'Dinner Plates', 'slug': 'dinner-plates'},
                    {'name': 'Pasta & Salad Bowls', 'slug': 'pasta-salad-plates'},
                    {'name': 'Complete Dinner Sets', 'slug': 'complete-dinner-sets'},
                ]
            },
            {
                'name': 'Bowls & Dining',
                'slug': 'bowls-dining',
                'desc': 'Deep ramen noodle bowls, cereal bowls, tapas pinch bowls, and stoneware mixing terrines.',
                'children': [
                    {'name': 'Ramen & Noodle Bowls', 'slug': 'ramen-noodle-bowls'},
                    {'name': 'Breakfast & Cereal Bowls', 'slug': 'breakfast-cereal-bowls'},
                    {'name': 'Nesting & Mixing Bowls', 'slug': 'serving-nesting-bowls'},
                ]
            },
            {
                'name': 'Drinkware & Tea Rituals',
                'slug': 'drinkware-tea-rituals',
                'desc': 'Speckled stoneware coffee mugs, espresso demi-tasse sets, pour-over carafes, and ceremonial matcha chawan.',
                'children': [
                    {'name': 'Stoneware Mugs', 'slug': 'stoneware-mugs'},
                    {'name': 'Espresso Cups & Saucers', 'slug': 'espresso-cups'},
                    {'name': 'Tea & Pour-Over Sets', 'slug': 'tea-pour-over'},
                ]
            },
            {
                'name': 'Vases & Sculptural Vessels',
                'slug': 'vases-sculptural-vessels',
                'desc': 'Fluted terracotta urns, organic wabi-sabi moon jars, minimalist pedestal cylinders, and ikebana dishes.',
                'children': [
                    {'name': 'Statement Vases', 'slug': 'statement-vases'},
                    {'name': 'Minimalist Clay Urns', 'slug': 'minimalist-vessels'},
                ]
            },
            {
                'name': 'Kitchen & Serveware',
                'slug': 'kitchen-serveware',
                'desc': 'Large ceramic serving platters, water carafes, French butter crocks, and olive oil cruets with brass pourers.',
                'children': [
                    {'name': 'Serving Platters', 'slug': 'serving-platters'},
                    {'name': 'Kitchen Storage Crocks', 'slug': 'kitchen-crocks'},
                ]
            },
        ]

        cat_map = {}
        for c_idx, c_info in enumerate(categories_structure):
            parent_cat, _ = Category.objects.get_or_create(
                slug=c_info['slug'],
                defaults={
                    'name': c_info['name'],
                    'description': c_info['desc'],
                    'sort_order': c_idx,
                    'is_active': True,
                }
            )
            cat_map[c_info['slug']] = parent_cat

            for sub_idx, sub_info in enumerate(c_info['children']):
                sub_cat, _ = Category.objects.get_or_create(
                    slug=sub_info['slug'],
                    defaults={
                        'name': sub_info['name'],
                        'parent': parent_cat,
                        'sort_order': sub_idx,
                        'is_active': True,
                    }
                )
                cat_map[sub_info['slug']] = sub_cat

        # ---------------------------------------------------------
        # 4. 28 HANDCRAFTED LUXURY CERAMIC PRODUCTS DEFINITION
        # ---------------------------------------------------------
        self.stdout.write("4. Defining 28 Handcrafted Ceramic Objects...")
        products_data = [
            # 1. Dinnerware & Plates
            {
                'name': 'Komorebi Fluted Stoneware Dinner Set (16-Piece)',
                'slug': 'komorebi-fluted-stoneware-dinner-set-16pc',
                'cat_slug': 'complete-dinner-sets',
                'brand_slug': 'nordic-klay',
                'base_price': Decimal('5999.00'),
                'discount_price': Decimal('5199.00'),
                'sku': 'CRK-SET-KOM16',
                'weight': Decimal('7.2'),
                'is_featured': True,
                'short_desc': 'A complete 16-piece high-fire stoneware tableware service for four, featuring organic fluted rims and hand-sponged matte speckle glaze.',
                'full_desc': 'Crafted in small batch firings, the Komorebi service combines Scandinavian minimalism with Japanese wabi-sabi earthiness. Includes 4 Dinner Plates (10.5"), 4 Salad Plates (8.2"), 4 Pasta Bowls (8.5"), and 4 Everyday Mugs (350ml). Fired at 1,280°C for exceptional chip resistance.',
                'colors': [
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'},
                    {'name': 'Sandstone Matte', 'hex': '#D9CFC4'}
                ],
                'sizes': ['16-Piece Complete Service (Serves 4)', '8-Piece Petite Set (Serves 2)'],
                'photo_idx': 0,
            },
            {
                'name': 'Khurja Raw-Rim Stoneware Dinner Plate (Set of 4)',
                'slug': 'khurja-raw-rim-stoneware-dinner-plate-set-4',
                'cat_slug': 'dinner-plates',
                'brand_slug': 'khurja-atelier',
                'base_price': Decimal('2499.00'),
                'discount_price': Decimal('1999.00'),
                'sku': 'CRK-PLT-KHU4',
                'weight': Decimal('2.8'),
                'is_featured': True,
                'short_desc': 'Heavyweight stoneware dinner plates with exposed raw clay rims, hand-thrown by master potters of Khurja.',
                'full_desc': 'These 10.5-inch entree plates celebrate the natural beauty of iron-rich earthenware. The unglazed foot ring provides tactile organic grip, while the interior features a smooth satin-matte food safe glaze.',
                'colors': [
                    {'name': 'Raw Terracotta', 'hex': '#C2714F'},
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'}
                ],
                'sizes': ['Set of 4 (10.5-Inch)', 'Set of 6 (10.5-Inch)'],
                'photo_idx': 2,
            },
            {
                'name': 'Wabi-Sabi Asymmetric Pasta & Risotto Bowl (Set of 2)',
                'slug': 'wabi-sabi-asymmetric-pasta-bowl-set-2',
                'cat_slug': 'pasta-salad-plates',
                'brand_slug': 'wabi-earthen',
                'base_price': Decimal('1850.00'),
                'discount_price': Decimal('1499.00'),
                'sku': 'CRK-BWL-WBI2',
                'weight': Decimal('1.6'),
                'is_featured': True,
                'short_desc': 'Broad shallow ceramic bowls designed with deliberate organic asymmetry for artisan pasta, curries, and stews.',
                'full_desc': 'No two bowls in this set are perfectly identical. Pinched and trimmed freehand on the wheel, the shallow wide-lip profile frames culinary creations with museum-like poise.',
                'colors': [
                    {'name': 'Charcoal Ash', 'hex': '#363534'},
                    {'name': 'Sandstone Matte', 'hex': '#D9CFC4'}
                ],
                'sizes': ['Set of 2 (8.5-Inch / 800ml)', 'Set of 4 (8.5-Inch / 800ml)'],
                'photo_idx': 6,
            },
            {
                'name': 'Jaipur Cobalt Ripple Salad Plate (Set of 4)',
                'slug': 'jaipur-cobalt-ripple-salad-plate-set-4',
                'cat_slug': 'pasta-salad-plates',
                'brand_slug': 'jaipur-clayworks',
                'base_price': Decimal('2100.00'),
                'discount_price': Decimal('1750.00'),
                'sku': 'CRK-PLT-JAI4',
                'weight': Decimal('1.9'),
                'is_featured': False,
                'short_desc': 'Hand-carved concentric ripple textures with gentle natural cobalt pooling glaze.',
                'full_desc': 'Inspired by the historic blue pottery tradition of Jaipur, these salad plates blend quartz stone clay with mineral pigments for a serene aquatic depth.',
                'colors': [
                    {'name': 'Indigo Mist', 'hex': '#3E4E59'},
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'}
                ],
                'sizes': ['Set of 4 (8.2-Inch)', 'Set of 6 (8.2-Inch)'],
                'photo_idx': 7,
            },
            {
                'name': 'Terra Oribe Deep Coupe Dinner Plate (Set of 4)',
                'slug': 'terra-oribe-coupe-dinner-plate-set-4',
                'cat_slug': 'dinner-plates',
                'brand_slug': 'terra-oribe',
                'base_price': Decimal('2800.00'),
                'discount_price': Decimal('2350.00'),
                'sku': 'CRK-PLT-ORB4',
                'weight': Decimal('2.9'),
                'is_featured': False,
                'short_desc': 'Stately coupe dinner plates featuring rich forest moss reduction glaze and iron flecks.',
                'full_desc': 'With a soft rim curvature, these coupe plates hold rich gravies and reductions effortlessly. Double-fired in a wood-ash atmosphere for subtle, one-of-a-kind color shifts.',
                'colors': [
                    {'name': 'Forest Moss', 'hex': '#2D4A3E'},
                    {'name': 'Charcoal Ash', 'hex': '#363534'}
                ],
                'sizes': ['Set of 4 (10.5-Inch)', 'Set of 6 (10.5-Inch)'],
                'photo_idx': 9,
            },
            {
                'name': 'Hasami Minimalist Flat Charger Serving Plate',
                'slug': 'hasami-minimalist-flat-charger-plate',
                'cat_slug': 'dinner-plates',
                'brand_slug': 'hasami-studio',
                'base_price': Decimal('1450.00'),
                'discount_price': Decimal('1199.00'),
                'sku': 'CRK-PLT-HAS1',
                'weight': Decimal('1.2'),
                'is_featured': False,
                'short_desc': 'Architectural, precision-calibrated flat ceramic plate with vertical edge lip.',
                'full_desc': 'Designed with Japanese modularity, these plates stack flush with zero wobble. Serve artisan cheeses, hors d’oeuvres, or use as a centerpiece charger.',
                'colors': [
                    {'name': 'Sandstone Matte', 'hex': '#D9CFC4'},
                    {'name': 'Raw Terracotta', 'hex': '#C2714F'}
                ],
                'sizes': ['11.5-Inch Single', '11.5-Inch Duo (Set of 2)'],
                'photo_idx': 10,
            },

            # 2. Bowls & Dining
            {
                'name': 'Earthen Deep Ramen & Noodle Bowl (Set of 2)',
                'slug': 'earthen-deep-ramen-noodle-bowl-set-2',
                'cat_slug': 'ramen-noodle-bowls',
                'brand_slug': 'khurja-atelier',
                'base_price': Decimal('1699.00'),
                'discount_price': Decimal('1399.00'),
                'sku': 'CRK-BWL-RAM2',
                'weight': Decimal('1.8'),
                'is_featured': True,
                'short_desc': 'Deep insulated ceramic bowl with contoured thumb rest and notched chopstick cradle.',
                'full_desc': 'Engineered to hold broth warmth for extended dining. Thick, heat-retentive vitrified stoneware walls prevent thermal burn while resting comfortably in the palm.',
                'colors': [
                    {'name': 'Charcoal Ash', 'hex': '#363534'},
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'}
                ],
                'sizes': ['Set of 2 (950ml)', 'Set of 4 (950ml)'],
                'photo_idx': 23,
            },
            {
                'name': 'Artisanal Breakfast Cereal & Acai Bowl (Set of 4)',
                'slug': 'artisanal-breakfast-cereal-bowl-set-4',
                'cat_slug': 'breakfast-cereal-bowls',
                'brand_slug': 'nordic-klay',
                'base_price': Decimal('1950.00'),
                'discount_price': Decimal('1599.00'),
                'sku': 'CRK-BWL-ACAI4',
                'weight': Decimal('1.6'),
                'is_featured': False,
                'short_desc': 'Warm morning staple bowls with hand-sponged rims, perfect for granola, fruit, and soups.',
                'full_desc': 'The 550ml capacity is optimized for portion-controlled everyday breakfast rituals. Features a weighted base that resists tipping.',
                'colors': [
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'},
                    {'name': 'Raw Terracotta', 'hex': '#C2714F'}
                ],
                'sizes': ['Set of 4 (550ml)', 'Set of 6 (550ml)'],
                'photo_idx': 8,
            },
            {
                'name': 'Hand-Pinched Tapas & Dipping Pinch Bowls (Set of 6)',
                'slug': 'hand-pinched-tapas-pinch-bowls-set-6',
                'cat_slug': 'breakfast-cereal-bowls',
                'brand_slug': 'wabi-earthen',
                'base_price': Decimal('1299.00'),
                'discount_price': Decimal('999.00'),
                'sku': 'CRK-BWL-PINCH6',
                'weight': Decimal('0.8'),
                'is_featured': False,
                'short_desc': 'Petite organic clay bowls for table salt, olive tapenade, wasabi, and infused oils.',
                'full_desc': 'Formed through tactile thumb pressure, each pinch bowl carries the subtle imprint of the potter’s hand. Adds rustic warmth to any charcuterie board.',
                'colors': [
                    {'name': 'Sandstone Matte', 'hex': '#D9CFC4'},
                    {'name': 'Forest Moss', 'hex': '#2D4A3E'}
                ],
                'sizes': ['Set of 6 (100ml)'],
                'photo_idx': 12,
            },
            {
                'name': 'Speckled Stoneware Nesting Mixing Bowls (Set of 3)',
                'slug': 'speckled-stoneware-nesting-bowls-set-3',
                'cat_slug': 'serving-nesting-bowls',
                'brand_slug': 'khurja-atelier',
                'base_price': Decimal('3200.00'),
                'discount_price': Decimal('2699.00'),
                'sku': 'CRK-BWL-NEST3',
                'weight': Decimal('4.1'),
                'is_featured': True,
                'short_desc': 'Graduated trio of nesting culinary bowls for meal prep, salad tossing, and family-style serving.',
                'full_desc': 'Includes Small (1.1L), Medium (2.2L), and Large (3.5L) nesting stoneware vessels. Heavyweight bases keep the bowls anchored while whisking or folding batter.',
                'colors': [
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'},
                    {'name': 'Sandstone Matte', 'hex': '#D9CFC4'}
                ],
                'sizes': ['3-Piece Nesting Suite (1.1L, 2.2L, 3.5L)'],
                'photo_idx': 14,
            },
            {
                'name': 'Jaipur Azure Hand-Carved Soup Terrine Bowl (Set of 4)',
                'slug': 'jaipur-azure-hand-carved-soup-bowl-set-4',
                'cat_slug': 'breakfast-cereal-bowls',
                'brand_slug': 'jaipur-clayworks',
                'base_price': Decimal('2200.00'),
                'discount_price': Decimal('1799.00'),
                'sku': 'CRK-BWL-JAI4',
                'weight': Decimal('2.1'),
                'is_featured': False,
                'short_desc': 'Elegantly fluted soup bowls with botanical mineral glazes for broths and chowders.',
                'full_desc': 'Traditional fluting along the exterior walls cools slightly faster for handling while retaining soup heat inside. Double vitrified.',
                'colors': [
                    {'name': 'Indigo Mist', 'hex': '#3E4E59'},
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'}
                ],
                'sizes': ['Set of 4 (650ml)'],
                'photo_idx': 24,
            },

            # 3. Drinkware & Tea Rituals
            {
                'name': 'Studio Speckled Everyday Stoneware Mug (Set of 2)',
                'slug': 'studio-speckled-stoneware-mug-set-2',
                'cat_slug': 'stoneware-mugs',
                'brand_slug': 'nordic-klay',
                'base_price': Decimal('1199.00'),
                'discount_price': Decimal('899.00'),
                'sku': 'CRK-MUG-SPECK2',
                'weight': Decimal('0.9'),
                'is_featured': True,
                'short_desc': 'Generous 360ml ceramic mug with an ergonomic two-finger pulled handle and exposed raw base.',
                'full_desc': 'Designed for slow morning brews and herbal infusions. The tapered lip ensures smooth, drip-free sipping, while natural iron speckling creates unique constellation patterns.',
                'colors': [
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'},
                    {'name': 'Forest Moss', 'hex': '#2D4A3E'},
                    {'name': 'Raw Terracotta', 'hex': '#C2714F'}
                ],
                'sizes': ['Set of 2 (360ml)', 'Set of 4 (360ml)'],
                'photo_idx': 5,
            },
            {
                'name': 'Smoked Ash Demi-Tasse Espresso Cup & Saucer Duo',
                'slug': 'smoked-ash-espresso-cup-saucer-duo',
                'cat_slug': 'espresso-cups',
                'brand_slug': 'hasami-studio',
                'base_price': Decimal('1450.00'),
                'discount_price': Decimal('1150.00'),
                'sku': 'CRK-MUG-ESP2',
                'weight': Decimal('0.7'),
                'is_featured': False,
                'short_desc': '90ml double-shot espresso cups with matching recessed stoneware saucers.',
                'full_desc': 'Thick ceramic walls maintain optimal extraction temperature and preserve crema texture. Stackable modular design inspired by Japanese tea houses.',
                'colors': [
                    {'name': 'Charcoal Ash', 'hex': '#363534'},
                    {'name': 'Sandstone Matte', 'hex': '#D9CFC4'}
                ],
                'sizes': ['Duo Set (2 Cups + 2 Saucers)', 'Quartet Set (4 Cups + 4 Saucers)'],
                'photo_idx': 19,
            },
            {
                'name': 'Handcrafted Ceramic Pour-Over Coffee Dripper & Carafe Set',
                'slug': 'handcrafted-ceramic-pour-over-brewer-set',
                'cat_slug': 'tea-pour-over',
                'brand_slug': 'khurja-atelier',
                'base_price': Decimal('2600.00'),
                'discount_price': Decimal('2199.00'),
                'sku': 'CRK-DRIP-SET',
                'weight': Decimal('1.5'),
                'is_featured': True,
                'short_desc': 'Spiral-ribbed cone dripper paired with a 600ml stoneware carafe and natural cork coaster.',
                'full_desc': 'Internal spiral grooves channel water flow evenly through the coffee bed for maximum flavor extraction. Beautiful on kitchen countertops and dining tables alike.',
                'colors': [
                    {'name': 'Sandstone Matte', 'hex': '#D9CFC4'},
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'}
                ],
                'sizes': ['600ml Complete Brewer Set (Dripper + Carafe)'],
                'photo_idx': 16,
            },
            {
                'name': 'Traditional Ribbed Matcha Chawan (Tea Ceremony Bowl)',
                'slug': 'traditional-ribbed-matcha-chawan',
                'cat_slug': 'tea-pour-over',
                'brand_slug': 'hasami-studio',
                'base_price': Decimal('1800.00'),
                'discount_price': Decimal('1450.00'),
                'sku': 'CRK-TEA-CHAWAN',
                'weight': Decimal('0.6'),
                'is_featured': False,
                'short_desc': 'Wide-mouthed ceramic whisking bowl for traditional ceremonial matcha preparation.',
                'full_desc': 'Contoured cylindrical basin allows vigorous bamboo whisking without splash. Textured foot ring provides steady palm grounding during preparation.',
                'colors': [
                    {'name': 'Forest Moss', 'hex': '#2D4A3E'},
                    {'name': 'Charcoal Ash', 'hex': '#363534'}
                ],
                'sizes': ['450ml Ceremony Bowl'],
                'photo_idx': 18,
            },
            {
                'name': 'Terracotta Ribbed Chai Kulhad Set (Set of 6)',
                'slug': 'terracotta-ribbed-chai-kulhad-set-6',
                'cat_slug': 'stoneware-mugs',
                'brand_slug': 'jaipur-clayworks',
                'base_price': Decimal('1350.00'),
                'discount_price': Decimal('999.00'),
                'sku': 'CRK-KUL-JAI6',
                'weight': Decimal('1.2'),
                'is_featured': False,
                'short_desc': 'Modern reinterpretation of the classic Indian chai kulhad with glazed lip for food safety.',
                'full_desc': 'Preserves the earthy aroma of raw baked clay while featuring a glazed rim so your lips touch smooth non-porous finish. Reusable and dishwasher safe.',
                'colors': [
                    {'name': 'Raw Terracotta', 'hex': '#C2714F'},
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'}
                ],
                'sizes': ['Set of 6 (180ml)'],
                'photo_idx': 3,
            },
            {
                'name': 'Oribe Glazed Ceramic Teapot with Walnut Timber Handle',
                'slug': 'oribe-glazed-teapot-walnut-handle',
                'cat_slug': 'tea-pour-over',
                'brand_slug': 'terra-oribe',
                'base_price': Decimal('3499.00'),
                'discount_price': Decimal('2950.00'),
                'sku': 'CRK-TEA-ORB1',
                'weight': Decimal('1.3'),
                'is_featured': True,
                'short_desc': 'Stunning 850ml stoneware teapot with integrated clay filter and heat-treated walnut wood arch handle.',
                'full_desc': 'Combines organic timber and rich moss green glaze. Includes an internal ceramic strainer for loose-leaf teas and a snug-fitting brass pin lid.',
                'colors': [
                    {'name': 'Forest Moss', 'hex': '#2D4A3E'},
                    {'name': 'Charcoal Ash', 'hex': '#363534'}
                ],
                'sizes': ['850ml Artisan Teapot'],
                'photo_idx': 4,
            },

            # 4. Vases & Sculptural Vessels
            {
                'name': 'Aura Fluted Terracotta Statement Vase (14-Inch)',
                'slug': 'aura-fluted-terracotta-statement-vase',
                'cat_slug': 'statement-vases',
                'brand_slug': 'wabi-earthen',
                'base_price': Decimal('3899.00'),
                'discount_price': Decimal('3199.00'),
                'sku': 'CRK-VAS-AURA14',
                'weight': Decimal('3.5'),
                'is_featured': True,
                'short_desc': 'Towering sculptural vase with vertical architectural fluting and matte terracotta exterior.',
                'full_desc': 'An arresting centerpiece for dining consoles, mantles, or entryway tables. Sealed on the inside to hold fresh botanical branches and water without seepage.',
                'colors': [
                    {'name': 'Raw Terracotta', 'hex': '#C2714F'},
                    {'name': 'Sandstone Matte', 'hex': '#D9CFC4'}
                ],
                'sizes': ['10-Inch Petite', '14-Inch Statement Grand'],
                'photo_idx': 17,
            },
            {
                'name': 'Komorebi Organic Minimalist Ceramic Urn',
                'slug': 'komorebi-organic-minimalist-ceramic-urn',
                'cat_slug': 'minimalist-vessels',
                'brand_slug': 'nordic-klay',
                'base_price': Decimal('2999.00'),
                'discount_price': Decimal('2450.00'),
                'sku': 'CRK-VAS-KOMURN',
                'weight': Decimal('2.6'),
                'is_featured': False,
                'short_desc': 'Voluptuous rounded clay urn with subtle oatmeal speckle glaze and narrow neck opening.',
                'full_desc': 'Engineered to showcase single dry olive branches or pampas grass. The soft matte glaze catches natural window sunlight with warm diffused shadows.',
                'colors': [
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'},
                    {'name': 'Sandstone Matte', 'hex': '#D9CFC4'}
                ],
                'sizes': ['9-Inch Console Size', '12-Inch Floor Vessel'],
                'photo_idx': 20,
            },
            {
                'name': 'Asymmetric Moon Jar Ceramic Amphora Vessel',
                'slug': 'asymmetric-moon-jar-ceramic-amphora',
                'cat_slug': 'statement-vases',
                'brand_slug': 'hasami-studio',
                'base_price': Decimal('4500.00'),
                'discount_price': Decimal('3750.00'),
                'sku': 'CRK-VAS-MOONJAR',
                'weight': Decimal('4.2'),
                'is_featured': True,
                'short_desc': 'Hand-pinched spherical ceramic vessel inspired by traditional Korean moon jar aesthetics.',
                'full_desc': 'Two hemispherical halves joined by hand on the wheel, leaving a proud organic belt line around the equator. A statement of pure quiet luxury.',
                'colors': [
                    {'name': 'Sandstone Matte', 'hex': '#D9CFC4'},
                    {'name': 'Charcoal Ash', 'hex': '#363534'}
                ],
                'sizes': ['11-Inch Hand-Turned Sphere'],
                'photo_idx': 1,
            },
            {
                'name': 'Jaipur Cobalt Bud Vase Trio (Set of 3)',
                'slug': 'jaipur-cobalt-bud-vase-trio-set-3',
                'cat_slug': 'minimalist-vessels',
                'brand_slug': 'jaipur-clayworks',
                'base_price': Decimal('2400.00'),
                'discount_price': Decimal('1899.00'),
                'sku': 'CRK-VAS-JAI3',
                'weight': Decimal('1.4'),
                'is_featured': False,
                'short_desc': 'Three graduated miniature bud vases for floral cuttings, wildflowers, and windowsill accents.',
                'full_desc': 'Heights measure 5", 6.5", and 8". Each features subtle variation in cobalt oxide crystallization during the 1,280°C reduction firing.',
                'colors': [
                    {'name': 'Indigo Mist', 'hex': '#3E4E59'},
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'}
                ],
                'sizes': ['Set of 3 Graduated Vases (5", 6.5", 8")'],
                'photo_idx': 11,
            },
            {
                'name': 'Terra Oribe Sculptural Ikebana Floral Dish',
                'slug': 'terra-oribe-sculptural-ikebana-dish',
                'cat_slug': 'minimalist-vessels',
                'brand_slug': 'terra-oribe',
                'base_price': Decimal('2200.00'),
                'discount_price': Decimal('1750.00'),
                'sku': 'CRK-VAS-IKEBANA',
                'weight': Decimal('1.5'),
                'is_featured': False,
                'short_desc': 'Shallow water basin dish paired with a solid brass kenzan flower frog for Japanese ikebana.',
                'full_desc': 'The shallow dish holds water while the heavy brass frog pins stems upright, turning simple leaves and blossoms into meditative art installations.',
                'colors': [
                    {'name': 'Forest Moss', 'hex': '#2D4A3E'},
                    {'name': 'Charcoal Ash', 'hex': '#363534'}
                ],
                'sizes': ['8.5-Inch Shallow Basin with Kenzan Frog'],
                'photo_idx': 21,
            },
            {
                'name': 'Raw Sandstone Cylinder Pedestal Vase (10-Inch)',
                'slug': 'raw-sandstone-cylinder-pedestal-vase',
                'cat_slug': 'minimalist-vessels',
                'brand_slug': 'wabi-earthen',
                'base_price': Decimal('2750.00'),
                'discount_price': Decimal('2199.00'),
                'sku': 'CRK-VAS-CYL10',
                'weight': Decimal('2.2'),
                'is_featured': False,
                'short_desc': 'Clean brutalist ceramic column with chamfered pedestal base.',
                'full_desc': 'Unglazed coarse sand exterior contrasts with a smooth vitrified waterproof interior. Stunning next to natural linen and warm walnut furniture.',
                'colors': [
                    {'name': 'Sandstone Matte', 'hex': '#D9CFC4'},
                    {'name': 'Raw Terracotta', 'hex': '#C2714F'}
                ],
                'sizes': ['10-Inch Column Vessel'],
                'photo_idx': 13,
            },

            # 5. Kitchen & Serveware
            {
                'name': 'Heirloom Speckled Ceramic Oval Serving Platter (16-Inch)',
                'slug': 'heirloom-speckled-oval-serving-platter',
                'cat_slug': 'serving-platters',
                'brand_slug': 'khurja-atelier',
                'base_price': Decimal('2899.00'),
                'discount_price': Decimal('2299.00'),
                'sku': 'CRK-SER-PLAT16',
                'weight': Decimal('3.1'),
                'is_featured': True,
                'short_desc': 'Substantial oval banquet platter with gently raised lip, perfect for roasts, artisanal bread, and mezze.',
                'full_desc': 'Oven safe up to 220°C, so you can bake directly on the platter and bring piping-hot meals straight from the kiln to the dining table.',
                'colors': [
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'},
                    {'name': 'Forest Moss', 'hex': '#2D4A3E'}
                ],
                'sizes': ['14-Inch Medium', '16.5-Inch Grand Banquet Platter'],
                'photo_idx': 15,
            },
            {
                'name': 'Artisan Stoneware Water Pitcher & Carafe (1.5L)',
                'slug': 'artisan-stoneware-water-pitcher-15l',
                'cat_slug': 'kitchen-crocks',
                'brand_slug': 'nordic-klay',
                'base_price': Decimal('2450.00'),
                'discount_price': Decimal('1950.00'),
                'sku': 'CRK-SER-PITCH15',
                'weight': Decimal('1.8'),
                'is_featured': False,
                'short_desc': '1.5-liter water pitcher with balanced loop handle and tapered drip-free pouring beak.',
                'full_desc': 'Ceramic evaporative properties keep water, iced tea, and sangria naturally cooler than room temperature. A dining table centerpiece.',
                'colors': [
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'},
                    {'name': 'Sandstone Matte', 'hex': '#D9CFC4'}
                ],
                'sizes': ['1.5-Liter Table Pitcher'],
                'photo_idx': 11,
            },
            {
                'name': 'Terracotta French Butter Crock (Water-Sealed)',
                'slug': 'terracotta-french-butter-crock',
                'cat_slug': 'kitchen-crocks',
                'brand_slug': 'wabi-earthen',
                'base_price': Decimal('1499.00'),
                'discount_price': Decimal('1199.00'),
                'sku': 'CRK-SER-BUTTER',
                'weight': Decimal('0.9'),
                'is_featured': False,
                'short_desc': 'Traditional bell crock that keeps butter spreadably soft and fresh for weeks using an airtight water seal.',
                'full_desc': 'No refrigeration needed. Pack softened butter into the lid cup, add cold water to the crock base, and invert the bell to create an airtight seal that locks in freshness.',
                'colors': [
                    {'name': 'Raw Terracotta', 'hex': '#C2714F'},
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'}
                ],
                'sizes': ['250g Water-Submerged Keeper'],
                'photo_idx': 7,
            },
            {
                'name': 'Glazed Stoneware Olive Oil Cruet with Weighted Brass Pourer',
                'slug': 'glazed-stoneware-oil-cruet-brass-pourer',
                'cat_slug': 'kitchen-crocks',
                'brand_slug': 'khurja-atelier',
                'base_price': Decimal('1299.00'),
                'discount_price': Decimal('999.00'),
                'sku': 'CRK-SER-OILCRUET',
                'weight': Decimal('0.7'),
                'is_featured': False,
                'short_desc': 'Opaque stoneware bottle that blocks UV light to protect delicate extra virgin olive oil flavor.',
                'full_desc': 'Fitted with a precision weighted brass flapper spout that opens on pour and closes immediately when set upright, eliminating messy oil drips.',
                'colors': [
                    {'name': 'Forest Moss', 'hex': '#2D4A3E'},
                    {'name': 'Charcoal Ash', 'hex': '#363534'}
                ],
                'sizes': ['500ml Dispenser Bottle'],
                'photo_idx': 22,
            },
            {
                'name': 'Hand-Carved Ceramic Spoon Rest & Pinch Dish Duo',
                'slug': 'hand-carved-ceramic-spoon-rest-duo',
                'cat_slug': 'kitchen-crocks',
                'brand_slug': 'jaipur-clayworks',
                'base_price': Decimal('950.00'),
                'discount_price': Decimal('699.00'),
                'sku': 'CRK-SER-SPREST2',
                'weight': Decimal('0.5'),
                'is_featured': False,
                'short_desc': 'Stovetop companion dish with contoured ladle groove to protect countertops from hot sauces.',
                'full_desc': 'Includes one wide cooking spoon rest and a matching salt pinch cup. Wipe clean or wash in dishwasher.',
                'colors': [
                    {'name': 'Indigo Mist', 'hex': '#3E4E59'},
                    {'name': 'Oatmeal Speckle', 'hex': '#EBE5DF'}
                ],
                'sizes': ['2-Piece Kitchen Companion Set'],
                'photo_idx': 0,
            },
        ]

        # Reviewers pool for realistic customer feedback
        reviewers_pool = [
            {'name': 'Aditi Rao', 'email': 'aditi.rao@example.com', 'rating': 5, 'comment': 'The glaze quality is unbelievable for this price. Heavy, tactile, and looks like a boutique Japanese art piece on our dining table.'},
            {'name': 'Vikram Mehra', 'email': 'vikram.mehra@example.com', 'rating': 5, 'comment': 'Packed with utmost fragile care! Arrived in zero breakage, microwave safe, and has that authentic artisanal raw clay rim.'},
            {'name': 'Sanya Kapoor', 'email': 'sanya.kapoor@example.com', 'rating': 4, 'comment': 'Stunning earth tones. Goes gorgeously with our raw wood dining table. Truly heirloom stoneware.'},
            {'name': 'Chef Kabir Nair', 'email': 'kabir.nair@example.com', 'rating': 5, 'comment': 'As a culinary stylist, these are my go-to bowls and plates for food photography. The matte glaze cuts glare completely.'},
        ]

        created_review_users = []
        for r_user in reviewers_pool:
            u, _ = User.objects.get_or_create(
                email=r_user['email'],
                defaults={'name': r_user['name'], 'phone': '+91 9876543000', 'is_active': True}
            )
            created_review_users.append((u, r_user['rating'], r_user['comment']))

        # ---------------------------------------------------------
        # 5. GENERATE & SAVE PRODUCTS, IMAGES, VARIANTS & SPECS
        # ---------------------------------------------------------
        total_p = len(products_data)
        for p_idx, p_data in enumerate(products_data, start=1):
            self.stdout.write(f"[{p_idx}/{total_p}] Generating: {p_data['name']}...")

            cat = cat_map[p_data['cat_slug']]
            brand = brand_map[p_data['brand_slug']]

            prod = Product.objects.create(
                name=p_data['name'],
                slug=p_data['slug'],
                category=cat,
                brand=brand,
                base_price=p_data['base_price'],
                discount_price=p_data['discount_price'],
                sku=p_data['sku'],
                weight=p_data['weight'],
                short_description=p_data['short_desc'],
                full_description=p_data['full_desc'],
                material='High-Fire Vitrified Stoneware',
                tags=f"crockery,ceramics,stoneware,tableware,{cat.name.lower()},{brand.name.lower()}",
                is_featured=p_data['is_featured'],
                is_active=True,
                meta_title=f"{p_data['name']} | Crookeries by AvailSmart",
                meta_description=p_data['short_desc'],
            )

            # Colors & 4:5 WebP Images
            photo_base_idx = p_data['photo_idx']
            for c_idx, c_info in enumerate(p_data['colors']):
                color = ProductColor.objects.create(
                    product=prod,
                    color_name=c_info['name'],
                    color_hex=c_info['hex'],
                    sort_order=c_idx,
                    is_active=True
                )

                # Fetch 4:5 vertical portrait WebP photography
                pid_hero = CERAMIC_PHOTO_POOL[(photo_base_idx + c_idx) % len(CERAMIC_PHOTO_POOL)]
                hero_content = fetch_and_crop_ceramic_image(
                    pid_hero,
                    title=prod.name,
                    subtitle=f"{c_info['name']} • High-Fire Vitrified Ceramic"
                )

                hero_filename = f"{prod.slug}_{c_idx}_hero.webp"
                hero_img = ProductImage(
                    product_color=color,
                    alt_text=f"{prod.name} in {c_info['name']}",
                    is_primary=(c_idx == 0),
                    sort_order=0
                )
                hero_img.image.save(hero_filename, hero_content, save=True)

                # Angle 2: Close-up / Texture view
                pid_detail = CERAMIC_PHOTO_POOL[(photo_base_idx + c_idx + 3) % len(CERAMIC_PHOTO_POOL)]
                detail_content = fetch_and_crop_ceramic_image(
                    pid_detail,
                    title=prod.name,
                    subtitle=f"Close-Up Glaze & Texture Details"
                )
                detail_filename = f"{prod.slug}_{c_idx}_detail.webp"
                detail_img = ProductImage(
                    product_color=color,
                    alt_text=f"{prod.name} glaze detail",
                    is_primary=False,
                    sort_order=1
                )
                detail_img.image.save(detail_filename, detail_content, save=True)

                # Create Variants for this color
                for s_idx, size_name in enumerate(p_data['sizes']):
                    var_sku = f"{p_data['sku']}-C{c_idx}-S{s_idx}"
                    # Price variation for larger sets
                    var_price = None
                    if 'Set of 6' in size_name or 'Floor' in size_name or 'Banquet' in size_name:
                        var_price = prod.effective_price + Decimal('800.00')

                    ProductVariant.objects.create(
                        product=prod,
                        product_color=color,
                        size=size_name,
                        sku=var_sku,
                        price=var_price,
                        stock_quantity=24 + (s_idx * 6),
                        weight=prod.weight,
                        is_active=True
                    )

            # Specifications
            specs = [
                ('Material & Clay', 'High-fire vitrified stoneware clay'),
                ('Firing Temperature', '1,280°C (Cone 10 reduction firing)'),
                ('Glaze Chemistry', '100% Food-Safe matte mineral glaze (Lead & Cadmium Free)'),
                ('Appliance Compatibility', 'Microwave safe, Dishwasher safe, Oven safe up to 220°C'),
                ('Craft Technique', 'Wheel-thrown & trimmed by hand by master potters'),
                ('Studio Origin', brand.name),
                ('Guarantee', '7-Day Doorstep Tabletop Trial & Fragile Breakage Insurance'),
            ]
            for s_idx, (k, v) in enumerate(specs):
                ProductSpecification.objects.create(
                    product=prod,
                    key=k,
                    value=v,
                    sort_order=s_idx
                )

            # Reviews
            rev_user_tuple = created_review_users[p_idx % len(created_review_users)]
            Review.objects.create(
                user=rev_user_tuple[0],
                product=prod,
                rating=rev_user_tuple[1],
                comment=rev_user_tuple[2],
                is_approved=True
            )
            # Add second review for featured products
            if prod.is_featured:
                rev2 = created_review_users[(p_idx + 1) % len(created_review_users)]
                Review.objects.create(
                    user=rev2[0],
                    product=prod,
                    rating=rev2[1],
                    comment=rev2[2],
                    is_approved=True
                )
            prod.update_rating_stats()

        # ---------------------------------------------------------
        # 6. HOMEPAGE PROMOTIONAL BANNERS
        # ---------------------------------------------------------
        self.stdout.write("6. Creating Editorial Studio Banners...")
        banners = [
            {
                'title': 'The Autumn Kiln Release',
                'subtitle': 'Hand-thrown stoneware curated for mindful, slow dining rituals.',
                'link': '/catalog/dinnerware-plates/',
                'sort': 0,
                'photo': CERAMIC_PHOTO_POOL[0],
            },
            {
                'title': 'Artisanal Studios of India',
                'subtitle': 'Vitrified at 1,280°C by the master potters of Khurja and Jaipur.',
                'link': '/story/',
                'sort': 1,
                'photo': CERAMIC_PHOTO_POOL[1],
            },
            {
                'title': 'The 7-Day Doorstep Trial',
                'subtitle': 'Test our ceramic pieces on your tabletop with complimentary fragile returns.',
                'link': '/orders/returns/',
                'sort': 2,
                'photo': CERAMIC_PHOTO_POOL[2],
            },
        ]
        for b_data in banners:
            b = Banner(
                title=b_data['title'],
                subtitle=b_data['subtitle'],
                link=b_data['link'],
                sort_order=b_data['sort'],
                is_active=True
            )
            b_img_content = fetch_and_crop_ceramic_image(b_data['photo'], b_data['title'], b_data['subtitle'], target_w=1200, target_h=500)
            b.image.save(f"banner_{b_data['sort']}.webp", b_img_content, save=True)

        self.stdout.write(self.style.SUCCESS(
            f"\n SUCCESS! Seeded {total_p} Handcrafted Ceramic Products, {Category.objects.count()} Categories, "
            f"{Brand.objects.count()} Studios, {ProductVariant.objects.count()} Variants, "
            f"and {ProductImage.objects.count()} 4:5 WebP Images into Crookeries by AvailSmart!"
        ))
