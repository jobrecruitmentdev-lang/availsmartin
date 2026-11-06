from django.contrib import admin
from .models import Order, OrderItem, Payment


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('product_name_snapshot', 'color', 'size', 'price_snapshot', 'quantity', 'total_price')


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    readonly_fields = ('method', 'transaction_id', 'status', 'amount', 'created_at')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'user', 'total', 'payment_method', 'payment_status', 'order_status', 'created_at')
    list_filter = ('order_status', 'payment_status', 'payment_method', 'created_at')
    search_fields = ('order_number', 'user__name', 'user__email', 'tracking_number')
    readonly_fields = ('order_number', 'created_at', 'updated_at')
    inlines = [OrderItemInline, PaymentInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product_name_snapshot', 'color', 'size', 'price_snapshot', 'quantity')
    search_fields = ('order__order_number', 'product_name_snapshot')


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('order', 'method', 'transaction_id', 'status', 'amount', 'created_at')
    list_filter = ('status', 'method')
    search_fields = ('order__order_number', 'transaction_id')
