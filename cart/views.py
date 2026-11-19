import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone

from .models import Cart, CartItem, Wishlist, Coupon
from catalog.models import Product, ProductVariant


def _get_cart(request):
    """
    Returns the shopping cart for authenticated user or guest session.
    Guarantees session persistence for guest shoppers.
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart
    
    if not request.session.session_key:
        request.session.create()

    # Guarantee session persistence so DualSessionMiddleware and browser retain the cookie
    request.session['has_cart'] = True
    request.session.modified = True

    session_key = request.session.session_key
    cart, _ = Cart.objects.get_or_create(session_key=session_key)
    return cart


def _calculate_cart_totals(cart, coupon=None, payment_method=None):
    """
    Calculates subtotal, coupon discount, shipping charge, UPI prepaid incentive, and final total.
    """
    subtotal = Decimal('0.00')
    for item in cart.items.select_related('variant', 'variant__product').all():
        subtotal += item.total_price

    discount = Decimal('0.00')
    if coupon and coupon.is_valid:
        discount = coupon.calculate_discount(subtotal)

    # Free express delivery on orders ₹499 or more
    shipping_charge = Decimal('0.00') if subtotal >= Decimal('499.00') or subtotal == Decimal('0.00') else Decimal('70.00')

    # Extra ₹50 Instant Discount on Prepaid UPI / Online Payment (Prepaid Conversion Incentive)
    upi_discount = Decimal('0.00')
    if payment_method in ['razorpay', 'upi'] and subtotal >= Decimal('299.00'):
        upi_discount = Decimal('50.00')

    total = max(Decimal('0.00'), subtotal - discount - upi_discount + shipping_charge)

    return {
        'subtotal': subtotal,
        'discount': discount,
        'upi_discount': upi_discount,
        'shipping_charge': shipping_charge,
        'total': total,
        'free_shipping_needed': max(Decimal('0.00'), Decimal('499.00') - subtotal) if subtotal < Decimal('499.00') else Decimal('0.00'),
    }


@ensure_csrf_cookie
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
    Supports both anonymous guest session carts and authenticated user carts seamlessly.
    """
    # Resolve variant
    variant = None
    if variant_id:
        variant = get_object_or_404(ProductVariant, id=variant_id, is_active=True)
    else:
        post_variant_id = request.POST.get('variant_id')
        if post_variant_id:
            try:
                variant = ProductVariant.objects.filter(id=int(post_variant_id), is_active=True).first()
            except (ValueError, TypeError):
                variant = None

        if not variant:
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
def add_bundle_to_cart_view(request):
    """
    Adds multiple fragrance products to the cart simultaneously (e.g. Pick Any 3 for ₹899 Trio Combo).
    Automatically applies combo coupon TRIO899 for instant bundle savings.
    Supports both anonymous guest session carts and authenticated user carts seamlessly.
    """
    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            product_ids = data.get('product_ids', [])
        else:
            product_ids = request.POST.getlist('product_ids') or request.POST.getlist('product_ids[]') or request.POST.get('product_ids', [])

        if isinstance(product_ids, str):
            product_ids = [int(p.strip()) for p in product_ids.split(',') if p.strip()]
        else:
            product_ids = [int(p) for p in product_ids if p]
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Invalid data: {str(e)}'}, status=400)

    if not product_ids:
        return JsonResponse({'status': 'error', 'message': 'No items selected for combo.'}, status=400)

    cart = _get_cart(request)
    added_names = []

    for pid in product_ids:
        try:
            prod = Product.objects.get(id=pid, is_active=True)
            variant = prod.variants.filter(is_active=True, stock_quantity__gt=0).first()
            if not variant:
                variant = prod.variants.filter(is_active=True).first()
            if variant:
                cart_item, created = CartItem.objects.get_or_create(cart=cart, variant=variant)
                if not created:
                    cart_item.quantity += 1
                else:
                    cart_item.quantity = 1
                cart_item.save()
                added_names.append(prod.name)
        except Product.DoesNotExist:
            continue

    # Apply Trio Combo Coupon if 3 or more items
    if len(product_ids) >= 3:
        trio_coupon = Coupon.objects.filter(code='TRIO899', is_active=True).first()
        if trio_coupon and trio_coupon.is_valid:
            request.session['coupon_id'] = trio_coupon.id

    return JsonResponse({
        'status': 'success',
        'message': f"Added {len(added_names)} fragrances to your bag at exclusive Trio Combo pricing (₹899)!",
        'cart_count': cart.total_items,
        'added_items': added_names,
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
    Seamlessly supports both authenticated customers and guest browser sessions.
    """
    product = get_object_or_404(Product, id=product_id, is_active=True)

    if request.user.is_authenticated:
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
    else:
        # Seamless Guest Session Wishlist (guarantees zero friction for browsing visitors)
        wishlist_ids = request.session.get('wishlist_ids', [])
        if product_id in wishlist_ids:
            wishlist_ids.remove(product_id)
            action = 'removed'
            msg = f"Removed '{product.name}' from your wishlist."
        else:
            wishlist_ids.append(product_id)
            action = 'added'
            msg = f"Added '{product.name}' to your wishlist!"
        request.session['wishlist_ids'] = wishlist_ids
        request.session.modified = True
        count = len(wishlist_ids)

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
    Renders saved items for both authenticated members and guest shopping sessions.
    """
    if request.user.is_authenticated:
        items = list(Wishlist.objects.filter(user=request.user).select_related('product', 'product__brand').prefetch_related('product__colors__images', 'product__variants'))
        wishlist_ids = set(item.product_id for item in items)
    else:
        guest_ids = request.session.get('wishlist_ids', [])
        products = Product.objects.filter(id__in=guest_ids, is_active=True).select_related('brand').prefetch_related('colors__images', 'variants')
        items = [{'product': p} for p in products]
        wishlist_ids = set(guest_ids)

    return render(request, 'cart/wishlist.html', {
        'wishlist_items': items,
        'wishlist_ids': wishlist_ids
    })
