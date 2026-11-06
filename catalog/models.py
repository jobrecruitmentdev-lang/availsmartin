from django.db import models
from django.conf import settings
from django.utils.text import slugify
from django.db.models import Avg, Count
from decimal import Decimal
from .utils import validate_image_file, generate_thumbnail


class Category(models.Model):
    """
    Category model with self-referential hierarchical parent for sub-categories.
    """
    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=150, unique=True, db_index=True)
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    image = models.ImageField(upload_to='categories/', null=True, blank=True, validators=[validate_image_file])
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['sort_order', 'name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['parent', 'is_active']),
            models.Index(fields=['sort_order']),
        ]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    @property
    def is_parent(self):
        return self.parent is None


class Brand(models.Model):
    """
    Product brand or manufacturer.
    """
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=150, unique=True, db_index=True)
    logo = models.ImageField(upload_to='brands/', null=True, blank=True, validators=[validate_image_file])
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Brand'
        verbose_name_plural = 'Brands'
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(models.Model):
    """
    Main Product catalog model supporting multiple colors, size variants,
    specifications, and comprehensive pricing attributes.
    """
    WEIGHT_UNIT_CHOICES = (
        ('kg', 'kg'),
        ('g', 'g'),
        ('lb', 'lb'),
        ('oz', 'oz'),
    )

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='products', db_index=True)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True, related_name='products', db_index=True)
    short_description = models.CharField(max_length=500, blank=True)
    full_description = models.TextField(blank=True)
    
    # Pricing
    base_price = models.DecimalField(max_digits=10, decimal_places=2, db_index=True, help_text="Regular MSRP or base price")
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, db_index=True, help_text="Discounted selling price if on sale")
    discount_percent = models.PositiveIntegerField(default=0, help_text="Discount percentage (auto-calculated or manual)")
    
    # Inventory / Physical details
    sku = models.CharField(max_length=100, unique=True, db_index=True)
    weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    weight_unit = models.CharField(max_length=10, choices=WEIGHT_UNIT_CHOICES, default='kg')
    length = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="In centimeters")
    width = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="In centimeters")
    height = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="In centimeters")
    material = models.CharField(max_length=120, blank=True)
    tags = models.CharField(max_length=255, blank=True, help_text="Comma-separated search tags")
    
    # Status flags
    is_featured = models.BooleanField(default=False, db_index=True)
    is_active = models.BooleanField(default=True, db_index=True)
    
    # SEO
    meta_title = models.CharField(max_length=255, blank=True)
    meta_description = models.TextField(blank=True)
    
    # Aggregate rating
    rating_avg = models.DecimalField(max_digits=3, decimal_places=2, default=0.00)
    rating_count = models.PositiveIntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['slug']),
            models.Index(fields=['category', 'is_active']),
            models.Index(fields=['brand', 'is_active']),
            models.Index(fields=['base_price', 'discount_price']),
            models.Index(fields=['is_featured', 'is_active']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        
        # Calculate discount percentage if discount_price is lower than base_price
        if self.discount_price and self.base_price > 0 and self.discount_price < self.base_price:
            calc_percent = round(((self.base_price - self.discount_price) / self.base_price) * 100)
            self.discount_percent = calc_percent
        elif not self.discount_price or self.discount_price >= self.base_price:
            self.discount_percent = 0
            
        super().save(*args, **kwargs)

    @property
    def effective_price(self):
        """Returns the active selling price taking discount into account."""
        if self.discount_price and self.discount_price > 0 and self.discount_price < self.base_price:
            return self.discount_price
        return self.base_price

    @property
    def has_discount(self):
        return bool(self.discount_price and self.discount_price < self.base_price)

    @property
    def primary_image(self):
        """Returns primary product image across all colors, or the first available."""
        # Find primary in colors
        for color in self.colors.all():
            primary = color.images.filter(is_primary=True).first()
            if primary:
                return primary
            first_img = color.images.first()
            if first_img:
                return first_img
        return None

    @property
    def secondary_image(self):
        """Returns second image for hover effect on product cards."""
        images = []
        for color in self.colors.all():
            for img in color.images.all():
                images.append(img)
                if len(images) >= 2:
                    return images[1]
        return None

    @property
    def total_stock(self):
        """Calculates total available stock across all active variants."""
        return sum(variant.stock_quantity for variant in self.variants.filter(is_active=True))

    @property
    def is_in_stock(self):
        return self.total_stock > 0

    def update_rating_stats(self):
        """Recalculates average rating and review count from approved reviews."""
        approved_reviews = self.reviews.filter(is_approved=True)
        stats = approved_reviews.aggregate(avg=Avg('rating'), count=Count('id'))
        self.rating_avg = round(Decimal(stats['avg'] or 0.0), 2)
        self.rating_count = stats['count'] or 0
        self.save(update_fields=['rating_avg', 'rating_count'])


class ProductColor(models.Model):
    """
    Colors associated with a product. Each color has its own separate set of images.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='colors')
    color_name = models.CharField(max_length=60, help_text="e.g. Midnight Black, Emerald Green")
    color_hex = models.CharField(max_length=7, default='#047857', help_text="Hex color code e.g. #047857")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product Color'
        verbose_name_plural = 'Product Colors'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.product.name} - {self.color_name}"


class ProductImage(models.Model):
    """
    Images attached to a specific ProductColor.
    One color can have multiple images with primary selection and order.
    Auto-generates thumbnails via Pillow.
    """
    product_color = models.ForeignKey(ProductColor, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='products/', validators=[validate_image_file])
    thumbnail = models.ImageField(upload_to='products/thumbs/', blank=True, null=True)
    alt_text = models.CharField(max_length=255, blank=True)
    is_primary = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product Image'
        verbose_name_plural = 'Product Images'
        ordering = ['-is_primary', 'sort_order', 'id']

    def __str__(self):
        return f"Image for {self.product_color} (Primary={self.is_primary})"

    def save(self, *args, **kwargs):
        # If set as primary, unmark other images for this color
        if self.is_primary:
            ProductImage.objects.filter(product_color=self.product_color, is_primary=True).exclude(pk=self.pk).update(is_primary=False)
        
        # Auto generate thumbnail if new or missing
        if self.image and not self.thumbnail:
            thumb_file = generate_thumbnail(self.image)
            if thumb_file:
                self.thumbnail.save(thumb_file.name, thumb_file, save=False)

        super().save(*args, **kwargs)


class ProductVariant(models.Model):
    """
    Size/SKU variant under a product and specific color.
    Unique together on: product + product_color + size
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    product_color = models.ForeignKey(ProductColor, on_delete=models.CASCADE, related_name='variants')
    size = models.CharField(max_length=60, blank=True, default='', help_text="e.g. S, M, L, XL, 128GB, Free Size")
    sku = models.CharField(max_length=120, unique=True, db_index=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Optional price override for this variant")
    stock_quantity = models.PositiveIntegerField(default=0)
    weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, help_text="Optional weight override")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product Variant'
        verbose_name_plural = 'Product Variants'
        unique_together = ('product', 'product_color', 'size')
        ordering = ['product_color', 'size']

    def __str__(self):
        size_label = f" - Size: {self.size}" if self.size else ""
        return f"{self.product.name} ({self.product_color.color_name}{size_label}) [SKU: {self.sku}]"

    @property
    def effective_price(self):
        """Returns variant price override if set, else parent product effective price."""
        if self.price is not None and self.price > 0:
            return self.price
        return self.product.effective_price

    @property
    def is_in_stock(self):
        return self.stock_quantity > 0


class ProductSpecification(models.Model):
    """
    Key-value specification rows for a product (e.g. Material, Battery, Dimensions).
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='specifications')
    key = models.CharField(max_length=120)
    value = models.CharField(max_length=255)
    sort_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Product Specification'
        verbose_name_plural = 'Product Specifications'
        ordering = ['sort_order', 'id']

    def __str__(self):
        return f"{self.product.name} - {self.key}: {self.value}"


class Review(models.Model):
    """
    Customer ratings and reviews with admin approval workflow.
    """
    RATING_CHOICES = (
        (1, '1 Star - Very Poor'),
        (2, '2 Stars - Poor'),
        (3, '3 Stars - Average'),
        (4, '4 Stars - Good'),
        (5, '5 Stars - Excellent'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='reviews')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(choices=RATING_CHOICES, db_index=True)
    comment = models.TextField()
    is_approved = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
        ordering = ['-created_at']

    def __str__(self):
        return f"Review by {self.user.name} on {self.product.name} ({self.rating}★)"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        # Recalculate average rating for product
        self.product.update_rating_stats()


class Banner(models.Model):
    """
    Homepage and promotional banners.
    """
    title = models.CharField(max_length=150)
    subtitle = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to='banners/', validators=[validate_image_file])
    link = models.CharField(max_length=255, default='/catalog/', blank=True)
    badge_text = models.CharField(max_length=80, default='Artisan Series', blank=True, help_text="e.g. 01 ARTISAN SERIES or FESTIVE DROP")
    product_tag = models.CharField(max_length=150, default='Hand-Poured Ceramic Mug', blank=True, help_text="Product or collection spotlight")
    price_text = models.CharField(max_length=80, default='From Rs. 1,299', blank=True, help_text="e.g. From Rs. 1,299 or 30% OFF")
    button_text = models.CharField(max_length=80, default='Explore Collection', blank=True, help_text="Button CTA label")
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Banner'
        verbose_name_plural = 'Banners'
        ordering = ['sort_order', '-created_at']

    def __str__(self):
        return self.title
