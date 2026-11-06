from django.contrib import admin
from .models import (
    Category, Brand, Product, ProductColor, ProductImage,
    ProductVariant, ProductSpecification, Review, Banner
)


class ProductSpecificationInline(admin.TabularInline):
    model = ProductSpecification
    extra = 1


class ProductColorInline(admin.TabularInline):
    model = ProductColor
    extra = 1


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent', 'slug', 'sort_order', 'is_active')
    list_filter = ('is_active', 'parent')
    search_fields = ('name', 'description')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'brand', 'base_price', 'discount_price', 'is_featured', 'is_active')
    list_filter = ('is_active', 'is_featured', 'category', 'brand')
    search_fields = ('name', 'sku', 'tags')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [ProductColorInline, ProductVariantInline, ProductSpecificationInline]


@admin.register(ProductColor)
class ProductColorAdmin(admin.ModelAdmin):
    list_display = ('product', 'color_name', 'color_hex', 'sort_order', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('product__name', 'color_name')


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ('product_color', 'is_primary', 'sort_order', 'created_at')
    list_filter = ('is_primary',)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('product', 'product_color', 'size', 'sku', 'price', 'stock_quantity', 'is_active')
    list_filter = ('is_active', 'size')
    search_fields = ('product__name', 'sku')


@admin.register(ProductSpecification)
class ProductSpecificationAdmin(admin.ModelAdmin):
    list_display = ('product', 'key', 'value', 'sort_order')
    search_fields = ('product__name', 'key', 'value')


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('product', 'user', 'rating', 'is_approved', 'created_at')
    list_filter = ('is_approved', 'rating')
    search_fields = ('product__name', 'user__name', 'user__email', 'comment')
    actions = ['approve_reviews']

    @admin.action(description="Approve selected reviews")
    def approve_reviews(self, request, queryset):
        for review in queryset:
            review.is_approved = True
            review.save()


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    list_display = ('title', 'link', 'sort_order', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('title', 'subtitle', 'link')
