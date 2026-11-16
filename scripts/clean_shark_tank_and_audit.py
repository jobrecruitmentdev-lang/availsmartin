import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'availsmart.settings')
django.setup()

from catalog.models import Product

for p in Product.objects.all():
    changed = False
    if p.bundle_text and 'shark' in p.bundle_text.lower():
        print(f"Cleaning bundle_text on [ID {p.id}] {p.slug}: {p.bundle_text}")
        p.bundle_text = "Imperial Reserve Signature Edition"
        changed = True
    if 'shark' in p.name.lower():
        print(f"Cleaning name on [ID {p.id}] {p.slug}: {p.name}")
        p.name = p.name.replace("Shark Tank", "Imperial").replace("shark tank", "Imperial")
        changed = True
    if p.short_description and 'shark' in p.short_description.lower():
        p.short_description = p.short_description.replace("Shark Tank", "Imperial").replace("shark tank", "Imperial")
        changed = True
    if p.full_description and 'shark' in p.full_description.lower():
        p.full_description = p.full_description.replace("Shark Tank", "Imperial").replace("shark tank", "Imperial")
        changed = True
    if changed:
        p.save()
        print(f"Saved [ID {p.id}] {p.slug}")

print("Clean scan complete!")
