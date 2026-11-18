import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'availsmart.settings')

import django
django.setup()

from django.template.loader import get_template

template_dir = os.path.join(BASE_DIR, 'templates')
errors = []
success_count = 0

for root, _, files in os.walk(template_dir):
    for f in files:
        if f.endswith('.html'):
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, template_dir).replace('\\', '/')
            try:
                get_template(rel_path)
                success_count += 1
            except Exception as e:
                errors.append((rel_path, str(e)))

print(f"Successfully compiled {success_count} templates.")
if errors:
    print(f"FAILED {len(errors)} templates:")
    for path, err in errors:
        print(f"  - {path}: {err}")
else:
    print("ALL TEMPLATES COMPILED CLEANLY WITH ZERO ERRORS!")
