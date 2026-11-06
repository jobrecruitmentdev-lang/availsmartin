from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from catalog.models import Product, ProductVariant


class Cart(models.Model):
    """
    Shopping cart associated with an authenticated user or an anonymous session.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='cart'
    )
    session_key = models.CharField(max_length=40, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cart'
        verbose_name_plural = 'Carts'

    def __str__(self):
        if self.user:
            return f"Cart for {self.user.email}"
        return f"Guest Cart ({self.session_key})"

    @property
    def total_items(self):
        """Returns total item count in cart."""
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        """Calculates total gross amount before coupon discounts."""
        return sum(item.total_price for item in self.items.all())

    @property
    def is_empty(self):
        return not self.items.exists()


class CartItem(models.Model):
    """
    Item within a cart pointing to a specific product variant (color + size combination).
    """
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='cart_items')
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cart Item'
        verbose_name_plural = 'Cart Items'
        unique_together = ('cart', 'variant')

    def __str__(self):
        return f"{self.quantity}x {self.variant} in Cart #{self.cart_id}"

    @property
    def unit_price(self):
        return self.variant.effective_price

    @property
    def total_price(self):
        return self.unit_price * self.quantity


class Wishlist(models.Model):
    """
    Customer wishlist of saved products.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='wishlist_items'
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='wishlisted_by')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Wishlist Item'
        verbose_name_plural = 'Wishlist Items'
        unique_together = ('user', 'product')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.name} saved {self.product.name}"


class Coupon(models.Model):
    """
    Promotional discount coupons with type (percentage or flat amount),
    minimum order requirement, usage limit and expiry dates.
    """
    DISCOUNT_TYPE_CHOICES = (
        ('percent', 'Percentage (%)'),
        ('flat', 'Flat Amount (₹)'),
    )

    code = models.CharField(max_length=50, unique=True, db_index=True)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPE_CHOICES, default='percent')
    value = models.DecimalField(max_digits=10, decimal_places=2, help_text="Percentage value (e.g. 10 for 10%) or flat amount in INR")
    min_order = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text="Minimum order value needed to apply")
    expiry = models.DateTimeField()
    usage_limit = models.PositiveIntegerField(default=100)
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Coupon'
        verbose_name_plural = 'Coupons'
        ordering = ['-created_at']

    def __str__(self):
        unit = '%' if self.discount_type == 'percent' else '₹'
        return f"{self.code} ({self.value}{unit} off)"

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expiry

    @property
    def is_valid(self):
        return self.is_active and not self.is_expired and self.used_count < self.usage_limit

    def calculate_discount(self, order_subtotal):
        """
        Calculates discount amount in Decimal based on order subtotal.
        Returns 0 if order does not meet minimum order value.
        """
        if not self.is_valid or order_subtotal < self.min_order:
            return Decimal('0.00')

        if self.discount_type == 'percent':
            discount = (order_subtotal * (self.value / Decimal('100.00')))
            return round(min(discount, order_subtotal), 2)
        else:
            return round(min(self.value, order_subtotal), 2)
