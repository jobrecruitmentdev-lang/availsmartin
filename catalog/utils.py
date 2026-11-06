import os
from io import BytesIO
from PIL import Image
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile

ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
MAX_IMAGE_SIZE_MB = 5


def validate_image_file(image):
    """
    Validates uploaded image file extension and size.
    Also verifies it is a valid image via Pillow.
    """
    if not image:
        return
    
    # Check file size
    file_size_mb = image.size / (1024 * 1024)
    if file_size_mb > MAX_IMAGE_SIZE_MB:
        raise ValidationError(f"Image file size exceeds {MAX_IMAGE_SIZE_MB}MB limit. Current size is {file_size_mb:.2f}MB.")
    
    # Check file extension
    ext = os.path.splitext(image.name)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(f"Unsupported image extension '{ext}'. Allowed: {', '.join(ALLOWED_IMAGE_EXTENSIONS)}.")
    
    # Verify image integrity using Pillow
    try:
        image.seek(0)
        img = Image.open(image)
        img.verify()
        image.seek(0)
    except Exception as e:
        raise ValidationError(f"Invalid or corrupted image file: {e}")


def generate_thumbnail(image_field, target_size=(400, 400), quality=85):
    """
    Generates a high-quality WebP thumbnail from an ImageField using Pillow,
    retaining aspect ratio, and returns a ContentFile ready to save.
    """
    if not image_field:
        return None

    try:
        image_field.seek(0)
        with Image.open(image_field) as img:
            # Convert RGBA / P mode images to RGB if needed
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create a white background for transparent images
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if 'A' in img.getbands() else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            img.thumbnail(target_size, Image.Resampling.LANCZOS)
            
            thumb_io = BytesIO()
            img.save(thumb_io, format='WEBP', quality=quality, optimize=True)
            thumb_io.seek(0)

            base_name = os.path.splitext(os.path.basename(image_field.name))[0]
            thumb_filename = f"{base_name}_thumb.webp"
            
            return ContentFile(thumb_io.read(), name=thumb_filename)
    except Exception as err:
        print(f"Error generating thumbnail for {image_field.name}: {err}")
        return None
