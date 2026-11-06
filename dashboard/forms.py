from django import forms
from catalog.models import Category, Brand, Product, Banner
from cart.models import Coupon

INPUT_CLASSES = "w-full px-4 py-2.5 bg-white border border-emerald-border rounded-xl text-textMain text-sm focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent transition"
TEXTAREA_CLASSES = "w-full px-4 py-2.5 bg-white border border-emerald-border rounded-xl text-textMain text-sm focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent transition resize-y"
SELECT_CLASSES = "w-full px-4 py-2.5 bg-white border border-emerald-border rounded-xl text-textMain text-sm focus:outline-none focus:ring-2 focus:ring-emerald focus:border-transparent transition"
CHECKBOX_CLASSES = "w-4 h-4 text-emerald rounded border-emerald-border focus:ring-emerald focus:ring-offset-0"


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'parent', 'image', 'description', 'sort_order', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. Footwear & Sneakers'}),
            'parent': forms.Select(attrs={'class': SELECT_CLASSES}),
            'description': forms.Textarea(attrs={'class': TEXTAREA_CLASSES, 'rows': 3, 'placeholder': 'Category summary...'}),
            'sort_order': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only allow top-level categories to be parents
        self.fields['parent'].queryset = Category.objects.filter(parent__isnull=True)
        self.fields['parent'].empty_label = "-- None (Make Top-Level Category) --"


class BrandForm(forms.ModelForm):
    class Meta:
        model = Brand
        fields = ['name', 'logo', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. Nike, Apple, Sony'}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
        }


class ProductBaseForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = [
            'name', 'category', 'brand', 'base_price', 'discount_price',
            'sku', 'weight', 'weight_unit', 'length', 'width', 'height',
            'material', 'tags', 'short_description', 'full_description',
            'is_featured', 'is_active', 'meta_title', 'meta_description'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. AeroGlide Ultra Running Shoes'}),
            'category': forms.Select(attrs={'class': SELECT_CLASSES}),
            'brand': forms.Select(attrs={'class': SELECT_CLASSES}),
            'base_price': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'placeholder': '0.00', 'step': '0.01'}),
            'discount_price': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'placeholder': '0.00', 'step': '0.01'}),
            'sku': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. PROD-SKU-001'}),
            'weight': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'placeholder': '0.00', 'step': '0.01'}),
            'weight_unit': forms.Select(attrs={'class': SELECT_CLASSES}),
            'length': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Length (cm)', 'step': '0.1'}),
            'width': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Width (cm)', 'step': '0.1'}),
            'height': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Height (cm)', 'step': '0.1'}),
            'material': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. 100% Organic Cotton'}),
            'tags': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. trending, casual, summer (comma separated)'}),
            'short_description': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'Brief teaser description for card preview...'}),
            'full_description': forms.Textarea(attrs={'class': TEXTAREA_CLASSES, 'rows': 5, 'placeholder': 'Comprehensive product specifications, features, and care instructions...'}),
            'is_featured': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
            'meta_title': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'SEO Meta Title (recommended 50-60 chars)'}),
            'meta_description': forms.Textarea(attrs={'class': TEXTAREA_CLASSES, 'rows': 2, 'placeholder': 'SEO Meta Description (recommended 150-160 chars)'}),
        }


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = ['code', 'discount_type', 'value', 'min_order', 'expiry', 'usage_limit', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. SUMMER25'}),
            'discount_type': forms.Select(attrs={'class': SELECT_CLASSES}),
            'value': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. 20 for 20% or 500 for ₹500', 'step': '0.01'}),
            'min_order': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'placeholder': '0.00', 'step': '0.01'}),
            'expiry': forms.DateTimeInput(attrs={'class': INPUT_CLASSES, 'type': 'datetime-local'}),
            'usage_limit': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'min': 1}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
        }


class BannerForm(forms.ModelForm):
    class Meta:
        model = Banner
        fields = [
            'title', 'subtitle', 'image', 'link', 
            'badge_text', 'product_tag', 'price_text', 'button_text',
            'sort_order', 'is_active'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. Thoughtfully Formed Objects for Living.'}),
            'subtitle': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. Discover hand-poured ceramics, organic home textiles...'}),
            'link': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': '/catalog/'}),
            'badge_text': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. 01 ARTISAN SERIES or FESTIVE DROP'}),
            'product_tag': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. Hand-Poured Ceramic Mug'}),
            'price_text': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. From ₹1,299 or 30% OFF'}),
            'button_text': forms.TextInput(attrs={'class': INPUT_CLASSES, 'placeholder': 'e.g. Explore Collection'}),
            'sort_order': forms.NumberInput(attrs={'class': INPUT_CLASSES, 'min': 0}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECKBOX_CLASSES}),
        }
