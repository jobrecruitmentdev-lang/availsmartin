import sys
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.db import transaction
from catalog.models import Category


MASTER_VERTICALS = [
    {
        "name": "Fashion & Clothing",
        "description": "Men's, women's, ethnic, western, luxury, and designer apparel collections.",
        "subcategories": [
            "Men's Fashion", "Women's Fashion", "Kids' Fashion", "Baby Fashion",
            "Unisex Fashion", "Ethnic Wear", "Western Wear", "Luxury Fashion",
            "Designer Fashion", "Plus Size Fashion", "Sportswear", "Activewear",
            "Innerwear & Lingerie", "Sleepwear & Nightwear", "Winter Wear",
            "Summer Wear", "Maternity Wear", "Bridal Wear", "Party Wear",
            "Traditional Clothing"
        ]
    },
    {
        "name": "Footwear",
        "description": "Men's, women's, formal, sports, sneakers, and designer footwear.",
        "subcategories": [
            "Men's Shoes", "Women's Shoes", "Kids' Shoes", "Sneakers",
            "Sports Shoes", "Casual Shoes", "Formal Shoes", "Boots",
            "Sandals & Slippers", "Luxury Footwear"
        ]
    },
    {
        "name": "Watches & Jewellery",
        "description": "Luxury watches, smartwatches, fine gold, silver, and diamond jewellery.",
        "subcategories": [
            "Men's Watches", "Women's Watches", "Luxury Watches", "Smartwatches",
            "Fitness Bands", "Men's Jewellery", "Women's Jewellery", "Gold Jewellery",
            "Silver Jewellery", "Diamond Jewellery", "Fashion Jewellery",
            "Bridal Jewellery", "Couple Jewellery"
        ]
    },
    {
        "name": "Fashion Accessories",
        "description": "Handbags, backpacks, sunglasses, eyewear, belts, and styling accessories.",
        "subcategories": [
            "Men's Accessories", "Women's Accessories", "Sunglasses", "Eyewear",
            "Handbags", "Backpacks", "Wallets", "Belts", "Caps & Hats",
            "Scarves & Stoles", "Hair Accessories", "Travel Accessories",
            "Curated Styling Accessories"
        ]
    },
    {
        "name": "Electronics & Technology",
        "description": "Smartphones, laptops, audio, cameras, gaming, and smart home gadgets.",
        "subcategories": [
            "Mobile Phones", "Mobile Accessories", "Laptops", "Desktop Computers",
            "Tablets", "Computer Accessories", "Gaming Accessories", "Gaming Consoles",
            "Televisions", "Audio & Speakers", "Headphones & Earphones",
            "Cameras & Photography", "Drones", "Smart Home Devices",
            "Networking Devices", "Storage Devices", "Printers & Scanners",
            "Electronic Gadgets", "Wearable Technology"
        ]
    },
    {
        "name": "Home & Living",
        "description": "Artisan home decor, handcrafted furnishings, living room, and lighting.",
        "subcategories": [
            "Home Decor", "Home Furnishing", "Home Furniture", "Living Room Furniture",
            "Bedroom Furniture", "Office Furniture", "Kitchen & Dining",
            "Kitchen Appliances", "Home Appliances", "Bathroom Accessories",
            "Home Storage & Organization", "Home Improvement", "Home Essentials",
            "Home Lighting", "Smart Home & Automation"
        ]
    },
    {
        "name": "Lifestyle & Personal Care",
        "description": "Skincare, makeup, grooming, luxury fragrances, and holistic wellness.",
        "subcategories": [
            "Beauty & Makeup", "Skincare", "Haircare", "Personal Care",
            "Men's Grooming", "Women's Grooming", "Perfumes & Fragrances",
            "Bath & Body", "Beauty Tools", "Health & Wellness"
        ]
    },
    {
        "name": "Sports & Fitness",
        "description": "Gym equipment, outdoor sporting gear, yoga essentials, and active nutrition.",
        "subcategories": [
            "Sports Equipment", "Gym & Fitness", "Yoga & Meditation",
            "Outdoor Sports", "Indoor Games", "Cycling", "Running Accessories",
            "Camping & Hiking", "Swimming Accessories", "Sports Nutrition"
        ]
    },
    {
        "name": "Baby, Kids & Toys",
        "description": "Baby care, feeding gear, educational toys, games, and kids furniture.",
        "subcategories": [
            "Baby Products", "Baby Care", "Baby Feeding", "Baby Gear",
            "Kids Toys", "Educational Toys", "Board Games & Puzzles",
            "Kids School Supplies", "Kids Furniture", "Kids Room Decor"
        ]
    },
    {
        "name": "Kitchen, Grocery & Food",
        "description": "Organic staples, gourmet food, tea, artisanal coffee, and kitchen tools.",
        "subcategories": [
            "Grocery", "Organic Products", "Packaged Food", "Snacks & Beverages",
            "Dry Fruits & Nuts", "Tea & Coffee", "Chocolates & Sweets",
            "Cooking Essentials", "Kitchen Tools", "Food & Gourmet Products"
        ]
    },
    {
        "name": "Bags & Travel",
        "description": "Luggage, suitcases, laptop backpacks, gym bags, and travel essentials.",
        "subcategories": [
            "Travel Bags", "Suitcases & Luggage", "Laptop Bags", "School Bags",
            "Office Bags", "Handbags & Purses", "Gym Bags", "Travel Essentials"
        ]
    },
    {
        "name": "Automotive",
        "description": "Car and bike accessories, EV accessories, auto electronics, and car care.",
        "subcategories": [
            "Car Accessories", "Bike Accessories", "Car Care Products",
            "Automotive Electronics", "Automotive Parts", "Two-Wheeler Accessories",
            "EV Accessories", "Automobile Lifestyle Products"
        ]
    },
    {
        "name": "Books, Education & Stationery",
        "description": "Books, e-books, office supplies, art & craft supplies, and instruments.",
        "subcategories": [
            "Books", "E-Books", "Educational Products", "Office Supplies",
            "Stationery", "Art & Craft Supplies", "Musical Instruments"
        ]
    },
    {
        "name": "Garden & Outdoor Living",
        "description": "Plants, gardening tools, outdoor lighting, and patio furniture.",
        "subcategories": [
            "Plants & Gardening", "Garden Accessories", "Outdoor Furniture",
            "Outdoor Lighting", "Gardening Tools", "Outdoor Living"
        ]
    },
    {
        "name": "Pets",
        "description": "Pet food, accessories, toys, and supplies for dogs, cats, and aquariums.",
        "subcategories": [
            "Pet Supplies", "Dog Products", "Cat Products", "Pet Food",
            "Pet Accessories", "Aquarium & Fish Supplies"
        ]
    },
    {
        "name": "Gifts & Special Collections",
        "description": "Curated gift hampers, handmade items, wedding gifts, and festive collections.",
        "subcategories": [
            "Gifts & Hampers", "Personalized Gifts", "Wedding Gifts",
            "Corporate Gifts", "Handmade Products", "Collectibles & Antiques",
            "Festival & Celebration Products", "Religious & Spiritual Products"
        ]
    },
    {
        "name": "Tools & Industrial",
        "description": "Hardware, tools, electrical, plumbing, construction, and safety supplies.",
        "subcategories": [
            "Hardware & Tools", "Industrial Supplies", "Electrical Supplies",
            "Plumbing Supplies", "Construction Materials", "Safety Equipment",
            "Machinery & Equipment"
        ]
    },
    {
        "name": "Additional Shopping Categories",
        "description": "Eco-friendly, sustainable, handcrafted, trending, and bestseller finds.",
        "subcategories": [
            "Premium & Luxury Products", "Eco-Friendly Products", "Sustainable Products",
            "Handmade & Artisan Products", "Refurbished Products", "Second-Hand Products",
            "Seasonal Collections", "Trending Products", "New Arrivals", "Best Sellers"
        ]
    }
]


class Command(BaseCommand):
    help = 'Seeds all 18 parent verticals and 172 subcategories (190 total) cleanly into database'

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding Master Taxonomy (18 Verticals + 172 Subcategories)..."))

        # Base sort order for master verticals starts at 10, preserving top 5 ceramics
        parent_sort_start = 10
        created_parents = 0
        created_children = 0

        with transaction.atomic():
            for v_idx, vertical in enumerate(MASTER_VERTICALS, start=1):
                parent_name = vertical["name"]
                parent_desc = vertical["description"]
                parent_slug = slugify(parent_name)
                parent_sort = parent_sort_start + (v_idx * 5)

                # Ensure slug uniqueness
                base_slug = parent_slug
                counter = 1
                while Category.objects.filter(slug=parent_slug).exclude(name=parent_name).exists():
                    parent_slug = f"{base_slug}-{counter}"
                    counter += 1

                parent_cat, p_created = Category.objects.get_or_create(
                    name=parent_name,
                    defaults={
                        'slug': parent_slug,
                        'description': parent_desc,
                        'is_active': True,
                        'sort_order': parent_sort,
                        'parent': None
                    }
                )

                if p_created:
                    created_parents += 1
                    self.stdout.write(self.style.SUCCESS(f"  [+] Created Parent: {parent_name} (/{parent_slug}/)"))
                else:
                    self.stdout.write(f"  [*] Parent Exists: {parent_name}")

                # Now create subcategories
                for s_idx, sub_name in enumerate(vertical["subcategories"], start=1):
                    sub_slug = slugify(sub_name)

                    # Ensure slug uniqueness (if subcategory slug conflicts, prefix with parent slug)
                    base_sub_slug = sub_slug
                    counter = 1
                    while Category.objects.filter(slug=sub_slug).exclude(name=sub_name, parent=parent_cat).exists():
                        sub_slug = f"{slugify(parent_name)[:15]}-{base_sub_slug}"
                        if Category.objects.filter(slug=sub_slug).exclude(name=sub_name, parent=parent_cat).exists():
                            sub_slug = f"{base_sub_slug}-{counter}"
                            counter += 1

                    sub_cat, s_created = Category.objects.get_or_create(
                        name=sub_name,
                        parent=parent_cat,
                        defaults={
                            'slug': sub_slug,
                            'description': f"{sub_name} under {parent_name}",
                            'is_active': True,
                            'sort_order': s_idx
                        }
                    )

                    if s_created:
                        created_children += 1

        total_in_db = Category.objects.count()
        parents_in_db = Category.objects.filter(parent__isnull=True).count()
        children_in_db = Category.objects.filter(parent__isnull=False).count()

        self.stdout.write(self.style.SUCCESS(
            f"\nTaxonomy Seed Complete! "
            f"Created {created_parents} new parents, {created_children} new subcategories.\n"
            f"Total Categories in DB: {total_in_db} ({parents_in_db} Parents, {children_in_db} Subcategories)"
        ))
