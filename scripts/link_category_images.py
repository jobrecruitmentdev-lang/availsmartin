import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'availsmart.settings')
import django
django.setup()

from catalog.models import Category, Product

mapping = {
    'pure-attars': 'shanaya-luxury-concentrated-attar-12ml',
    'edp-sprays': 'lattafa-khamrah-eau-de-parfum-100ml',
    'discovery-sets': 'availsmart-10-fragrance-discovery-box',
    'rare-cambodian-oudh': 'dehn-al-oudh-cambodi-rare-vintage-oil-3ml',
    'bakhoor-incense': 'royal-bakhoor-incense-burner-gift-set',
    'gift-combos': 'pack-of-2-luxury-attar-duo-shanaya-white-oudh',
}

for cat_slug, prod_slug in mapping.items():
    try:
        cat = Category.objects.get(slug=cat_slug)
        prod = Product.objects.get(slug=prod_slug)
        if prod.primary_image and prod.primary_image.image:
            cat.image = prod.primary_image.image.name
            cat.save()
            print(f"Updated category {cat.name} ({cat.slug}) image to {cat.image}")
    except Exception as e:
        print(f"Error for {cat_slug}: {e}")
