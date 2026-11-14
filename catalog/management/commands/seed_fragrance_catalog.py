import os
import io
import urllib.request
from datetime import timedelta
from decimal import Decimal
from PIL import Image, ImageDraw, ImageFont

from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils.text import slugify
from django.utils import timezone
from django.conf import settings

from accounts.models import User
from catalog.models import (
    Category, Brand, Product, ProductColor, ProductImage,
    ProductVariant, ProductSpecification, Review, Banner
)
from cart.models import Coupon


# High-resolution luxury perfume, attar & glass flacon photography pool from Unsplash
PERFUME_PHOTO_POOL = [
    'photo-1592945403244-b3fbafd7f539',  # Luxury perfume bottle on dark silk
    'photo-1547887537-6158d64c35b3',  # Gold perfume bottle with amber liquid
    'photo-1523293182086-7651a899d37f',  # Luxury aesthetic glass bottle
    'photo-1594035910387-fea47794261f',  # Perfume bottle with golden cap
    'photo-1588405748880-12d1d2a59f75',  # Luxury black flacon perfume
    'photo-1592945403407-98e604084620',  # Perfume flacon in studio light
    'photo-1616949755610-8c9bbc08f138',  # Arabic / Oriental style perfume bottle
    'photo-1563178406-4cdc2923acbc',  # Glass bottle with perfume & botanical reflections
    'photo-1587017539504-67cfbddac569',  # Dark aesthetic luxury fragrance
    'photo-1508746829417-e6f548d8d6ed',  # Perfume bottle with gold reflections
    'photo-1615655406736-b37c4fabf923',  # Amber perfume bottle
    'photo-1595425970377-c9703cf48b6d',  # Roll-on attar bottle & luxury box
]


def create_pro_fallback_perfume_image(title, subtitle, liquid_color='#C99700', bg_color='#0B0F17', width=800, height=1000):
    """
    Generates an artistic 4:5 vertical portrait WebP image of a luxury perfume flacon
    with golden cap, glowing amber/rose/oudh liquid, and royal typography.
    """
    img = Image.new('RGB', (width, height), color=bg_color)
    draw = ImageDraw.Draw(img)

    # Ambient studio radial glow behind bottle
    cx, cy = width // 2, height // 2 - 30
    for r in range(240, 40, -20):
        alpha_color = '#172033' if r > 160 else '#202E4A'
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=alpha_color)

    # Pedestal shadow
    draw.ellipse([cx - 150, cy + 220, cx + 150, cy + 260], fill='#05070B')

    # Bottle Body (Crystal Flacon)
    bottle_w, bottle_h = 130, 220
    draw.rectangle(
        [cx - bottle_w, cy - 30, cx + bottle_w, cy + 220],
        fill='#121824',
        outline='#D4AF37',
        width=3
    )

    # Inner Liquid Glow
    liquid_margin = 14
    draw.rectangle(
        [cx - bottle_w + liquid_margin, cy + 10, cx + bottle_w - liquid_margin, cy + 205],
        fill=liquid_color
    )

    # Label on Flacon
    label_w, label_h = 95, 75
    draw.rectangle(
        [cx - label_w, cy + 50, cx + label_w, cy + 50 + label_h],
        fill='#0B0F17',
        outline='#D4AF37',
        width=2
    )
    # Crown & Brand initials on label
    draw.text((cx - 30, cy + 58), "✦ AVAILSMART ✦", fill='#D4AF37')
    draw.text((cx - 38, cy + 78), "IMPERIAL ATTAR", fill='#FFFFFF')
    draw.text((cx - 28, cy + 98), "PURE PERFUME", fill='#D4AF37')

    # Bottle Neck
    draw.rectangle([cx - 40, cy - 75, cx + 40, cy - 30], fill='#C5A059', outline='#D4AF37', width=2)

    # Golden Cap (Crown / Dome Style)
    draw.polygon([
        (cx - 55, cy - 75),
        (cx + 55, cy - 75),
        (cx + 45, cy - 160),
        (cx - 45, cy - 160),
    ], fill='#D4AF37')
    # Cap tip jewel
    draw.ellipse([cx - 16, cy - 180, cx + 16, cy - 155], fill='#F3E5AB', outline='#D4AF37', width=2)

    # Title & Subtitle banner at bottom
    draw.rectangle([0, height - 120, width, height], fill='#070A0F')
    draw.line([(0, height - 120), (width, height - 120)], fill='#D4AF37', width=2)

    draw.text((40, height - 95), title.upper()[:34], fill='#FFFFFF')
    draw.text((40, height - 65), subtitle[:50], fill='#D4AF37')

    buf = io.BytesIO()
    img.save(buf, format='WEBP', quality=88, optimize=True)
    buf.seek(0)
    return ContentFile(buf.read())


def fetch_and_crop_perfume_image(photo_id, title="AvailSmart Luxury Fragrance", subtitle="Pure Concentrated Perfume", liquid_color='#C99700', target_w=800, target_h=1000):
    """
    Fetches genuine high-res fragrance photo from Unsplash, crops to 4:5 vertical portrait,
    and returns a ContentFile in WebP format. Falls back gracefully to artistic flacon render.
    """
    url = f"https://images.unsplash.com/{photo_id}?w=1000&auto=format&fit=crop&q=80"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
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
        print(f"  [Fallback Pill Image Used for {photo_id}]: {e}")

    # Fallback if download times out or 404s
    return create_pro_fallback_perfume_image(title, subtitle, liquid_color=liquid_color, width=target_w, height=target_h)


class Command(BaseCommand):
    help = 'Seeds database with 16 flagship luxury fragrances, attars, discovery boxes, authentic notes, and banners.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("===> Initiating AvailSmart Luxury Fragrance & Attar Catalog Seeding..."))

        # ---------------------------------------------------------
        # 1. CLEAN PREVIOUS GENERIC PRODUCTS & CATEGORIES
        # ---------------------------------------------------------
        self.stdout.write("1. Cleaning old catalog records...")
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
        # 2. SEED FRAGRANCE BRANDS (Authority Multi-Brand Store)
        # ---------------------------------------------------------
        self.stdout.write("2. Seeding Global & D2C Fragrance Brands...")
        brands_data = [
            {'name': 'AvailSmart Imperial Reserve', 'slug': 'availsmart-reserve'},
            {'name': 'Adil Qadri Signature', 'slug': 'adil-qadri'},
            {'name': 'Lattafa Perfumes Dubai', 'slug': 'lattafa'},
            {'name': 'Ahmed Al Maghribi', 'slug': 'ahmed-al-maghribi'},
            {'name': 'Ajmal Perfumes', 'slug': 'ajmal'},
            {'name': 'Rasasi Dubai', 'slug': 'rasasi'},
            {'name': 'Afnan Perfumes', 'slug': 'afnan'},
            {'name': 'Surrati Perfumes', 'slug': 'surrati'},
        ]
        brands_map = {}
        for b in brands_data:
            obj, _ = Brand.objects.get_or_create(slug=b['slug'], defaults={'name': b['name'], 'is_active': True})
            brands_map[b['slug']] = obj

        # ---------------------------------------------------------
        # 3. SEED MASTER CATEGORIES & SUBCATEGORIES
        # ---------------------------------------------------------
        self.stdout.write("3. Seeding Luxury Fragrance Categories & Subcategories...")
        cat_definitions = [
            {
                'name': 'Pure Concentrated Attars',
                'slug': 'pure-attars',
                'description': '100% Alcohol-Free concentrated perfume oils crafted with aged Cambodian oudh, pure amber, Damascus rose, and rare musks. 36+ hour longevity.',
                'sort_order': 1,
                'children': [
                    {'name': 'Royal Oudh Roll-ons', 'slug': 'royal-oudh-roll-ons'},
                    {'name': 'Amber & Musk Elixirs', 'slug': 'amber-musk-elixirs'},
                    {'name': 'Damascus Rose & Floral', 'slug': 'floral-rose-attars'},
                ]
            },
            {
                'name': 'French & Arabian EDP Sprays',
                'slug': 'edp-sprays',
                'description': 'High-concentration Eau De Parfum and Extrait De Parfum luxury sprays blending French perfumery elegance with opulent Arabian sillage.',
                'sort_order': 2,
                'children': [
                    {'name': 'Gourmand & Warm Spicy', 'slug': 'gourmand-spicy'},
                    {'name': 'Fresh Citrus & Aquatic', 'slug': 'fresh-aquatic'},
                    {'name': 'Dark Oudh & Leather', 'slug': 'dark-oudh-leather'},
                ]
            },
            {
                'name': 'Shark Tank Discovery Sets',
                'slug': 'discovery-sets',
                'description': 'Curated luxury discovery sample boxes containing 6ml to 10ml mini flacons. Try before you commit to a full bottle.',
                'sort_order': 3,
                'children': [
                    {'name': '10-Fragrance Pocket Samplers', 'slug': 'pocket-samplers'},
                    {'name': 'Luxury Gift Experience Boxes', 'slug': 'experience-gift-boxes'},
                ]
            },
            {
                'name': 'Rare Cambodian Oudh',
                'slug': 'rare-cambodian-oudh',
                'description': 'Artisanal aged pure agarwood oils harvested from wild aquilaria trees in Cambodia, Assam, and Trat. For royal connoisseurs.',
                'sort_order': 4,
                'children': []
            },
            {
                'name': 'Luxury Bakhoor & Incense',
                'slug': 'bakhoor-incense',
                'description': 'Aromatic wood chips, resinous frankincense, and crystal burners to elevate your home rituals with enduring Arabian warmth.',
                'sort_order': 5,
                'children': []
            },
            {
                'name': 'Combo Packs & Gift Sets',
                'slug': 'gift-combos',
                'description': 'Value bundles and signature sets curated for weddings, anniversaries, and personal gifting with up to 50% savings.',
                'sort_order': 6,
                'children': []
            },
        ]

        cats_map = {}
        for c in cat_definitions:
            parent_cat, _ = Category.objects.get_or_create(
                slug=c['slug'],
                defaults={'name': c['name'], 'description': c['description'], 'sort_order': c['sort_order'], 'is_active': True}
            )
            cats_map[c['slug']] = parent_cat
            for sub in c['children']:
                sub_cat, _ = Category.objects.get_or_create(
                    slug=sub['slug'],
                    defaults={'name': sub['name'], 'parent': parent_cat, 'is_active': True}
                )
                cats_map[sub['slug']] = sub_cat

        # ---------------------------------------------------------
        # 4. SEED FLAGSHIP PERFUMES (16 Rich Iconic Products)
        # ---------------------------------------------------------
        self.stdout.write("4. Seeding 16 Flagship Fragrances & Olfactory Data...")

        products_data = [
            {
                'name': 'Shanaya Luxury Concentrated Attar (12ml)',
                'slug': 'shanaya-luxury-concentrated-attar-12ml',
                'brand': 'adil-qadri',
                'category': 'amber-musk-elixirs',
                'base_price': Decimal('1199.00'),
                'discount_price': Decimal('799.00'),
                'discount_percent': 33,
                'fragrance_family': 'Oriental Sweet Amber',
                'top_notes': 'Sweet Amber, Bergamot, Italian Mandarin',
                'heart_notes': 'Damascus Rose, Madagascan Vanilla, Spiced Cinnamon',
                'base_notes': 'White Musk, Warm Agarwood, Tonka Bean',
                'longevity_hours': 36,
                'sillage_level': 'Enormous',
                'is_non_alcoholic': True,
                'bundle_text': 'Pack of 2 @ ₹1,199 (Save 50%)',
                'short_description': 'The legendary Shark Tank viral signature attar. 100% alcohol-free pure oil with rich sweet amber, floral warmth, and an unforgettable 36-hour trail.',
                'full_description': 'Shanaya by Adil Qadri is one of India’s most celebrated luxury attars. Formulated without a single drop of alcohol, this concentrated perfume oil opens with luminous citrus and golden sweet amber before melting into a decadent heart of spiced cinnamon and Damascus rose. The dry-down reveals rich agarwood and cashmere white musk that remains on clothing well past 36 hours.',
                'rating_avg': Decimal('4.94'),
                'rating_count': 1840,
                'is_featured': True,
                'liquid_color': '#D4AF37',
                'photo_idx': 0,
                'sizes': ['6ml Pocket Roll-On', '12ml Royal Crystal Flacon', 'Pack of 2 (12ml x 2)'],
                'specs': {
                    'Concentration': '100% Pure Attar Oil',
                    'Alcohol Content': '0% Alcohol-Free (Halal & Skin-Safe)',
                    'Longevity': 'Guaranteed 36+ Hours on Fabric',
                    'Origin': 'Gujarat, India (Artisanal Distillation)',
                    'Application': 'Glass Roll-on Applicator',
                    'Best For': 'Evening, Weddings, Daily Signature Scent',
                }
            },
            {
                'name': 'The AvailSmart 10-Fragrance Shark Tank Discovery Box',
                'slug': 'availsmart-10-fragrance-discovery-box',
                'brand': 'availsmart-reserve',
                'category': 'pocket-samplers',
                'base_price': Decimal('999.00'),
                'discount_price': Decimal('499.00'),
                'discount_percent': 50,
                'fragrance_family': 'Multi-Accord Discovery',
                'top_notes': 'Bergamot, Pink Pepper, Saffron, Mandarin',
                'heart_notes': 'Turkish Rose, Cardamom, French Lavender, Warm Amber',
                'base_notes': 'Cambodian Agarwood, White Musk, Patchouli, Sandalwood',
                'longevity_hours': 36,
                'sillage_level': 'Strong',
                'is_non_alcoholic': True,
                'bundle_text': 'Includes Free ₹200 Voucher for Full Bottle',
                'short_description': 'Our most popular discovery experience. 10 iconic non-alcoholic 6ml attar & perfume oils curated across fresh, oriental, oudh, and gourmand notes.',
                'full_description': 'The AvailSmart Discovery Box lets you discover your ultimate signature scent at home. Contains 10 premium 6ml rollerballs: White Oudh, Shanaya Amber, Royal Bakhoor, Safwan Musk, Imperial Rose, Velvet Oud, Citrus Zest, French Leather, Night Jasmine, and Golden Ambergris. Every order comes with an exclusive voucher towards your first full-size bottle purchase.',
                'rating_avg': Decimal('4.97'),
                'rating_count': 3290,
                'is_featured': True,
                'liquid_color': '#C5A059',
                'photo_idx': 1,
                'sizes': ['Box of 10 (6ml x 10)', 'Deluxe Box of 10 with Leather Pouch'],
                'specs': {
                    'Total Volume': '60ml (10 Bottles x 6ml)',
                    'Alcohol Content': '0% Alcohol-Free',
                    'Flacon Type': 'Precision Roll-on Bottles with Travel Box',
                    'Longevity': '36+ Hours per application',
                    'Bonus': 'Free ₹200 Gift Voucher included inside',
                }
            },
            {
                'name': 'Imperial White Oudh Non-Alcoholic Attar (12ml)',
                'slug': 'imperial-white-oudh-non-alcoholic-attar-12ml',
                'brand': 'availsmart-reserve',
                'category': 'royal-oudh-roll-ons',
                'base_price': Decimal('1499.00'),
                'discount_price': Decimal('899.00'),
                'discount_percent': 40,
                'fragrance_family': 'Rare Oudh & Woody',
                'top_notes': 'Cardamom, Sicilian Bergamot, White Pepper',
                'heart_notes': 'Aged Cambodian White Oudh, Cedarwood, Clary Sage',
                'base_notes': 'Royal Ambergris, Velvet White Musk, Haitian Vetiver',
                'longevity_hours': 36,
                'sillage_level': 'Enormous',
                'is_non_alcoholic': True,
                'bundle_text': 'Buy with Shanaya & Save 45%',
                'short_description': 'Crisp, royal, and aristocratic. Clean woody white agarwood blended with shimmering bergamot and velvet amber for lasting royal aura.',
                'full_description': 'Imperial White Oudh is the epitome of refined oriental elegance. Unlike harsh heavy oudhs, White Oudh offers a sophisticated crisp opening of cardamom and bergamot before transitioning into creamy agarwood heartwood. Its long-lasting dry-down is clean, powdery, and magnetic.',
                'rating_avg': Decimal('4.91'),
                'rating_count': 1120,
                'is_featured': True,
                'liquid_color': '#F3E5AB',
                'photo_idx': 2,
                'sizes': ['6ml Pocket Roll-On', '12ml Crystal Flacon', '24ml Connoisseur Vial'],
                'specs': {
                    'Concentration': 'Pure Perfume Oil',
                    'Alcohol Content': '100% Non-Alcoholic (Pure Oil)',
                    'Projection': '6+ Feet Sillage',
                    'Longevity': '36+ Hours',
                    'Origin': 'Kannauj & Dubai Collaboration',
                }
            },
            {
                'name': 'Lattafa Khamrah Eau De Parfum (100ml)',
                'slug': 'lattafa-khamrah-eau-de-parfum-100ml',
                'brand': 'lattafa',
                'category': 'gourmand-spicy',
                'base_price': Decimal('3499.00'),
                'discount_price': Decimal('2299.00'),
                'discount_percent': 34,
                'fragrance_family': 'Gourmand Warm Spicy',
                'top_notes': 'Cinnamon, Nutmeg, Bergamot',
                'heart_notes': 'Medjool Dates, Praline, Tuberose, Mahonial',
                'base_notes': 'Vanilla, Tonka Bean, Benzoin, Amberwood, Myrrh',
                'longevity_hours': 24,
                'sillage_level': 'Enormous',
                'is_non_alcoholic': False,
                'bundle_text': '100% Original Dubai Import with Hologram',
                'short_description': 'The world-famous viral gourmand sensation. Decadent dates, warm cinnamon, roasted praline, and creamy vanilla in a heavy crystal decanter bottle.',
                'full_description': 'Lattafa Khamrah is a globally acclaimed oriental unisex masterpiece. Packed in a heavy crystal glass flask reminiscent of fine cognac, it exudes warmth with intoxicating cinnamon and nutmeg, sweetened by date nectar and praline. An indispensable winter and evening fragrance that garners compliments everywhere.',
                'rating_avg': Decimal('4.96'),
                'rating_count': 4180,
                'is_featured': True,
                'liquid_color': '#B86B14',
                'photo_idx': 3,
                'sizes': ['100ml Full Crystal Bottle', '100ml + Khamrah Body Spray Combo'],
                'specs': {
                    'Concentration': 'Eau De Parfum (EDP)',
                    'Volume': '100ml / 3.4 fl. oz.',
                    'Country of Origin': 'United Arab Emirates (Dubai)',
                    'Packaging': 'Heavy Crystal Decanter with Embossed Box',
                    'Authenticity': '100% Original with Verification Scratch Seal',
                }
            },
            {
                'name': 'Ahmed Al Maghribi Bin Shaikh Extrait De Parfum (90ml)',
                'slug': 'ahmed-al-maghribi-bin-shaikh-90ml',
                'brand': 'ahmed-al-maghribi',
                'category': 'dark-oudh-leather',
                'base_price': Decimal('5500.00'),
                'discount_price': Decimal('4199.00'),
                'discount_percent': 24,
                'fragrance_family': 'Dark Amber Oudh',
                'top_notes': 'Saffron, Damascus Rose, French Oakmoss, Citruses',
                'heart_notes': 'Jasmine, Orchid, Sugar, Frankincense',
                'base_notes': 'Pure Dehn Al Oudh, Golden Amber, White Musk, Patchouli',
                'longevity_hours': 36,
                'sillage_level': 'Enormous',
                'is_non_alcoholic': False,
                'bundle_text': 'Royal Niche Masterpiece • Beast Mode Longevity',
                'short_description': 'The ultimate status symbol in Arabian luxury perfumery. Pure Dehn Al Oudh, saffron threads, and opulent rose with unparalleled beast projection.',
                'full_description': 'Bin Shaikh by Ahmed Al Maghribi is formulated for the royal connoisseur. As an Extrait De Parfum with exceptionally high fragrance oil concentration, it fills rooms with its hypnotic blend of authentic aged agarwood, rich floral saffron, and smoky amber. One or two sprays last through an entire day and into the next.',
                'rating_avg': Decimal('4.98'),
                'rating_count': 940,
                'is_featured': True,
                'liquid_color': '#6E2C00',
                'photo_idx': 4,
                'sizes': ['90ml Extrait Luxury Flacon'],
                'specs': {
                    'Concentration': 'Extrait De Parfum (35% Oil Concentration)',
                    'Volume': '90ml',
                    'Longevity': '36+ Hours on Clothes',
                    'Origin': 'UAE / Ahmed Al Maghribi House',
                    'Bottle': 'Gold Embroidered Velvet Presentation Box',
                }
            },
            {
                'name': 'Safwan Royal Musk Concentrated Attar (12ml)',
                'slug': 'safwan-royal-musk-attar-12ml',
                'brand': 'adil-qadri',
                'category': 'amber-musk-elixirs',
                'base_price': Decimal('999.00'),
                'discount_price': Decimal('699.00'),
                'discount_percent': 30,
                'fragrance_family': 'Clean White Musk & Powdery',
                'top_notes': 'Lily of the Valley, Morning Dew, White Florals',
                'heart_notes': 'Sweet Violet, Egyptian Jasmine, Soft Cotton',
                'base_notes': 'Velvet White Musk, Indian Sandalwood, Powdery Amber',
                'longevity_hours': 36,
                'sillage_level': 'Moderate',
                'is_non_alcoholic': True,
                'bundle_text': 'Ideal For Daily Wear & Office Elegance',
                'short_description': 'Crisp, velvety, and soothing pure white musk. 100% non-alcoholic attar oil evoking freshly laundered white linen and gentle floral breeze.',
                'full_description': 'Safwan by Adil Qadri is revered for its pristine cleanliness and non-intrusive elegance. Crafted for everyday rituals and work settings, this pure roll-on attar opens with dewy florals and settles into a serene white musk and creamy sandalwood cocoon that stays comforting and fresh throughout the day.',
                'rating_avg': Decimal('4.88'),
                'rating_count': 1420,
                'is_featured': False,
                'liquid_color': '#FAF8F5',
                'photo_idx': 5,
                'sizes': ['6ml Pocket Roll-On', '12ml Crystal Flacon'],
                'specs': {
                    'Concentration': '100% Pure Attar Oil',
                    'Alcohol Content': '0% Non-Alcoholic (Skin-Friendly)',
                    'Character': 'Powdery, Fresh, Velvety Clean',
                    'Longevity': '36 Hours',
                }
            },
            {
                'name': 'Rasasi Hawas For Men Eau De Parfum (100ml)',
                'slug': 'rasasi-hawas-for-men-100ml',
                'brand': 'rasasi',
                'category': 'fresh-aquatic',
                'base_price': Decimal('4999.00'),
                'discount_price': Decimal('3499.00'),
                'discount_percent': 30,
                'fragrance_family': 'Fresh Aquatic Spicy',
                'top_notes': 'Crisp Apple, Bergamot, Lemon, Ceylon Cinnamon',
                'heart_notes': 'Watery Marine Accords, Plum, Orange Blossom, Cardamom',
                'base_notes': 'Ambergris, Clean Musk, Patchouli, Driftwood',
                'longevity_hours': 24,
                'sillage_level': 'Enormous',
                'is_non_alcoholic': False,
                'bundle_text': 'India’s #1 Summer Fragrance Choice',
                'short_description': 'The undeniable king of fresh masculine scents. Juicy Italian apple, aquatic sea breeze, and rich ambergris base with commanding projection.',
                'full_description': 'Rasasi Hawas blends cinnamon, bergamot, orange blossom, and grey amber to create an aquatic scent that embodies masculine adventurous spirit. Highly versatile, it cuts through Indian heat effortlessly and lasts from morning till deep into the evening.',
                'rating_avg': Decimal('4.93'),
                'rating_count': 2670,
                'is_featured': True,
                'liquid_color': '#3B82F6',
                'photo_idx': 6,
                'sizes': ['100ml Eau De Parfum Flacon'],
                'specs': {
                    'Concentration': 'Eau De Parfum (EDP)',
                    'Volume': '100ml',
                    'Origin': 'Dubai, UAE (Rasasi Headquarters)',
                    'Best Season': 'Summer, Monsoon, Spring',
                }
            },
            {
                'name': 'Afnan 9pm Eau De Parfum (100ml)',
                'slug': 'afnan-9pm-eau-de-parfum-100ml',
                'brand': 'afnan',
                'category': 'gourmand-spicy',
                'base_price': Decimal('3600.00'),
                'discount_price': Decimal('2499.00'),
                'discount_percent': 31,
                'fragrance_family': 'Sweet Spicy Oriental',
                'top_notes': 'Wild Apple, Cinnamon, French Lavender, Bergamot',
                'heart_notes': 'Orange Blossom, Lily of the Valley',
                'base_notes': 'Warm Vanilla, Tonka Bean, Golden Amber, Patchouli',
                'longevity_hours': 24,
                'sillage_level': 'Strong',
                'is_non_alcoholic': False,
                'bundle_text': 'Party & Date Night Bestseller',
                'short_description': 'Intoxicating vanilla, crisp spiced apple, and lavender for electric evenings. A high-impact club and party masterpiece.',
                'full_description': 'Afnan 9pm is created for unforgettable nights. Opening with sweet wild apple and aromatic cinnamon, it transitions into smooth orange blossom and a rich foundation of tonka bean and ambered vanilla.',
                'rating_avg': Decimal('4.92'),
                'rating_count': 1950,
                'is_featured': False,
                'liquid_color': '#8B5CF6',
                'photo_idx': 7,
                'sizes': ['100ml Heavy Glass Bottle'],
                'specs': {
                    'Concentration': 'Eau De Parfum',
                    'Volume': '100ml',
                    'Scent Type': 'Sweet, Spicy, Evening Allure',
                }
            },
            {
                'name': 'Ajmal Wisal Dhabab Concentrated Perfume Oil (14ml)',
                'slug': 'ajmal-wisal-dhabab-perfume-oil-14ml',
                'brand': 'ajmal',
                'category': 'floral-rose-attars',
                'base_price': Decimal('2200.00'),
                'discount_price': Decimal('1599.00'),
                'discount_percent': 27,
                'fragrance_family': 'Floral Woody Musky',
                'top_notes': 'Fresh Florals, Green Apple, Peach, Pear',
                'heart_notes': 'Damascus Rose, Jasmine, Royal Geranium, Orchid',
                'base_notes': 'Mysore Sandalwood, Cedarwood, White Musk, Patchouli',
                'longevity_hours': 36,
                'sillage_level': 'Strong',
                'is_non_alcoholic': True,
                'bundle_text': 'Heritage Indian & Arabian Craft Since 1951',
                'short_description': 'Golden flacon with opulent floral rose, fruity nectar, and rich sandalwood. 100% non-alcoholic pure oil from house of Ajmal.',
                'full_description': 'Wisal Dhabab by Ajmal is an alluring oriental floral perfume oil. Housed in a signature golden metallic flacon, it showcases the pinnacle of Ajmal’s decades of artisanal distillation.',
                'rating_avg': Decimal('4.89'),
                'rating_count': 830,
                'is_featured': False,
                'liquid_color': '#D4AF37',
                'photo_idx': 8,
                'sizes': ['14ml Ornate Gold Flacon'],
                'specs': {
                    'Concentration': 'Pure Concentrated Perfume Oil',
                    'Alcohol Content': '0% Alcohol-Free',
                    'Volume': '14ml',
                }
            },
            {
                'name': 'Royal Bakhoor & Incense Burner Gift Set',
                'slug': 'royal-bakhoor-incense-burner-gift-set',
                'brand': 'availsmart-reserve',
                'category': 'bakhoor-incense',
                'base_price': Decimal('2199.00'),
                'discount_price': Decimal('1299.00'),
                'discount_percent': 41,
                'fragrance_family': 'Smoky Resin & Incense',
                'top_notes': 'Omani Frankincense, Cardamom Seed',
                'heart_notes': 'Aged Agarwood Chips, Dried Rose Petals',
                'base_notes': 'Amber Resin, Mysore Sandalwood Shavings',
                'longevity_hours': 36,
                'sillage_level': 'Enormous',
                'is_non_alcoholic': True,
                'bundle_text': 'Complete Set: 50g Chips + Burner + Tongs',
                'short_description': 'Traditional luxury incense ritual. Includes 50g aged scented wood chips soaked in pure fragrant oils and an imperial gold metallic burner.',
                'full_description': 'Transform your home into an Arabian palace with the AvailSmart Royal Bakhoor Set. Infused with natural agarwood shavings, rose oil, and amber resins, burning just one small pinch fills the entire house with soothing fragrant smoke that lasts for days.',
                'rating_avg': Decimal('4.95'),
                'rating_count': 640,
                'is_featured': False,
                'liquid_color': '#78350F',
                'photo_idx': 9,
                'sizes': ['Complete Burner Set (50g + Burner)', 'Bakhoor Chips Refill (100g)'],
                'specs': {
                    'Contents': '50g Bakhoor Jar + Imperial Burner + Charcoal Tongs',
                    'Fragrance Duration': 'Up to 48 Hours in Rooms and Wardrobes',
                }
            },
            {
                'name': 'Pack of 2 Luxury Attar Duo (Shanaya + White Oudh)',
                'slug': 'pack-of-2-luxury-attar-duo-shanaya-white-oudh',
                'brand': 'availsmart-reserve',
                'category': 'gift-combos',
                'base_price': Decimal('2098.00'),
                'discount_price': Decimal('1199.00'),
                'discount_percent': 43,
                'fragrance_family': 'Royal Amber & Oudh',
                'top_notes': 'Sweet Amber, Bergamot, Cardamom',
                'heart_notes': 'Damascus Rose, Aged Cambodian Oudh',
                'base_notes': 'Tonka Bean, Velvet White Musk, Sandalwood',
                'longevity_hours': 36,
                'sillage_level': 'Enormous',
                'is_non_alcoholic': True,
                'bundle_text': 'Bestseller Combo • Save ₹899 Extra',
                'short_description': 'Our two most acclaimed attars paired together in an imperial gift box. Shanaya for sweet evening warmth, White Oudh for crisp daytime royalty.',
                'full_description': 'The definitive luxury combo. Shanaya (12ml) provides hypnotic sweet amber and rose, while Imperial White Oudh (12ml) delivers crisp woody agarwood. 100% alcohol-free, skin safe, and guaranteed 36-hour performance.',
                'rating_avg': Decimal('4.99'),
                'rating_count': 2880,
                'is_featured': True,
                'liquid_color': '#D4AF37',
                'photo_idx': 10,
                'sizes': ['Duo Set (12ml x 2)', 'Duo Set (24ml x 2)'],
                'specs': {
                    'Package Includes': '1x Shanaya (12ml) + 1x Imperial White Oudh (12ml)',
                    'Alcohol Content': '0% Alcohol-Free',
                    'Savings': '43% Off Individual Prices',
                }
            },
            {
                'name': 'Dehn Al Oudh Cambodi Rare Vintage Oil (3ml Crystal Vial)',
                'slug': 'dehn-al-oudh-cambodi-rare-vintage-oil-3ml',
                'brand': 'availsmart-reserve',
                'category': 'rare-cambodian-oudh',
                'base_price': Decimal('7500.00'),
                'discount_price': Decimal('4999.00'),
                'discount_percent': 33,
                'fragrance_family': 'Aged Leather & Barnyard Oudh',
                'top_notes': 'Smoked Wild Agarwood, Earthy Resin',
                'heart_notes': 'Rich Aged Cambodian Oud, Worn Leather',
                'base_notes': 'Balsamic Amber, Dark Honey, Tobacco Leaf',
                'longevity_hours': 36,
                'sillage_level': 'Enormous',
                'is_non_alcoholic': True,
                'bundle_text': '10-Year Aged Pure Artisanal Distillation',
                'short_description': 'Pure 100% uncut aged Cambodian agarwood oil. Thick, resinous, and deeply complex for true collectors of authentic Dehn Al Oudh.',
                'full_description': 'Distilled from wild, mature aquilaria trees in Koh Kong, Cambodia and aged for over a decade in glass carboys. This is uncut pure Dehn Al Oudh with sweet balsamic nuances, rich smoky leather, and an eternal sillage.',
                'rating_avg': Decimal('5.00'),
                'rating_count': 310,
                'is_featured': False,
                'liquid_color': '#3E1F07',
                'photo_idx': 11,
                'sizes': ['3ml Handcrafted Crystal Dipstick Bottle', '6ml Crystal Topped Flacon'],
                'specs': {
                    'Purity': '100% Uncut Artisanal Agarwood Oil',
                    'Harvest Region': 'Koh Kong, Cambodia',
                    'Aging': 'Aged 10+ Years',
                }
            },
            {
                'name': 'Lattafa Yara Candy Eau De Parfum (100ml)',
                'slug': 'lattafa-yara-candy-eau-de-parfum-100ml',
                'brand': 'lattafa',
                'category': 'gourmand-spicy',
                'base_price': Decimal('3200.00'),
                'discount_price': Decimal('2199.00'),
                'discount_percent': 31,
                'fragrance_family': 'Sweet Fruity Gourmand',
                'top_notes': 'Green Tangerine, Blackcurrant, Candied Fruits',
                'heart_notes': 'Strawberry Fizz, Gardenia, Vanilla Cream',
                'base_notes': 'Musk, Amber, Sandalwood, Caramelized Sugar',
                'longevity_hours': 24,
                'sillage_level': 'Strong',
                'is_non_alcoholic': False,
                'bundle_text': 'Viral Feminine Scent with Magnetic Aura',
                'short_description': 'The newest candy iteration of the viral pink Yara perfume. Sugary candied fruits, strawberry fizz, whipped cream, and soft vanilla musk.',
                'full_description': 'Lattafa Yara Candy captures playful youth and luxurious sweetness. Infused with candied berries, fizzy fruits, and creamy vanilla, it creates a trail that turns heads wherever you walk.',
                'rating_avg': Decimal('4.90'),
                'rating_count': 1630,
                'is_featured': False,
                'liquid_color': '#EC4899',
                'photo_idx': 0,
                'sizes': ['100ml Gloss Pink Flacon'],
                'specs': {
                    'Concentration': 'Eau De Parfum',
                    'Volume': '100ml',
                    'Best For': 'Daytime, Parties, Casual Chic',
                }
            },
            {
                'name': 'Adil Qadri Lavish Musk Non-Alcoholic Attar (12ml)',
                'slug': 'adil-qadri-lavish-musk-attar-12ml',
                'brand': 'adil-qadri',
                'category': 'amber-musk-elixirs',
                'base_price': Decimal('1199.00'),
                'discount_price': Decimal('799.00'),
                'discount_percent': 33,
                'fragrance_family': 'Sweet Floral Musk',
                'top_notes': 'Sparkling Citrus, White Florals',
                'heart_notes': 'Damascena Rose, Sweet Honeycomb, Spices',
                'base_notes': 'Royal Musk, Patchouli, Creamy Vanilla',
                'longevity_hours': 36,
                'sillage_level': 'Strong',
                'is_non_alcoholic': True,
                'bundle_text': 'Shark Tank India Featured Scent',
                'short_description': 'Opulent, sweet floral musk designed for memorable presence. 100% alcohol-free roll-on with golden honeyed undertones.',
                'full_description': 'Lavish Musk by Adil Qadri is created for those who enjoy sweet, alluring floral musks with depth. The golden honeyed floral heart develops into a soft, velvety trail of musk that lingers on clothes for days.',
                'rating_avg': Decimal('4.89'),
                'rating_count': 1180,
                'is_featured': False,
                'liquid_color': '#D4AF37',
                'photo_idx': 1,
                'sizes': ['6ml Pocket Roll-On', '12ml Royal Crystal Flacon'],
                'specs': {
                    'Concentration': 'Pure Attar Oil',
                    'Alcohol Content': '0% Non-Alcoholic',
                    'Longevity': '36 Hours',
                }
            },
            {
                'name': 'Ahmed Al Maghribi Marj Extrait De Parfum (60ml)',
                'slug': 'ahmed-al-maghribi-marj-extrait-60ml',
                'brand': 'ahmed-al-maghribi',
                'category': 'dark-oudh-leather',
                'base_price': Decimal('4800.00'),
                'discount_price': Decimal('3699.00'),
                'discount_percent': 23,
                'fragrance_family': 'Rich Leather & Smoky Rose',
                'top_notes': 'Bergamot, Pink Pepper, Elemi, Orange Blossom',
                'heart_notes': 'May Rose, Saffron, Nutmeg, Cardamom',
                'base_notes': 'Leather, Agarwood, Amber, Patchouli, Sandalwood',
                'longevity_hours': 36,
                'sillage_level': 'Enormous',
                'is_non_alcoholic': False,
                'bundle_text': 'Elite Unisex Luxury Extrait',
                'short_description': 'A masterclass in modern Arabian niche perfumery. Spicy saffron, smoky rose, and supple leather in high-concentration extrait format.',
                'full_description': 'Marj by Ahmed Al Maghribi is one of the house’s crowning achievements. Blending vibrant spice with leather, saffron, and incense, it creates a rich dark trail that radiates nobility.',
                'rating_avg': Decimal('4.94'),
                'rating_count': 720,
                'is_featured': False,
                'liquid_color': '#78350F',
                'photo_idx': 2,
                'sizes': ['60ml Heavy Luxury Flacon'],
                'specs': {
                    'Concentration': 'Extrait De Parfum',
                    'Volume': '60ml',
                    'Longevity': '36+ Hours',
                }
            },
            {
                'name': 'AvailSmart Royal Ambergris Concentrated Attar (12ml)',
                'slug': 'availsmart-royal-ambergris-attar-12ml',
                'brand': 'availsmart-reserve',
                'category': 'amber-musk-elixirs',
                'base_price': Decimal('1699.00'),
                'discount_price': Decimal('1099.00'),
                'discount_percent': 35,
                'fragrance_family': 'Warm Golden Amber',
                'top_notes': 'Sweet Orange Peel, Spiced Nutmeg',
                'heart_notes': 'Golden Ambergris, Labdanum, Benzoin',
                'base_notes': 'Dark Vanilla, Cedarwood, Cashmere Musk',
                'longevity_hours': 36,
                'sillage_level': 'Enormous',
                'is_non_alcoholic': True,
                'bundle_text': 'Exclusive Master Distiller Batch',
                'short_description': 'Sensual golden ambergris with warm resinous woods and rich vanilla. 100% alcohol-free pure oil with magnetic cozy warmth.',
                'full_description': 'Royal Ambergris is formulated using traditional enfleurage and aging methods. Opening with spiced citrus, its warm ambergris and labdanum heart wraps you in luxurious, velvety aura that projects for hours.',
                'rating_avg': Decimal('4.92'),
                'rating_count': 860,
                'is_featured': True,
                'liquid_color': '#D97706',
                'photo_idx': 3,
                'sizes': ['6ml Pocket Roll-On', '12ml Royal Crystal Flacon'],
                'specs': {
                    'Concentration': 'Pure Attar Oil',
                    'Alcohol Content': '0% Non-Alcoholic',
                    'Longevity': '36+ Hours',
                }
            },
        ]

        for idx, p in enumerate(products_data):
            self.stdout.write(f"  -> Seeding Product: {p['name']}")
            brand_obj = brands_map.get(p['brand'])
            cat_obj = cats_map.get(p['category'])

            prod = Product.objects.create(
                name=p['name'],
                slug=p['slug'],
                brand=brand_obj,
                category=cat_obj,
                base_price=p['base_price'],
                discount_price=p['discount_price'],
                discount_percent=p['discount_percent'],
                short_description=p['short_description'],
                full_description=p['full_description'],
                fragrance_family=p['fragrance_family'],
                top_notes=p['top_notes'],
                heart_notes=p['heart_notes'],
                base_notes=p['base_notes'],
                longevity_hours=p['longevity_hours'],
                sillage_level=p['sillage_level'],
                is_non_alcoholic=p['is_non_alcoholic'],
                bundle_text=p['bundle_text'],
                rating_avg=p['rating_avg'],
                rating_count=p['rating_count'],
                is_featured=p['is_featured'],
                is_active=True,
                tags=f"fragrance, attar, {p['fragrance_family'].lower()}, alcohol-free, {brand_obj.name.lower()}",
                sku=f"AS-FRAG-{1000 + idx}",
            )

            # Generate / fetch authentic 4:5 portrait images
            photo_id = PERFUME_PHOTO_POOL[p['photo_idx'] % len(PERFUME_PHOTO_POOL)]
            hero_file = fetch_and_crop_perfume_image(
                photo_id,
                title=p['name'],
                subtitle=f"{p['fragrance_family']} • {p['longevity_hours']}h Longevity",
                liquid_color=p['liquid_color']
            )

            # Create default Color / Accent
            accent_name = "Imperial Gold Flacon" if p['is_non_alcoholic'] else "Royal Crystal Spray"
            color_obj = ProductColor.objects.create(
                product=prod,
                color_name=accent_name,
                color_hex='#D4AF37' if p['is_non_alcoholic'] else '#1C529C',
                is_active=True
            )

            # Attach primary image
            img_obj = ProductImage(
                product_color=color_obj,
                is_primary=True,
                alt_text=f"{p['name']} Luxury Fragrance Presentation"
            )
            img_obj.image.save(f"{p['slug']}_hero.webp", hero_file, save=True)

            # Create Size Variants
            for s_idx, s_name in enumerate(p['sizes']):
                # First variant is default price, larger sizes have proportional pricing
                price_add = Decimal('0.00') if s_idx == 0 else Decimal(str(s_idx * 400))
                variant_base = p['base_price'] + price_add
                variant_disc = (p['discount_price'] + price_add) if p['discount_price'] else None

                ProductVariant.objects.create(
                    product=prod,
                    product_color=color_obj,
                    size=s_name,
                    stock_quantity=50 + (s_idx * 20),
                    price=variant_disc or variant_base,
                    sku=f"{prod.sku}-V{s_idx+1}",
                    is_active=True
                )

            # Attach Specifications
            for spec_k, spec_v in p['specs'].items():
                ProductSpecification.objects.create(
                    product=prod,
                    key=spec_k,
                    value=spec_v
                )

            # Add Verified Customer Reviews for Social Proof
            review_user, _ = User.objects.get_or_create(
                email='connoisseur@availsmart.in',
                defaults={
                    'name': 'Fragrance Connoisseur',
                    'is_active': True
                }
            )
            sample_reviews = [
                {
                    'rating': 5,
                    'comment': 'Absolute Beast Longevity! Lasted 2 days on my kurta. I was skeptical about the 36 hour claim, but this fragrance is unreal. The projection is smooth without being overwhelming, and people kept asking what scent I was wearing all evening.'
                },
                {
                    'rating': 5,
                    'comment': '100% Alcohol-Free and Pure Luxury. Gentle on skin, zero irritation, and smells richer than luxury designer perfumes costing 5 times as much. Packaging was stunning.'
                }
            ]
            for r in sample_reviews:
                Review.objects.create(
                    product=prod,
                    user=review_user,
                    rating=r['rating'],
                    comment=r['comment'],
                    is_approved=True
                )

        # ---------------------------------------------------------
        # 5. SEED EDITORIAL HERO BANNERS
        # ---------------------------------------------------------
        self.stdout.write("5. Seeding Fragrance Hero Banners...")
        banner_1_file = create_pro_fallback_perfume_image(
            "THE ROYAL FRAGRANCE ARCHIVE",
            "100% Alcohol-Free Pure Attars & French Sprays",
            liquid_color='#D4AF37',
            width=1600,
            height=700
        )
        b1 = Banner(
            title="The Royal Fragrance Archive",
            subtitle="Distilled from aged Cambodian Oudh, Damascus Rose, and golden amber. 100% Alcohol-Free with guaranteed 36+ hour projection.",
            link="/catalog/",
            button_text="Explore Royal Attars",
            badge_text="2026 Reserve",
            product_tag="Imperial White Oudh Attar",
            price_text="From ₹399 • 100% Pure Oil",
            sort_order=1,
            is_active=True
        )
        b1.image.save("banner_royal_fragrances.webp", banner_1_file, save=True)

        banner_2_file = create_pro_fallback_perfume_image(
            "DISCOVERY BOX AT ₹499",
            "10 Iconic 6ml Samples • Shark Tank Viral Bestseller",
            liquid_color='#1C529C',
            width=1600,
            height=700
        )
        b2 = Banner(
            title="The AvailSmart 10-Fragrance Discovery Box",
            subtitle="Experience 10 iconic luxury attars & French-Arabian EDPs (6ml each) curated for day, evening, and formal rituals.",
            link="/catalog/?deal=discovery",
            button_text="Get Discovery Box @ ₹499",
            badge_text="Special Offer",
            product_tag="Shark Tank Discovery Set",
            price_text="₹499 (50% OFF)",
            sort_order=2,
            is_active=True
        )
        b2.image.save("banner_discovery_box.webp", banner_2_file, save=True)

        # ---------------------------------------------------------
        # 6. SEED PREPAID & COMBO COUPONS
        # ---------------------------------------------------------
        self.stdout.write("6. Seeding Promo & Combo Coupons...")
        Coupon.objects.get_or_create(
            code="UPI50",
            defaults={
                'discount_type': 'flat',
                'value': Decimal('50.00'),
                'min_order': Decimal('299.00'),
                'expiry': timezone.now() + timedelta(days=365),
                'usage_limit': 100000,
                'is_active': True
            }
        )
        Coupon.objects.get_or_create(
            code="TRIO899",
            defaults={
                'discount_type': 'flat',
                'value': Decimal('298.00'),
                'min_order': Decimal('899.00'),
                'expiry': timezone.now() + timedelta(days=365),
                'usage_limit': 100000,
                'is_active': True
            }
        )

        self.stdout.write(self.style.SUCCESS("===> Successfully seeded AvailSmart Luxury Fragrance Catalog!"))
