import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone

from .models import Cart, CartItem, Wishlist, Coupon
from catalog.models import Product, ProductVariant


def _get_cart(request):
    """
    Returns the shopping cart for authenticated user or guest session.
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart
    
    if not request.session.session_key:
        request.session.create()
    session_key = request.session.session_key
    cart, _ = Cart.objects.get_or_create(session_key=session_key)
    return cart


def _calculate_cart_totals(cart, coupon=None):
    """
    Calculates subtotal, coupon discount, shipping charge, and final total.
    """
    subtotal = Decimal('0.00')
    for item in cart.items.select_related('variant', 'variant__product').all():
        subtotal += item.total_price

    discount = Decimal('0.00')
    if coupon and coupon.is_valid:
        discount = coupon.calculate_discount(subtotal)

    # Free shipping on orders ₹999 or more
    shipping_charge = Decimal('0.00') if subtotal >= Decimal('999.00') or subtotal == Decimal('0.00') else Decimal('99.00')
    total = max(Decimal('0.00'), subtotal - discount + shipping_charge)

    return {
        'subtotal': subtotal,
        'discount': discount,
        'shipping_charge': shipping_charge,
        'total': total,
        'free_shipping_needed': max(Decimal('0.00'), Decimal('999.00') - subtotal) if subtotal < Decimal('999.00') else Decimal('0.00'),
    }


def cart_detail_view(request):
    """
    Shopping cart page view with real-time item quantities, coupon discounts,
    free shipping progress, and price breakdown.
    """
    cart = _get_cart(request)
    coupon = None
    coupon_id = request.session.get('coupon_id')
    if coupon_id:
        coupon = Coupon.objects.filter(id=coupon_id, is_active=True).first()
        if coupon and not coupon.is_valid:
            coupon = None
            request.session.pop('coupon_id', None)

    totals = _calculate_cart_totals(cart, coupon)

    context = {
        'cart': cart,
        'coupon': coupon,
        **totals,
    }
    return render(request, 'cart/cart.html', context)


@require_POST
def add_to_cart_view(request, variant_id=None):
    """
    Adds a product variant to the cart.
    Rule: Guests can browse; login required to add to cart or checkout.
    """
    next_url = request.META.get('HTTP_REFERER', '/')

    if not request.user.is_authenticated:
        login_url = f"{reverse('accounts:login')}?next={next_url}"
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({
                'status': 'unauthenticated',
                'message': 'Please sign in to add items to your cart.',
                'redirect_url': login_url
            }, status=401)
        messages.warning(request, "Please log in to add items to your cart.")
        return redirect(login_url)

    # Resolve variant
    variant = None
    if variant_id:
        variant = get_object_or_404(ProductVariant, id=variant_id, is_active=True)
    else:
        product_id = request.POST.get('product_id')
        if product_id:
            product = get_object_or_404(Product, id=product_id, is_active=True)
            variant = product.variants.filter(is_active=True, stock_quantity__gt=0).first()
            if not variant:
                variant = product.variants.filter(is_active=True).first()

    if not variant:
        return JsonResponse({'status': 'error', 'message': 'Product variant not found.'}, status=404)

    # Quantity
    try:
        quantity = int(request.POST.get('quantity', 1))
        if quantity < 1:
            quantity = 1
    except (ValueError, TypeError):
        quantity = 1

    if variant.stock_quantity < quantity:
        return JsonResponse({
            'status': 'error',
            'message': f"Only {variant.stock_quantity} units available in stock."
        }, status=400)

    cart = _get_cart(request)
    cart_item, created = CartItem.objects.get_or_create(cart=cart, variant=variant)

    if not created:
        if cart_item.quantity + quantity > variant.stock_quantity:
            cart_item.quantity = variant.stock_quantity
            cart_item.save()
            return JsonResponse({
                'status': 'warning',
                'message': f"Maximum available stock ({variant.stock_quantity}) reached in your cart.",
                'cart_count': cart.total_items
            })
        cart_item.quantity += quantity
        cart_item.save()
    else:
        cart_item.quantity = quantity
        cart_item.save()

    return JsonResponse({
        'status': 'success',
        'message': f"Added '{variant.product.name} ({variant.size or variant.product_color.color_name})' to cart!",
        'cart_count': cart.total_items,
        'item_title': variant.product.name,
        'variant_label': f"{variant.product_color.color_name} / {variant.size}" if variant.size else variant.product_color.color_name,
        'price': str(variant.effective_price),
    })


@require_POST
def update_quantity_view(request, item_id):
    """
    Updates the quantity of an item in the cart. Supports increment, decrement,
    or setting an explicit quantity value.
    """
    cart = _get_cart(request)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)

    action = request.POST.get('action')
    try:
        explicit_qty = int(request.POST.get('quantity', 0))
    except (ValueError, TypeError):
        explicit_qty = 0

    if action == 'increment':
        if item.quantity + 1 > item.variant.stock_quantity:
            return JsonResponse({
                'status': 'error',
                'message': f"Only {item.variant.stock_quantity} units available in stock."
            }, status=400)
        item.quantity += 1
        item.save()
    elif action == 'decrement':
        if item.quantity > 1:
            item.quantity -= 1
            item.save()
        else:
            item.delete()
            item = None
    elif explicit_qty > 0:
        if explicit_qty > item.variant.stock_quantity:
            return JsonResponse({
                'status': 'error',
                'message': f"Only {item.variant.stock_quantity} units available in stock."
            }, status=400)
        item.quantity = explicit_qty
        item.save()
    elif explicit_qty <= 0 and action == 'set':
        item.delete()
        item = None

    coupon = None
    coupon_id = request.session.get('coupon_id')
    if coupon_id:
        coupon = Coupon.objects.filter(id=coupon_id, is_active=True).first()

    totals = _calculate_cart_totals(cart, coupon)

    return JsonResponse({
        'status': 'success',
        'quantity': item.quantity if item else 0,
        'item_total': str(item.total_price) if item else '0.00',
        'subtotal': str(totals['subtotal']),
        'discount': str(totals['discount']),
        'shipping_charge': str(totals['shipping_charge']),
        'total': str(totals['total']),
        'cart_count': cart.total_items,
        'is_empty': cart.is_empty,
    })


@require_POST
def remove_cart_item_view(request, item_id):
    """
    Removes an item completely from the shopping cart.
    """
    cart = _get_cart(request)
    item = get_object_or_404(CartItem, id=item_id, cart=cart)
    product_name = item.variant.product.name
    item.delete()

    coupon = None
    coupon_id = request.session.get('coupon_id')
    if coupon_id:
        coupon = Coupon.objects.filter(id=coupon_id, is_active=True).first()

    totals = _calculate_cart_totals(cart, coupon)

    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'success',
            'message': f"Removed '{product_name}' from cart.",
            'subtotal': str(totals['subtotal']),
            'discount': str(totals['discount']),
            'shipping_charge': str(totals['shipping_charge']),
            'total': str(totals['total']),
            'cart_count': cart.total_items,
            'is_empty': cart.is_empty,
        })

    messages.info(request, f"Removed '{product_name}' from your cart.")
    return redirect('cart:index')


@require_POST
def apply_coupon_view(request):
    """
    Validates and applies a coupon code to the active cart session.
    """
    code = request.POST.get('code', '').strip().upper()
    if not code:
        return JsonResponse({'status': 'error', 'message': 'Please enter a coupon code.'}, status=400)

    cart = _get_cart(request)
    if cart.is_empty:
        return JsonResponse({'status': 'error', 'message': 'Your cart is empty.'}, status=400)

    coupon = Coupon.objects.filter(code=code, is_active=True).first()
    if not coupon:
        return JsonResponse({'status': 'error', 'message': 'Invalid coupon code.'}, status=404)

    if not coupon.is_valid:
        return JsonResponse({'status': 'error', 'message': 'This coupon has expired or reached its usage limit.'}, status=400)

    if cart.subtotal < coupon.min_order:
        return JsonResponse({
            'status': 'error',
            'message': f"Coupon requires a minimum order value of ₹{coupon.min_order}."
        }, status=400)

    request.session['coupon_id'] = coupon.id
    totals = _calculate_cart_totals(cart, coupon)

    return JsonResponse({
        'status': 'success',
        'message': f"Coupon '{coupon.code}' applied! You saved ₹{totals['discount']}.",
        'coupon_code': coupon.code,
        'discount': str(totals['discount']),
        'total': str(totals['total']),
    })


@require_POST
def remove_coupon_view(request):
    """
    Removes applied coupon from the current cart session.
    """
    request.session.pop('coupon_id', None)
    cart = _get_cart(request)
    totals = _calculate_cart_totals(cart)

    return JsonResponse({
        'status': 'success',
        'message': 'Coupon removed.',
        'discount': '0.00',
        'total': str(totals['total']),
    })


def cart_drawer_data_view(request):
    """
    Returns live JSON payload of the cart for the slide-in mini cart drawer.
    """
    cart = _get_cart(request)
    items_data = []

    for it in cart.items.select_related('variant', 'variant__product', 'variant__product_color').all():
        prim = it.variant.product.primary_image
        thumb_url = prim.thumbnail.url if prim and prim.thumbnail else (prim.image.url if prim else '')
        items_data.append({
            'id': it.id,
            'name': it.variant.product.name,
            'color': it.variant.product_color.color_name,
            'size': it.variant.size,
            'quantity': it.quantity,
            'unit_price': str(it.unit_price),
            'total_price': str(it.total_price),
            'thumbnail': thumb_url,
            'url': reverse('catalog:product_detail', kwargs={'slug': it.variant.product.slug}),
        })

    return JsonResponse({
        'cart_count': cart.total_items,
        'subtotal': str(cart.subtotal),
        'is_empty': cart.is_empty,
        'items': items_data,
    })


@require_POST
def toggle_wishlist_view(request, product_id):
    """
    Toggles product in user's saved wishlist.
    """
    next_url = request.META.get('HTTP_REFERER', '/')

    if not request.user.is_authenticated:
        login_url = f"{reverse('accounts:login')}?next={next_url}"
        if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json':
            return JsonResponse({
                'status': 'unauthenticated',
                'message': 'Please sign in to save items to your wishlist.',
                'redirect_url': login_url
            }, status=401)
        messages.warning(request, "Please log in to save items to your wishlist.")
        return redirect(login_url)

    product = get_object_or_404(Product, id=product_id, is_active=True)
    wishlist_item = Wishlist.objects.filter(user=request.user, product=product).first()

    if wishlist_item:
        wishlist_item.delete()
        action = 'removed'
        msg = f"Removed '{product.name}' from your wishlist."
    else:
        Wishlist.objects.create(user=request.user, product=product)
        action = 'added'
        msg = f"Added '{product.name}' to your wishlist!"

    count = Wishlist.objects.filter(user=request.user).count()

    return JsonResponse({
        'status': 'success',
        'action': action,
        'message': msg,
        'wishlist_count': count,
        'is_wishlisted': (action == 'added')
    })


def wishlist_view(request):
    """
    Customer's wishlist listing page.
    """
    if not request.user.is_authenticated:
        messages.info(request, "Please sign in to view your wishlist.")
        return redirect(f"{reverse('accounts:login')}?next=/cart/wishlist/")

    items = Wishlist.objects.filter(user=request.user).select_related('product', 'product__brand').prefetch_related('product__colors__images', 'product__variants')
    return render(request, 'cart/wishlist.html', {'wishlist_items': items})
