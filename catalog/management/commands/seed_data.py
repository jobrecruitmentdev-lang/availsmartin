import os
from io import BytesIO
from decimal import Decimal
from PIL import Image, ImageDraw, ImageFont
from django.core.management.base import BaseCommand
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta

from accounts.models import User, Address
from catalog.models import (
    Category, Brand, Product, ProductColor, ProductImage,
    ProductVariant, ProductSpecification, Review, Banner
)
from cart.models import Coupon
from orders.models import Order, OrderItem, Payment


def create_placeholder_image(text, size=(800, 800), bg_color='#047857', text_color='#FFFFFF', subtext=None):
    """
    Creates a styled, crisp image using Pillow and returns a ContentFile.
    """
    img = Image.new('RGB', size, color=bg_color)
    draw = ImageDraw.Draw(img)
    
    # Outer elegant border
    draw.rectangle([20, 20, size[0] - 20, size[1] - 20], outline='#ECFDF5', width=4)
    draw.rectangle([35, 35, size[0] - 35, size[1] - 35], outline='#D1FAE5', width=1)
    
    # Inner badge or decorative block
    badge_box = [60, size[1] - 120, size[0] - 60, size[1] - 60]
    draw.rectangle(badge_box, fill='#064E3B')
    
    # Simple default font drawing without needing external ttf files
    draw.text((80, 80), "AVAILSMART", fill='#D1FAE5')
    draw.text((80, size[1] // 2 - 40), text[:30], fill=text_color)
    if subtext:
        draw.text((80, size[1] // 2 + 10), subtext[:40], fill='#ECFDF5')
    draw.text((80, size[1] - 100), "PREMIUM QUALITY GUARANTEED", fill='#FFFFFF')
    
    buf = BytesIO()
    img.save(buf, format='WEBP', quality=88, optimize=True)
    buf.seek(0)
    return ContentFile(buf.read())


class Command(BaseCommand):
    help = 'Seeds database with realistic multi-category products, colors, images, variants, users, coupons, and banners.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("==> Seeding AvailSmart Database..."))

        # 1. USERS & ADDRESSES
        self.stdout.write("1. Creating Users & Addresses...")
        admin_user, _ = User.objects.get_or_create(
            email='admin@availsmart.com',
            defaults={
                'name': 'AvailSmart Admin',
                'phone': '+91 9876543210',
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )
        admin_user.set_password('Admin@123')
        admin_user.save()

        customer1, _ = User.objects.get_or_create(
            email='rohit.sharma@example.com',
            defaults={
                'name': 'Rohit Sharma',
                'phone': '+91 9812345678',
                'is_active': True,
            }
        )
        customer1.set_password('Customer@123')
        customer1.save()

        customer2, _ = User.objects.get_or_create(
            email='priya.patel@example.com',
            defaults={
                'name': 'Priya Patel',
                'phone': '+91 9898765432',
                'is_active': True,
            }
        )
        customer2.set_password('Customer@123')
        customer2.save()

        # Addresses
        Address.objects.get_or_create(
            user=customer1,
            full_name='Rohit Sharma',
            phone='+91 9812345678',
            address_line1='Flat 402, Green Glen Heights, Outer Ring Road',
            address_line2='Near Bellandur Flyover',
            city='Bengaluru',
            state='Karnataka',
            pincode='560103',
            country='India',
            address_type='home',
            is_default=True,
        )
        Address.objects.get_or_create(
            user=customer1,
            full_name='Rohit Sharma (Office)',
            phone='+91 9812345678',
            address_line1='Tech Park 4, 3rd Floor, Embassy TechVillage',
            address_line2='Devarabisanahalli',
            city='Bengaluru',
            state='Karnataka',
            pincode='560103',
            country='India',
            address_type='work',
            is_default=False,
        )

        Address.objects.get_or_create(
            user=customer2,
            full_name='Priya Patel',
            phone='+91 9898765432',
            address_line1='A-12, Sagar Darshan Society, Carter Road',
            address_line2='Bandra West',
            city='Mumbai',
            state='Maharashtra',
            pincode='400050',
            country='India',
            address_type='home',
            is_default=True,
        )

        # 2. CATEGORIES (Parent and Sub-categories)
        self.stdout.write("2. Creating Categories & Subcategories...")
        categories_data = [
            {
                'name': 'Fashion',
                'slug': 'fashion',
                'desc': 'Trendsetting apparel, footwear, and designer wardrobe essentials.',
                'children': [
                    {'name': "Men's Apparel", 'slug': 'mens-apparel', 'desc': 'Casual shirts, t-shirts, jackets, and trousers.'},
                    {'name': "Women's Apparel", 'slug': 'womens-apparel', 'desc': 'Dresses, kurtas, tops, and activewear.'},
                    {'name': 'Footwear & Sneakers', 'slug': 'footwear-sneakers', 'desc': 'Casual sneakers, formal shoes, and sports runners.'},
                ]
            },
            {
                'name': 'Electronics',
                'slug': 'electronics',
                'desc': 'Smart tech, wireless audio, computing devices, and accessories.',
                'children': [
                    {'name': 'Smart Audio & Headphones', 'slug': 'smart-audio-headphones', 'desc': 'Noise-cancelling headphones and true wireless earbuds.'},
                    {'name': 'Smartphones & Tablets', 'slug': 'smartphones-tablets', 'desc': 'Flagship phones, tablets, and high-performance chargers.'},
                    {'name': 'Smart Watches & Wearables', 'slug': 'smart-watches-wearables', 'desc': 'Fitness tracking smartwatches and health rings.'},
                ]
            },
            {
                'name': 'Home & Living',
                'slug': 'home-living',
                'desc': 'Modern furniture, cozy bedding, lamps, and culinary essentials.',
                'children': [
                    {'name': 'Kitchen & Dining', 'slug': 'kitchen-dining', 'desc': 'Cookware, coffee makers, and porcelain dinner sets.'},
                    {'name': 'Luxury Bedding', 'slug': 'luxury-bedding', 'desc': 'Egyptian cotton sheets, duvets, and memory foam pillows.'},
                    {'name': 'Home Decor & Lighting', 'slug': 'home-decor-lighting', 'desc': 'Minimalist table lamps, wall art, and aromatic diffusers.'},
                ]
            },
            {
                'name': 'Beauty & Wellness',
                'slug': 'beauty-wellness',
                'desc': 'Dermatologist-approved skincare, fragrances, and personal grooming.',
                'children': [
                    {'name': 'Skincare & Serums', 'slug': 'skincare-serums', 'desc': 'Vitamin C serums, sunscreens, and hydrators.'},
                    {'name': 'Luxury Fragrances', 'slug': 'luxury-fragrances', 'desc': 'Eau de parfum, colognes, and body mists.'},
                ]
            },
            {
                'name': 'Lifestyle & Fitness',
                'slug': 'lifestyle-fitness',
                'desc': 'Bags, luggage, workout gear, and everyday adventure essentials.',
                'children': [
                    {'name': 'Bags & Backpacks', 'slug': 'bags-backpacks', 'desc': 'Waterproof commuter backpacks and weekend duffels.'},
                    {'name': 'Yoga & Fitness Gear', 'slug': 'yoga-fitness-gear', 'desc': 'Eco-friendly yoga mats, resistance bands, and foam rollers.'},
                ]
            },
        ]

        category_objs = {}
        for cat_data in categories_data:
            cat, _ = Category.objects.get_or_create(
                slug=cat_data['slug'],
                defaults={
                    'name': cat_data['name'],
                    'description': cat_data['desc'],
                    'is_active': True,
                    'sort_order': len(category_objs),
                }
            )
            # Create category thumbnail if missing
            if not cat.image:
                img_file = create_placeholder_image(cat.name, size=(600, 600), bg_color='#065F46', subtext=cat.description)
                cat.image.save(f"cat_{cat.slug}.webp", img_file, save=True)

            category_objs[cat.slug] = cat

            for sub_idx, sub_data in enumerate(cat_data['children']):
                sub_cat, _ = Category.objects.get_or_create(
                    slug=sub_data['slug'],
                    defaults={
                        'name': sub_data['name'],
                        'parent': cat,
                        'description': sub_data['desc'],
                        'is_active': True,
                        'sort_order': sub_idx,
                    }
                )
                if not sub_cat.image:
                    sub_img = create_placeholder_image(sub_cat.name, size=(600, 600), bg_color='#047857', subtext=sub_data['desc'])
                    sub_cat.image.save(f"subcat_{sub_cat.slug}.webp", sub_img, save=True)
                category_objs[sub_cat.slug] = sub_cat

        # 3. BRANDS
        self.stdout.write("3. Creating Brands...")
        brands_data = [
            {'name': 'Apple', 'slug': 'apple'},
            {'name': 'Nike', 'slug': 'nike'},
            {'name': 'Samsung', 'slug': 'samsung'},
            {'name': 'Sony', 'slug': 'sony'},
            {'name': 'Zara', 'slug': 'zara'},
            {'name': 'Philips', 'slug': 'philips'},
            {'name': 'Puma', 'slug': 'puma'},
            {'name': 'Dyson', 'slug': 'dyson'},
            {'name': "L'Oreal", 'slug': 'loreal'},
            {'name': 'Bose', 'slug': 'bose'},
            {'name': 'Titan', 'slug': 'titan'},
            {'name': 'Ikea', 'slug': 'ikea'},
        ]
        brand_objs = {}
        for b in brands_data:
            brand, _ = Brand.objects.get_or_create(
                slug=b['slug'],
                defaults={'name': b['name'], 'is_active': True}
            )
            if not brand.logo:
                logo_file = create_placeholder_image(brand.name, size=(400, 400), bg_color='#064E3B', text_color='#ECFDF5', subtext="Official Brand Partner")
                brand.logo.save(f"brand_{brand.slug}.webp", logo_file, save=True)
            brand_objs[brand.slug] = brand

        # 4. PRODUCTS WITH MULTI-COLOR, MULTI-IMAGE, AND SIZE VARIANTS
        self.stdout.write("4. Creating Rich Products with Colors, Images, Variants & Specs...")

        products_catalog = [
            {
                'name': 'AeroGlide Ultra Breathable Running Shoes',
                'slug': 'aeroglide-ultra-breathable-running-shoes',
                'category': 'footwear-sneakers',
                'brand': 'nike',
                'short_desc': 'Featherlight cushioned running sneakers with responsive ZoomX foam and breathable mesh upper.',
                'full_desc': 'Designed for marathon runners and urban sprinters alike. The AeroGlide Ultra combines advanced kinetic energy return with an engineered mesh weave that keeps feet cool over long distances. High-traction rubber outsole guarantees superior wet and dry grip.',
                'base_price': Decimal('7999.00'),
                'discount_price': Decimal('5999.00'),
                'sku': 'NK-AERO-01',
                'weight': Decimal('0.65'),
                'material': 'Recycled Engineered Mesh & Foam',
                'tags': 'shoes, sneakers, running, nike, sports, fitness',
                'is_featured': True,
                'specs': [
                    ('Closure', 'Lace-Up'),
                    ('Sole Material', 'ZoomX Rubber Foam'),
                    ('Arch Support', 'Neutral to High'),
                    ('Warranty', '6 Months Manufacturer Warranty'),
                ],
                'colors': [
                    {
                        'name': 'Emerald Forest',
                        'hex': '#047857',
                        'images': ['Profile View', 'Sole & Cushion Detail', 'Top Down Angled'],
                        'sizes': [
                            {'size': 'UK 7', 'sku': 'NK-AERO-GRN-07', 'stock': 25, 'price': Decimal('5999.00')},
                            {'size': 'UK 8', 'sku': 'NK-AERO-GRN-08', 'stock': 40, 'price': Decimal('5999.00')},
                            {'size': 'UK 9', 'sku': 'NK-AERO-GRN-09', 'stock': 30, 'price': Decimal('5999.00')},
                            {'size': 'UK 10', 'sku': 'NK-AERO-GRN-10', 'stock': 15, 'price': Decimal('5999.00')},
                        ]
                    },
                    {
                        'name': 'Midnight Stealth Black',
                        'hex': '#1E293B',
                        'images': ['Profile Angle View', 'Rear Heel Counter', 'Reflective Night Shot'],
                        'sizes': [
                            {'size': 'UK 7', 'sku': 'NK-AERO-BLK-07', 'stock': 18, 'price': Decimal('5999.00')},
                            {'size': 'UK 8', 'sku': 'NK-AERO-BLK-08', 'stock': 50, 'price': Decimal('5999.00')},
                            {'size': 'UK 9', 'sku': 'NK-AERO-BLK-09', 'stock': 35, 'price': Decimal('5999.00')},
                            {'size': 'UK 10', 'sku': 'NK-AERO-BLK-10', 'stock': 20, 'price': Decimal('5999.00')},
                        ]
                    },
                    {
                        'name': 'Solar Orange Accent',
                        'hex': '#F97316',
                        'images': ['Dynamic Side Angle', 'Sole Grip Close-Up'],
                        'sizes': [
                            {'size': 'UK 8', 'sku': 'NK-AERO-ORG-08', 'stock': 22, 'price': Decimal('6299.00')},
                            {'size': 'UK 9', 'sku': 'NK-AERO-ORG-09', 'stock': 14, 'price': Decimal('6299.00')},
                        ]
                    }
                ],
                'reviews': [
                    {'user': customer1, 'rating': 5, 'comment': 'Incredible comfort right out of the box! Ran 10k without any hotspots.'},
                    {'user': customer2, 'rating': 4, 'comment': 'Love the emerald green colorway. Very stylish and bouncy.'},
                ]
            },
            {
                'name': 'SonicPulse Pro ANC Wireless Headphones',
                'slug': 'sonicpulse-pro-anc-wireless-headphones',
                'category': 'smart-audio-headphones',
                'brand': 'sony',
                'short_desc': 'Flagship active noise cancellation headphones with Hi-Res Audio, LDAC, and 40-hour playback.',
                'full_desc': 'Immerse yourself in concert-grade acoustic fidelity. The SonicPulse Pro features quad-microphone adaptive hybrid noise cancellation that nullifies airplane cabin hum and office chatter. Plush vegan leather earcups provide fatigue-free all-day comfort.',
                'base_price': Decimal('18990.00'),
                'discount_price': Decimal('14999.00'),
                'sku': 'SN-SONIC-40',
                'weight': Decimal('0.25'),
                'material': 'Anodized Aluminum & Memory Foam',
                'tags': 'audio, headphones, wireless, bluetooth, anc, sony',
                'is_featured': True,
                'specs': [
                    ('Driver Size', '40mm Liquid Crystal Polymer'),
                    ('Battery Life', '40 Hours (ANC On) / 55 Hours (ANC Off)'),
                    ('Charging', 'USB-C Quick Charge (10 min = 5 hours)'),
                    ('Connectivity', 'Bluetooth 5.3, Multipoint, 3.5mm AUX'),
                ],
                'colors': [
                    {
                        'name': 'Matte Silver & Mint',
                        'hex': '#10B981',
                        'images': ['Front Headband Perspective', 'Ear Cup Detail', 'Folded Travel Case'],
                        'sizes': [
                            {'size': 'Standard Over-Ear', 'sku': 'SN-SONIC-MNT', 'stock': 35, 'price': Decimal('14999.00')},
                        ]
                    },
                    {
                        'name': 'Obsidian Carbon Black',
                        'hex': '#0F172A',
                        'images': ['Side Profile', 'Earcup Swivel View', 'Lifestyle Studio Shot'],
                        'sizes': [
                            {'size': 'Standard Over-Ear', 'sku': 'SN-SONIC-BLK', 'stock': 45, 'price': Decimal('14999.00')},
                        ]
                    }
                ],
                'reviews': [
                    {'user': customer1, 'rating': 5, 'comment': 'ANC is next level. Blocks out completely the metro commute noise.'},
                ]
            },
            {
                'name': 'Titan Edge Minimalist Chronograph Watch',
                'slug': 'titan-edge-minimalist-chronograph-watch',
                'category': 'smart-watches-wearables',
                'brand': 'titan',
                'short_desc': 'Sleek ultra-slim stainless steel quartz chronograph with sapphire crystal and genuine leather strap.',
                'full_desc': 'The epitome of refined wristwear. Engineered with a precision Swiss movement, water resistance up to 50 meters, and a sunray dial that catches light from every angle. Ideal for boardroom meetings and formal dinners alike.',
                'base_price': Decimal('12495.00'),
                'discount_price': Decimal('9995.00'),
                'sku': 'TT-EDGE-50',
                'weight': Decimal('0.14'),
                'material': '316L Surgical Grade Stainless Steel',
                'tags': 'watch, chronograph, titan, luxury, fashion',
                'is_featured': True,
                'specs': [
                    ('Dial Glass', 'Scratch-resistant Sapphire Crystal'),
                    ('Water Resistance', '5 ATM (50m)'),
                    ('Case Diameter', '41 mm'),
                    ('Movement', 'Quartz Multi-Function Chronograph'),
                ],
                'colors': [
                    {
                        'name': 'Emerald Sunray Dial & Tan Leather',
                        'hex': '#047857',
                        'images': ['Dial Face Straight View', 'Crown and Pushers Macro', 'Buckle and Leather Texture'],
                        'sizes': [
                            {'size': '41mm Case', 'sku': 'TT-EDGE-EMR-41', 'stock': 20, 'price': Decimal('9995.00')},
                        ]
                    },
                    {
                        'name': 'Classic Silver & Midnight Blue',
                        'hex': '#1E3A8A',
                        'images': ['Front Blue Dial', 'Rear Caseback Engraving'],
                        'sizes': [
                            {'size': '41mm Case', 'sku': 'TT-EDGE-BLU-41', 'stock': 28, 'price': Decimal('9995.00')},
                        ]
                    }
                ],
                'reviews': [
                    {'user': customer2, 'rating': 5, 'comment': 'Gifted to my husband. The green dial looks exceptionally rich in natural sunlight!'},
                ]
            },
            {
                'name': 'Urban Commuter Waterproof Laptop Backpack (28L)',
                'slug': 'urban-commuter-waterproof-laptop-backpack-28l',
                'category': 'bags-backpacks',
                'brand': 'nike',
                'short_desc': 'Ergonomic 28-liter weatherproof backpack with dedicated 16-inch fleece laptop sleeve and hidden anti-theft pocket.',
                'full_desc': 'Built for modern tech professionals and weekend explorers. Crafted with recycled Cordura ballistic fabric and TPU water-repellent zippers. Features an airflow mesh back panel that prevents sweating during hot summer commutes.',
                'base_price': Decimal('4999.00'),
                'discount_price': Decimal('3499.00'),
                'sku': 'NK-URBAN-28',
                'weight': Decimal('0.85'),
                'material': '1000D Ballistic Cordura Nylon',
                'tags': 'backpack, travel, bag, laptop bag, waterproof',
                'is_featured': False,
                'specs': [
                    ('Capacity', '28 Liters'),
                    ('Laptop Compartment', 'Fits up to 16.2 inch MacBook Pro / Gaming Laptops'),
                    ('Rain Protection', 'Weatherproof TPU Coating + Integrated Rainfly'),
                    ('Warranty', '3 Years International Guarantee'),
                ],
                'colors': [
                    {
                        'name': 'Alpine Olive Forest',
                        'hex': '#065F46',
                        'images': ['Front Commuter Profile', 'Open Organization Compartment', 'Back Airflow Mesh Straps'],
                        'sizes': [
                            {'size': 'One Size (28L)', 'sku': 'NK-BAG-OLV-28', 'stock': 50, 'price': Decimal('3499.00')},
                        ]
                    },
                    {
                        'name': 'Stealth Matte Black',
                        'hex': '#111827',
                        'images': ['Front Matte Black', 'Side Water Bottle Pocket'],
                        'sizes': [
                            {'size': 'One Size (28L)', 'sku': 'NK-BAG-BLK-28', 'stock': 65, 'price': Decimal('3499.00')},
                        ]
                    }
                ],
                'reviews': [
                    {'user': customer1, 'rating': 5, 'comment': 'Survived heavy monsoon rain without a single drop reaching my laptop. 10/10.'},
                ]
            },
            {
                'name': 'Botanical Glow Niacinamide & Squalane Facial Serum (50ml)',
                'slug': 'botanical-glow-niacinamide-squalane-facial-serum',
                'category': 'skincare-serums',
                'brand': 'loreal',
                'short_desc': 'Pure botanical antioxidant elixir that refines enlarged pores, restores lipid barrier, and evens skin tone.',
                'full_desc': 'Formulated with 10% pure Niacinamide, plant-derived sugarcane Squalane, and calming centella asiatica extract. Absorbs instantly into skin without greasy residue, leaving a glass-skin dewy finish suitable for all skin types.',
                'base_price': Decimal('1499.00'),
                'discount_price': Decimal('999.00'),
                'sku': 'LO-SERUM-50',
                'weight': Decimal('0.18'),
                'material': 'Cruelty-Free Glass Dropper Bottle',
                'tags': 'beauty, skincare, serum, niacinamide, glowing skin',
                'is_featured': True,
                'specs': [
                    ('Key Actives', '10% Niacinamide + 2% Squalane + Centella Asiatica'),
                    ('Volume', '50 ml / 1.7 fl oz'),
                    ('Skin Type', 'All skin types, including sensitive and acne-prone'),
                    ('Certifications', '100% Vegan, Dermatologist Tested, Paraben Free'),
                ],
                'colors': [
                    {
                        'name': 'Emerald Glass Bottle',
                        'hex': '#047857',
                        'images': ['Product Bottle with Dropper', 'Serum Texture Swatch on Skin', 'Packaging Box View'],
                        'sizes': [
                            {'size': '50 ml', 'sku': 'LO-SERUM-50ML', 'stock': 120, 'price': Decimal('999.00')},
                            {'size': '100 ml Jumbo', 'sku': 'LO-SERUM-100ML', 'stock': 60, 'price': Decimal('1699.00')},
                        ]
                    }
                ],
                'reviews': [
                    {'user': customer2, 'rating': 5, 'comment': 'Noticeable difference in redness and pore size within 2 weeks! Will definitely repurchase.'},
                ]
            },
            {
                'name': 'Scandinavian Ceramic Pour-Over Coffee Brewer Set',
                'slug': 'scandinavian-ceramic-pour-over-coffee-brewer-set',
                'category': 'kitchen-dining',
                'brand': 'ikea',
                'short_desc': 'Handcrafted matte ceramic dripper with thermal borosilicate glass carafe and reusable stainless steel mesh filter.',
                'full_desc': 'Brew barista-grade pour-over coffee right in your kitchen. Engineered conical spiral ribs guide water flow evenly through the coffee bed for maximum flavor extraction and aromatic depth. Includes heat-resistant silicone neck grip.',
                'base_price': Decimal('2999.00'),
                'discount_price': Decimal('2199.00'),
                'sku': 'IK-POUR-SET',
                'weight': Decimal('0.72'),
                'material': 'Artisanal Ceramic & Borosilicate Glass',
                'tags': 'home, kitchen, coffee, brewer, scandinavian',
                'is_featured': False,
                'specs': [
                    ('Carafe Capacity', '600 ml (2-4 cups)'),
                    ('Heat Resistance', 'Up to 150°C thermal shock resistant'),
                    ('Dishwasher Safe', 'Yes, all components'),
                ],
                'colors': [
                    {
                        'name': 'Nordic Sage Mint',
                        'hex': '#10B981',
                        'images': ['Complete Carafe & Dripper Assembly', 'Ceramic Dripper Top View', 'Brewing Action Shot'],
                        'sizes': [
                            {'size': '600 ml Set', 'sku': 'IK-COFF-SAGE', 'stock': 40, 'price': Decimal('2199.00')},
                        ]
                    },
                    {
                        'name': 'Matte Chalk White',
                        'hex': '#F8FAFC',
                        'images': ['Chalk White Dripper', 'Kitchen Counter Setup'],
                        'sizes': [
                            {'size': '600 ml Set', 'sku': 'IK-COFF-WHT', 'stock': 35, 'price': Decimal('2199.00')},
                        ]
                    }
                ],
                'reviews': [
                    {'user': customer1, 'rating': 4, 'comment': 'Makes clean, crisp coffee every morning. Looks gorgeous on the countertop.'},
                ]
            },
            {
                'name': 'Pure Linen Relaxed Fit Resort Shirt',
                'slug': 'pure-linen-relaxed-fit-resort-shirt',
                'category': 'mens-apparel',
                'brand': 'zara',
                'short_desc': '100% French flax washed linen shirt with Cuban camp collar and Mother of Pearl buttons.',
                'full_desc': 'The timeless vacation staple. Crafted from premium breathable flax linen that softens with every wash. Designed with a relaxed drape, drop shoulders, and side hem vents for effortless tropical and summer styling.',
                'base_price': Decimal('3590.00'),
                'discount_price': Decimal('2490.00'),
                'sku': 'ZR-LINEN-SH',
                'weight': Decimal('0.30'),
                'material': '100% French Flax Linen',
                'tags': 'fashion, men, clothing, linen, shirts, zara',
                'is_featured': True,
                'specs': [
                    ('Collar Type', 'Cuban Camp Collar'),
                    ('Fit', 'Relaxed Boxy Fit'),
                    ('Care Instructions', 'Machine wash cold delicate, hang dry'),
                ],
                'colors': [
                    {
                        'name': 'Seafoam Emerald',
                        'hex': '#047857',
                        'images': ['Front Model Studio View', 'Fabric Weave & Collar Close Up', 'Back Hem Silhouette'],
                        'sizes': [
                            {'size': 'S', 'sku': 'ZR-LIN-SFM-S', 'stock': 15, 'price': Decimal('2490.00')},
                            {'size': 'M', 'sku': 'ZR-LIN-SFM-M', 'stock': 35, 'price': Decimal('2490.00')},
                            {'size': 'L', 'sku': 'ZR-LIN-SFM-L', 'stock': 30, 'price': Decimal('2490.00')},
                            {'size': 'XL', 'sku': 'ZR-LIN-SFM-XL', 'stock': 12, 'price': Decimal('2490.00')},
                        ]
                    },
                    {
                        'name': 'Natural Ecru Linen',
                        'hex': '#F3F4F6',
                        'images': ['Ecru Linen Front', 'Button Detail Macro'],
                        'sizes': [
                            {'size': 'S', 'sku': 'ZR-LIN-ECR-S', 'stock': 20, 'price': Decimal('2490.00')},
                            {'size': 'M', 'sku': 'ZR-LIN-ECR-M', 'stock': 40, 'price': Decimal('2490.00')},
                            {'size': 'L', 'sku': 'ZR-LIN-ECR-L', 'stock': 25, 'price': Decimal('2490.00')},
                            {'size': 'XL', 'sku': 'ZR-LIN-ECR-XL', 'stock': 15, 'price': Decimal('2490.00')},
                        ]
                    }
                ],
                'reviews': [
                    {'user': customer1, 'rating': 5, 'comment': 'Best linen shirt I own. Super airy and fits true to size with a nice drape.'},
                ]
            },
            {
                'name': 'SmartSense Smart Ambient Floor Lamp with RGBIC Sync',
                'slug': 'smartsense-smart-ambient-floor-lamp-with-rgbic-sync',
                'category': 'home-decor-lighting',
                'brand': 'philips',
                'short_desc': 'Minimalist corner floor lamp with 16 million colors, voice control (Alexa/Google), and music audio rhythm sync.',
                'full_desc': 'Transform any room into a tranquil retreat or an energetic party space. SmartSense features segmented RGBIC technology, allowing multiple gradient shades to flow up the aluminum stem simultaneously. Controlled via smartphone app or touch panel.',
                'base_price': Decimal('8999.00'),
                'discount_price': Decimal('6499.00'),
                'sku': 'PH-SMART-LAMP',
                'weight': Decimal('2.40'),
                'material': 'Aviation Anodized Aluminum & Acrylic Diffuser',
                'tags': 'lighting, home, smart home, alexa, decor, philips',
                'is_featured': False,
                'specs': [
                    ('Height', '145 cm (57 inches)'),
                    ('Brightness', '1200 Lumens (Adjustable 1-100%)'),
                    ('Color Temperature', '2200K - 6500K Tunable White + RGBIC'),
                    ('Connectivity', 'Wi-Fi 2.4GHz + Bluetooth BLE'),
                ],
                'colors': [
                    {
                        'name': 'Matte Dark Emerald Base',
                        'hex': '#064E3B',
                        'images': ['Lit Lamp in Living Room Corner', 'App Color Wheel Display', 'Base & Foot Switch Detail'],
                        'sizes': [
                            {'size': '145cm Standard', 'sku': 'PH-LAMP-EMR', 'stock': 30, 'price': Decimal('6499.00')},
                        ]
                    },
                    {
                        'name': 'Anodized Space Silver',
                        'hex': '#E2E8F0',
                        'images': ['Silver Unlit Stance', 'Night Lighting Effect'],
                        'sizes': [
                            {'size': '145cm Standard', 'sku': 'PH-LAMP-SLV', 'stock': 25, 'price': Decimal('6499.00')},
                        ]
                    }
                ],
                'reviews': [
                    {'user': customer2, 'rating': 5, 'comment': 'The warm white light is soothing for reading, and movie mode sync is unbelievable!'},
                ]
            }
        ]

        for pdata in products_catalog:
            prod_cat = category_objs.get(pdata['category'])
            prod_brand = brand_objs.get(pdata['brand'])

            product, created = Product.objects.get_or_create(
                slug=pdata['slug'],
                defaults={
                    'name': pdata['name'],
                    'category': prod_cat,
                    'brand': prod_brand,
                    'short_description': pdata['short_desc'],
                    'full_description': pdata['full_desc'],
                    'base_price': pdata['base_price'],
                    'discount_price': pdata['discount_price'],
                    'sku': pdata['sku'],
                    'weight': pdata['weight'],
                    'material': pdata['material'],
                    'tags': pdata['tags'],
                    'is_featured': pdata['is_featured'],
                    'is_active': True,
                    'meta_title': f"{pdata['name']} - Buy Online at AvailSmart",
                    'meta_description': pdata['short_desc'],
                }
            )

            # Specifications
            for spec_idx, (s_key, s_val) in enumerate(pdata['specs']):
                ProductSpecification.objects.get_or_create(
                    product=product,
                    key=s_key,
                    defaults={'value': s_val, 'sort_order': spec_idx}
                )

            # Colors and Images and Variants
            for c_idx, col_data in enumerate(pdata['colors']):
                color, _ = ProductColor.objects.get_or_create(
                    product=product,
                    color_name=col_data['name'],
                    defaults={
                        'color_hex': col_data['hex'],
                        'sort_order': c_idx,
                        'is_active': True,
                    }
                )

                # Images for THIS specific color
                for img_idx, img_title in enumerate(col_data['images']):
                    is_prim = (c_idx == 0 and img_idx == 0)
                    existing_img = ProductImage.objects.filter(product_color=color, sort_order=img_idx).first()
                    if not existing_img:
                        p_img = ProductImage(
                            product_color=color,
                            alt_text=f"{product.name} in {color.color_name} - {img_title}",
                            is_primary=is_prim,
                            sort_order=img_idx,
                        )
                        # Distinct image per color and angle
                        file_obj = create_placeholder_image(
                            text=f"{product.name[:24]}",
                            size=(800, 800),
                            bg_color=color.color_hex if color.color_hex.startswith('#') else '#047857',
                            text_color='#FFFFFF' if color.color_hex not in ('#F8FAFC', '#F3F4F6') else '#0F172A',
                            subtext=f"Color: {color.color_name} | {img_title}"
                        )
                        p_img.image.save(f"prod_{product.id}_{color.id}_{img_idx}.webp", file_obj, save=True)

                # Variants for THIS specific color
                for v_data in col_data['sizes']:
                    ProductVariant.objects.get_or_create(
                        product=product,
                        product_color=color,
                        size=v_data['size'],
                        defaults={
                            'sku': v_data['sku'],
                            'stock_quantity': v_data['stock'],
                            'price': v_data['price'],
                            'is_active': True,
                        }
                    )

            # Reviews
            for r_data in pdata.get('reviews', []):
                review, _ = Review.objects.get_or_create(
                    user=r_data['user'],
                    product=product,
                    defaults={
                        'rating': r_data['rating'],
                        'comment': r_data['comment'],
                        'is_approved': True,
                    }
                )
            product.update_rating_stats()

        # 5. COUPONS
        self.stdout.write("5. Creating Promotional Coupons...")
        coupons_list = [
            {
                'code': 'WELCOME50',
                'type': 'percent',
                'val': Decimal('50.00'),
                'min_order': Decimal('999.00'),
                'limit': 500,
            },
            {
                'code': 'AVAIL20',
                'type': 'percent',
                'val': Decimal('20.00'),
                'min_order': Decimal('1499.00'),
                'limit': 1000,
            },
            {
                'code': 'FLAT500',
                'type': 'flat',
                'val': Decimal('500.00'),
                'min_order': Decimal('2499.00'),
                'limit': 200,
            },
            {
                'code': 'SMART10',
                'type': 'percent',
                'val': Decimal('10.00'),
                'min_order': Decimal('499.00'),
                'limit': 2000,
            },
        ]
        future_date = timezone.now() + timedelta(days=90)
        for c in coupons_list:
            Coupon.objects.get_or_create(
                code=c['code'],
                defaults={
                    'discount_type': c['type'],
                    'value': c['val'],
                    'min_order': c['min_order'],
                    'expiry': future_date,
                    'usage_limit': c['limit'],
                    'is_active': True,
                }
            )

        # 6. HOMEPAGE BANNERS
        self.stdout.write("6. Creating Homepage Banners...")
        banners_data = [
            {
                'title': 'The Green Season Sale - Up to 50% Off',
                'subtitle': 'Discover certified sustainable electronics, designer apparel, and eco living essentials.',
                'link': '/catalog/?tag=trending',
                'sort': 0,
            },
            {
                'title': 'Next-Gen Wireless Audio & Smart Wearables',
                'subtitle': 'Studio quality sound meets all-day battery life. Explore the 2026 Collection.',
                'link': '/catalog/electronics/',
                'sort': 1,
            },
            {
                'title': 'Elevate Your Sanctuary - Artisan Home Decor',
                'subtitle': 'Handmade ceramic brewers, ambient smart lighting, and French flax linen.',
                'link': '/catalog/home-living/',
                'sort': 2,
            },
        ]
        for b_idx, b in enumerate(banners_data):
            banner, created = Banner.objects.get_or_create(
                title=b['title'],
                defaults={
                    'subtitle': b['subtitle'],
                    'link': b['link'],
                    'sort_order': b['sort'],
                    'is_active': True,
                }
            )
            if not banner.image:
                banner_file = create_placeholder_image(
                    text=b['title'][:32],
                    size=(1600, 600),
                    bg_color='#064E3B' if b_idx == 0 else ('#047857' if b_idx == 1 else '#065F46'),
                    text_color='#FFFFFF',
                    subtext=b['subtitle'][:60]
                )
                banner.image.save(f"banner_{b_idx + 1}.webp", banner_file, save=True)

        self.stdout.write(self.style.SUCCESS("==> Database successfully seeded with full production test data!"))
