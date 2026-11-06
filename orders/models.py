from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid
from catalog.models import ProductVariant


class Order(models.Model):
    """
    Customer order with frozen address and financial snapshots, order tracking,
    and extensible logistics/payment metadata.
    """
    PAYMENT_METHOD_CHOICES = (
        ('cod', 'Cash on Delivery (COD)'),
        ('razorpay', 'Razorpay (UPI / Card / NetBanking)'),
    )

    PAYMENT_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )

    ORDER_STATUS_CHOICES = (
        ('pending', 'Pending Approval'),
        ('confirmed', 'Confirmed'),
        ('packed', 'Packed'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
        ('returned', 'Returned'),
    )

    order_number = models.CharField(max_length=50, unique=True, db_index=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    
    # Address snapshot stored at time of purchase
    shipping_address_snapshot = models.JSONField(help_text="Snapshot of the delivery address at time of order")
    
    # Financial breakdown
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_charge = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Payment status
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, default='cod')
    payment_status = models.CharField(max_length=50, choices=PAYMENT_STATUS_CHOICES, default='pending', db_index=True)
    
    # Fulfillment status
    order_status = models.CharField(max_length=50, choices=ORDER_STATUS_CHOICES, default='pending', db_index=True)
    
    # Future-ready logistics fields
    shipping_partner = models.CharField(max_length=100, blank=True, help_text="e.g. BlueDart, Delhivery, DTDC")
    tracking_number = models.CharField(max_length=100, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True, help_text="Customer or internal notes")
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_number']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['order_status']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Order #{self.order_number} ({self.get_order_status_display()}) - ₹{self.total}"

    @classmethod
    def generate_order_number(cls):
        """Generates a human-friendly unique order reference e.g. AS-20261104-ABCD."""
        date_str = timezone.now().strftime('%Y%m%d')
        random_suffix = uuid.uuid4().hex[:6].upper()
        return f"AS-{date_str}-{random_suffix}"

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = self.generate_order_number()
        super().save(*args, **kwargs)

    @property
    def item_count(self):
        return sum(item.quantity for item in self.items.all())


class OrderItem(models.Model):
    """
    Individual item snapshot in an order preserving historical pricing and naming.
    """
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='order_items'
    )
    product_name_snapshot = models.CharField(max_length=255)
    color = models.CharField(max_length=60, blank=True)
    size = models.CharField(max_length=60, blank=True)
    price_snapshot = models.DecimalField(max_digits=10, decimal_places=2, help_text="Unit price at purchase time")
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'

    def __str__(self):
        return f"{self.quantity}x {self.product_name_snapshot} in Order #{self.order.order_number}"

    @property
    def total_price(self):
        return self.price_snapshot * self.quantity


class Payment(models.Model):
    """
    Payment transaction record for an order.
    Structured and ready for Razorpay webhooks and responses.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('success', 'Success'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    )

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='payments')
    method = models.CharField(max_length=50, help_text="e.g. cod, razorpay_card, razorpay_upi")
    transaction_id = models.CharField(max_length=100, blank=True, db_index=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending', db_index=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    gateway_response = models.JSONField(blank=True, null=True, help_text="Raw payload from payment gateway")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment for #{self.order.order_number} ({self.status}) - ₹{self.amount}"
