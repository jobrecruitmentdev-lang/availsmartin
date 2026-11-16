import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'availsmart.settings')
django.setup()

from catalog.models import Product

imgs = {}
for p in Product.objects.all().order_by('id'):
    for c in p.colors.all():
        for i in c.images.all():
            img_path = str(i.image)
            imgs.setdefault(img_path, []).append((p.id, p.slug, p.name))

print(f"Total Products: {Product.objects.count()}")
print(f"Total Distinct Image Files: {len(imgs)}")
print("=" * 80)
for path, prods in imgs.items():
    print(f"Image: {path}")
    for pid, slug, name in prods:
        print(f"   -> [{pid}] {slug} ({name})")
    print("-" * 40)
