import sys
import json
import secrets
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import ensure_csrf_cookie
from django.contrib import messages
from django.urls import reverse
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.http import JsonResponse

from .models import Order, OrderItem, Payment
from cart.models import Cart, CartItem, Coupon
from cart.views import _get_cart, _calculate_cart_totals
from accounts.models import Address, User
from accounts.views import merge_guest_cart
from accounts.otp_service import create_and_send_otp, verify_otp


@ensure_csrf_cookie
def checkout_view(request):
    """
    Seamless D2C Checkout page view supporting both authenticated customers
    and instant guest shoppers with 6-digit Email OTP confirmation.
    """
    cart = _get_cart(request)
    if not cart or cart.is_empty:
        messages.info(request, "Your shopping bag is empty. Please add items before checking out.")
        return redirect('cart:index')

    if request.user.is_authenticated:
        addresses = Address.objects.filter(user=request.user, is_active=True).order_by('-is_default', '-created_at')
    else:
        addresses = Address.objects.none()

    coupon = None
    coupon_id = request.session.get('coupon_id')
    if coupon_id:
        coupon = Coupon.objects.filter(id=coupon_id, is_active=True).first()
        if coupon and not coupon.is_valid:
            coupon = None
            request.session.pop('coupon_id', None)

    totals = _calculate_cart_totals(cart, coupon)
    upi_totals = _calculate_cart_totals(cart, coupon, payment_method='razorpay')

    context = {
        'cart': cart,
        'addresses': addresses,
        'coupon': coupon,
        **totals,
        'upi_total': upi_totals['total'],
        'upi_discount_amount': upi_totals['upi_discount'],
    }
    return render(request, 'orders/checkout.html', context)


@require_POST
def send_order_otp_view(request):
    """
    Sends a 6-digit confirmation code to the customer's email before finalizing the studio order.
    Supports authenticated users and guest checkouts seamlessly.
    """
    cart = _get_cart(request)
    if not cart or cart.is_empty:
        return JsonResponse({'status': 'error', 'message': 'Your shopping bag is empty.'}, status=400)

    if request.user.is_authenticated:
        email = request.user.email.strip().lower()
        user = request.user
    else:
        email = request.POST.get('email', '').strip().lower()
        if not email or '@' not in email:
            return JsonResponse({'status': 'error', 'message': 'Please enter a valid email address to receive your verification code.'}, status=400)
        user = None
        request.session['guest_checkout_email'] = email
        request.session.modified = True

    coupon = None
    coupon_id = request.session.get('coupon_id')
    if coupon_id:
        coupon = Coupon.objects.filter(id=coupon_id, is_active=True).first()
    totals = _calculate_cart_totals(cart, coupon)

    success, msg, _ = create_and_send_otp(
        email=email,
        purpose='order_confirmation',
        user=user,
        metadata={
            'total_amount': str(totals['total']),
            'item_count': f"{cart.total_items} items"
        },
        expiry_minutes=10
    )

    if success:
        return JsonResponse({
            'status': 'success',
            'message': f"A 6-digit confirmation code has been dispatched to {email}."
        })
    else:
        return JsonResponse({'status': 'error', 'message': msg}, status=429 if 'wait' in msg.lower() else 400)


@require_POST
def place_order_view(request):
    """
    Processes the checkout form, validates address and inventory,
    decrements stock, freezes order snapshot, creates Payment and OrderItems,
    and empties the cart.
    Supports authenticated customers and seamless guest checkout.
    """
    cart = _get_cart(request)
    if not cart or cart.is_empty:
        messages.error(request, "Your cart is empty.")
        return redirect('cart:index')

    # Resolve customer user & email
    if request.user.is_authenticated:
        customer_user = request.user
        customer_email = request.user.email.strip().lower()
    else:
        customer_email = request.POST.get('new_email', '').strip().lower() or request.session.get('guest_checkout_email', '')
        if not customer_email or '@' not in customer_email:
            messages.error(request, "Please provide a valid email address.")
            return redirect('orders:checkout')
        customer_name = request.POST.get('new_full_name', '').strip() or 'Valued Customer'
        customer_phone = request.POST.get('new_phone', '').strip()

        # Find or create customer account seamlessly
        customer_user = User.objects.filter(email=customer_email).first()
        if not customer_user:
            customer_user = User.objects.create_user(
                email=customer_email,
                name=customer_name,
                phone=customer_phone,
                password=secrets.token_urlsafe(16),
                is_active=True
            )
        elif not customer_user.is_active:
            customer_user.is_active = True
            customer_user.save(update_fields=['is_active'])

    # 0. Mandatory Security OTP Verification before order confirmation
    otp_code = request.POST.get('otp_code', '').strip()
    if not otp_code:
        messages.error(request, "Please enter the 6-digit confirmation code sent to your email to verify your order.")
        return redirect('orders:checkout')

    is_valid, otp_msg, _ = verify_otp(email=customer_email, otp_code=otp_code, purpose='order_confirmation')
    if not is_valid:
        messages.error(request, otp_msg)
        return redirect('orders:checkout')

    # 1. Resolve Delivery Address
    selected_address_id = request.POST.get('address_id')
    address_snapshot = None

    if selected_address_id and selected_address_id != 'new' and request.user.is_authenticated:
        address = get_object_or_404(Address, id=selected_address_id, user=request.user, is_active=True)
        address_snapshot = {
            'full_name': address.full_name,
            'phone': address.phone,
            'address_line1': address.address_line1,
            'address_line2': address.address_line2,
            'city': address.city,
            'state': address.state,
            'pincode': address.pincode,
            'country': address.country,
            'address_type': address.address_type,
        }
    else:
        # User submitted a new address directly in checkout
        full_name = request.POST.get('new_full_name', '').strip()
        phone = request.POST.get('new_phone', '').strip()
        address_line1 = request.POST.get('new_address_line1', '').strip()
        address_line2 = request.POST.get('new_address_line2', '').strip()
        city = request.POST.get('new_city', '').strip()
        state = request.POST.get('new_state', '').strip()
        pincode = request.POST.get('new_pincode', '').strip()
        country = request.POST.get('new_country', 'India').strip()
        address_type = request.POST.get('new_address_type', 'home')
        save_address = request.POST.get('save_address') in ['1', 'on', 'true']

        if not all([full_name, phone, address_line1, city, state, pincode]):
            messages.error(request, "Please fill in all mandatory delivery address fields.")
            return redirect('orders:checkout')

        address_snapshot = {
            'full_name': full_name,
            'phone': phone,
            'address_line1': address_line1,
            'address_line2': address_line2,
            'city': city,
            'state': state,
            'pincode': pincode,
            'country': country,
            'address_type': address_type,
        }

        if save_address and customer_user:
            has_existing = Address.objects.filter(user=customer_user, is_active=True).exists()
            Address.objects.create(
                user=customer_user,
                full_name=full_name,
                phone=phone,
                address_line1=address_line1,
                address_line2=address_line2,
                city=city,
                state=state,
                pincode=pincode,
                country=country,
                address_type=address_type,
                is_default=(not has_existing)
            )

    # 2. Check and Lock Inventory
    with transaction.atomic():
        # Re-fetch items with select_for_update
        cart_items = list(cart.items.select_related('variant', 'variant__product', 'variant__product_color').all())
        
        for item in cart_items:
            variant = item.variant
            if variant.stock_quantity < item.quantity:
                messages.error(
                    request,
                    f"Insufficient stock for '{variant.product.name} ({variant.size or variant.product_color.color_name})'. "
                    f"Only {variant.stock_quantity} available."
                )
                return redirect('cart:index')

        # 3. Calculate Financials
        coupon = None
        coupon_id = request.session.get('coupon_id')
        if coupon_id:
            coupon = Coupon.objects.filter(id=coupon_id, is_active=True).first()

        payment_method = request.POST.get('payment_method', 'cod')
        totals = _calculate_cart_totals(cart, coupon, payment_method=payment_method)
        total_discount = totals['discount'] + totals['upi_discount']

        # 4. Generate Order
        order_number = Order.generate_order_number()
        order_notes = request.POST.get('order_notes', '').strip()

        order = Order.objects.create(
            order_number=order_number,
            user=customer_user,
            shipping_address_snapshot=address_snapshot,
            subtotal=totals['subtotal'],
            discount=total_discount,
            shipping_charge=totals['shipping_charge'],
            tax=Decimal('0.00'),
            total=totals['total'],
            payment_method=payment_method,
            payment_status='pending' if payment_method == 'cod' else 'pending',
            order_status='confirmed',
            notes=order_notes,
        )

        # 5. Create Order Items & Decrement Inventory
        for item in cart_items:
            variant = item.variant
            OrderItem.objects.create(
                order=order,
                variant=variant,
                product_name_snapshot=variant.product.name,
                color=variant.product_color.color_name,
                size=variant.size,
                price_snapshot=variant.effective_price,
                quantity=item.quantity,
            )
            # Deduct inventory
            variant.stock_quantity -= item.quantity
            variant.save()

        # 6. Create Payment Record (COD or Razorpay placeholder)
        Payment.objects.create(
            order=order,
            method=payment_method,
            amount=totals['total'],
            status='pending',
            transaction_id=f"TXN-{order.order_number}",
        )

        # 7. Update Coupon Usage Count if applicable
        if coupon and coupon.is_valid and totals['discount'] > 0:
            coupon.used_count += 1
            coupon.save(update_fields=['used_count'])

        # 8. Empty Cart and Session
        cart.items.all().delete()
        request.session.pop('coupon_id', None)
        request.session.pop('guest_checkout_email', None)

    # Seamless login for guest shopper so they can view their order receipt
    if not request.user.is_authenticated:
        old_session_key = request.session.session_key
        login(request, customer_user, backend='django.contrib.auth.backends.ModelBackend')
        merge_guest_cart(request, customer_user, old_session_key=old_session_key)

    messages.success(request, f"Order #{order.order_number} placed successfully!")
    return redirect('orders:order_success', order_number=order.order_number)


@login_required
def order_success_view(request, order_number):
    """
    Order confirmation success receipt page with order summary and tracking details.
    """
    order = get_object_or_404(
        Order.objects.prefetch_related('items__variant__product__colors__images'),
        order_number=order_number,
        user=request.user
    )
    return render(request, 'orders/success.html', {'order': order})


@login_required
def order_list_view(request):
    """
    Customer's past order history.
    """
    orders = Order.objects.filter(user=request.user).prefetch_related('items').order_by('-created_at')
    return render(request, 'orders/order_list.html', {'orders': orders})


@login_required
def order_detail_view(request, order_number):
    """
    Detailed order tracking view with fulfillment status progress, item snapshots,
    address details, and cancellation action.
    """
    order = get_object_or_404(
        Order.objects.prefetch_related('items__variant__product__colors__images'),
        order_number=order_number,
        user=request.user
    )
    return render(request, 'orders/order_detail.html', {'order': order})


@login_required
@require_POST
def cancel_order_view(request, order_number):
    """
    Allows a customer to cancel an order if it is still pending or confirmed.
    Restores stock to inventory.
    """
    order = get_object_or_404(Order, order_number=order_number, user=request.user)

    if order.order_status not in ['pending', 'confirmed']:
        messages.error(request, f"Order #{order.order_number} is already {order.get_order_status_display()} and cannot be cancelled.")
        return redirect('orders:order_detail', order_number=order.order_number)

    with transaction.atomic():
        order.order_status = 'cancelled'
        order.save()

        # Restore inventory
        for item in order.items.select_related('variant').all():
            if item.variant:
                item.variant.stock_quantity += item.quantity
                item.variant.save()

        # Update payment status
        for payment in order.payments.all():
            payment.status = 'failed'
            payment.save()

    messages.success(request, f"Order #{order.order_number} has been cancelled successfully.")
    return redirect('orders:order_detail', order_number=order.order_number)


def returns_policy_view(request):
    """7-Day In-Home Trial, Returns & Exchanges Policy."""
    return render(request, 'orders/returns.html')


def track_order_view(request):
    """Direct Order Lookup by Order Number & Phone/Email."""
    order = None
    searched = False
    query = request.GET.get('order_number', '').strip()
    contact = request.GET.get('contact', '').strip()

    if query:
        searched = True
        qs = Order.objects.filter(order_number__iexact=query)
        if contact:
            qs = qs.filter(Q(user__email__iexact=contact) | Q(shipping_address__icontains=contact))
        order = qs.first()

    return render(request, 'orders/track.html', {
        'order': order,
        'searched': searched,
        'query': query,
        'contact': contact,
    })
