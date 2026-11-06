from django.contrib import admin
from .models import Cart, CartItem, Wishlist, Coupon


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'session_key', 'total_items', 'created_at', 'updated_at')
    search_fields = ('user__email', 'session_key')
    inlines = [CartItemInline]


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ('user', 'product', 'created_at')
    search_fields = ('user__name', 'user__email', 'product__name')


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_type', 'value', 'min_order', 'expiry', 'used_count', 'usage_limit', 'is_active')
    list_filter = ('discount_type', 'is_active')
    search_fields = ('code',)
