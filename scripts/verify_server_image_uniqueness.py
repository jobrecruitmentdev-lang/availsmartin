import os
import hashlib
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'availsmart.settings')
django.setup()

from catalog.models import Product

prods = Product.objects.all().order_by('id')
hashes = {}

for p in prods:
    primary_img = None
    for c in p.colors.all():
        for img in c.images.all():
            if img.is_primary or primary_img is None:
                primary_img = img.image.name
                break
        if primary_img:
            break
    
    if primary_img:
        full_path = os.path.join('/home/u390470426/availsmart/media', primary_img)
        if os.path.exists(full_path):
            with open(full_path, 'rb') as f:
                h = hashlib.md5(f.read()).hexdigest()
            hashes.setdefault(h, []).append((p.id, p.slug, primary_img))
        else:
            print(f"File NOT FOUND: {full_path}")
    else:
        print(f"Product {p.id} ({p.slug}) has NO images!")

print(f"\nTotal Products: {prods.count()}")
print(f"Distinct Image Content Hashes: {len(hashes)}")
print("=" * 80)
for h, plist in hashes.items():
    if len(plist) > 1:
        print(f"🚨 DUPLICATE CONTENT DETECTED! (Hash: {h[:10]})")
        for pid, slug, fn in plist:
            print(f"   - [ID {pid}] {slug} -> {fn}")
    else:
        pid, slug, fn = plist[0]
        print(f"✅ Unique: [ID {pid}] {slug} -> {fn}")
