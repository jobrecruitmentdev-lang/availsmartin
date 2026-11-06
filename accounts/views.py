import time
from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse

from .forms import (
    UserRegistrationForm, UserLoginForm,
    ForgotPasswordForm, ResetPasswordForm
)
from .models import User
from .otp_service import create_and_send_otp, verify_otp
from cart.models import Cart


def check_rate_limit(request, key_prefix='login', max_attempts=5, lockout_seconds=300):
    """
    Session-based rate limiter for preventing brute-force authentication attacks.
    Returns (is_locked, remaining_seconds).
    """
    session = request.session
    now = time.time()
    
    attempts_key = f"{key_prefix}_attempts"
    lockout_key = f"{key_prefix}_lockout_until"

    lockout_until = session.get(lockout_key, 0)
    if now < lockout_until:
        return True, int(lockout_until - now)

    return False, 0


def record_failed_attempt(request, key_prefix='login', max_attempts=5, lockout_seconds=300):
    session = request.session
    now = time.time()
    attempts_key = f"{key_prefix}_attempts"
    lockout_key = f"{key_prefix}_lockout_until"

    attempts = session.get(attempts_key, 0) + 1
    session[attempts_key] = attempts

    if attempts >= max_attempts:
        session[lockout_key] = now + lockout_seconds
        session[attempts_key] = 0
        return True, lockout_seconds
    return False, 0


def clear_attempts(request, key_prefix='login'):
    request.session.pop(f"{key_prefix}_attempts", None)
    request.session.pop(f"{key_prefix}_lockout_until", None)


def merge_guest_cart(request, user):
    """
    Transfers items from an anonymous session cart to the authenticated user's cart.
    """
    session_key = request.session.session_key
    if not session_key:
        return

    try:
        guest_cart = Cart.objects.filter(session_key=session_key).first()
        if guest_cart and not guest_cart.is_empty:
            user_cart, _ = Cart.objects.get_or_create(user=user)
            for item in guest_cart.items.all():
                existing_item = user_cart.items.filter(variant=item.variant).first()
                if existing_item:
                    existing_item.quantity += item.quantity
                    existing_item.save()
                else:
                    item.cart = user_cart
                    item.save()
            guest_cart.delete()
    except Exception as e:
        print(f"Error merging cart on login: {e}")


def register_view(request):
    if request.user.is_authenticated:
        return redirect('/')

    next_url = request.GET.get('next', '')
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            existing_inactive = User.objects.filter(email=email, is_active=False).first()
            if existing_inactive:
                existing_inactive.name = form.cleaned_data['name']
                existing_inactive.phone = form.cleaned_data.get('phone', '')
                existing_inactive.set_password(form.cleaned_data['password'])
                existing_inactive.save()
                user = existing_inactive
            else:
                user = form.save(commit=False)
                user.is_active = False  # Enforce 6-digit OTP verification before activation
                user.save()

            # Store pending state in session
            request.session['pending_otp_email'] = user.email
            request.session['pending_otp_purpose'] = 'registration'
            if next_url:
                request.session['pending_otp_next'] = next_url

            # Dispatch 6-digit OTP to user's email
            create_and_send_otp(email=user.email, purpose='registration', user=user, expiry_minutes=10)
            messages.info(request, f"A 6-digit security verification code has been dispatched to {user.email}.")
            return redirect('accounts:verify_email')
    else:
        form = UserRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form, 'next': next_url})


def verify_email_otp_view(request):
    if request.user.is_authenticated:
        return redirect('/')

    email = request.session.get('pending_otp_email', '').strip()
    next_url = request.session.get('pending_otp_next', '/')

    if not email:
        messages.warning(request, "No pending registration found. Please register or sign in.")
        return redirect('accounts:register')

    if request.method == 'POST':
        otp_code = request.POST.get('otp_code', '').strip()
        is_valid, msg, otp_obj = verify_otp(email=email, otp_code=otp_code, purpose='registration')

        if is_valid:
            user = User.objects.filter(email=email).first()
            if user:
                user.is_active = True
                user.save(update_fields=['is_active'])
                login(request, user)
                clear_attempts(request, 'login')
                merge_guest_cart(request, user)

                # Clean session state
                request.session.pop('pending_otp_email', None)
                request.session.pop('pending_otp_purpose', None)
                request.session.pop('pending_otp_next', None)

                messages.success(request, f"Welcome to AvailSmart, {user.name}! Your email has been verified successfully.")
                return redirect(next_url if next_url and next_url.startswith('/') else '/')
            else:
                messages.error(request, "Account record could not be found. Please register again.")
                return redirect('accounts:register')
        else:
            messages.error(request, msg)

    return render(request, 'accounts/verify_otp.html', {
        'email': email,
        'next_url': next_url,
    })


@require_POST
def resend_otp_view(request):
    email = request.POST.get('email') or request.session.get('pending_otp_email', '')
    purpose = request.POST.get('purpose', 'registration')

    if not email:
        return JsonResponse({'status': 'error', 'message': 'No email address specified.'}, status=400)

    user = User.objects.filter(email=email).first()
    success, msg, _ = create_and_send_otp(email=email, purpose=purpose, user=user, expiry_minutes=10)

    if success:
        return JsonResponse({'status': 'success', 'message': msg})
    else:
        return JsonResponse({'status': 'error', 'message': msg}, status=429)


def login_view(request):
    if request.user.is_authenticated:
        return redirect('/')

    # Check rate limit
    is_locked, remaining = check_rate_limit(request, 'login')
    if is_locked:
        messages.error(request, f"Too many failed login attempts. Please wait {remaining} seconds before trying again.")
        return render(request, 'accounts/login.html', {'form': UserLoginForm(), 'is_locked': True, 'remaining': remaining})

    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)

            user = authenticate(request, email=email, password=password)
            if user is not None:
                if not user.is_active:
                    messages.error(request, "This account has been deactivated. Please contact customer support.")
                else:
                    login(request, user)
                    clear_attempts(request, 'login')
                    merge_guest_cart(request, user)

                    if not remember_me:
                        request.session.set_expiry(0)  # Expires on browser close
                    else:
                        request.session.set_expiry(86400 * 14)  # 14 days

                    messages.success(request, f"Welcome back, {user.name}!")
                    next_url = request.GET.get('next')
                    return redirect(next_url if next_url and next_url.startswith('/') else '/')
            else:
                is_now_locked, lockout_sec = record_failed_attempt(request, 'login')
                if is_now_locked:
                    messages.error(request, f"Too many failed attempts. Account login locked for {lockout_sec // 60} minutes.")
                else:
                    messages.error(request, "Invalid email address or password. Please try again.")
    else:
        form = UserLoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out safely.")
    return redirect('/')


def forgot_password_view(request):
    if request.user.is_authenticated:
        return redirect('/')

    sent = False
    if request.method == 'POST':
        form = ForgotPasswordForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            user = User.objects.filter(email=email, is_active=True).first()
            if user:
                token = default_token_generator.make_token(user)
                uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
                reset_url = request.build_absolute_uri(
                    reverse('accounts:reset_password', kwargs={'uidb64': uidb64, 'token': token})
                )
                subject = "Reset your AvailSmart Password"
                message = f"Hello {user.name},\n\nPlease click the link below to reset your AvailSmart account password:\n\n{reset_url}\n\nIf you did not request this, please ignore this email.\n\nBest regards,\nAvailSmart Team"
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=False,
                )
                request.session['last_reset_url'] = reset_url
            sent = True
            messages.success(request, "If an account with that email exists, we have sent instructions to reset your password.")
    else:
        form = ForgotPasswordForm()

    demo_reset_url = request.session.pop('last_reset_url', None)
    return render(request, 'accounts/forgot_password.html', {'form': form, 'sent': sent, 'demo_reset_url': demo_reset_url})


def reset_password_view(request, uidb64, token):
    if request.user.is_authenticated:
        return redirect('/')

    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(request, "The password reset link is invalid or has expired.")
        return redirect('accounts:login')

    if request.method == 'POST':
        form = ResetPasswordForm(request.POST)
        if form.is_valid():
            new_password = form.cleaned_data['new_password']
            user.set_password(new_password)
            user.save()
            messages.success(request, "Your password has been reset successfully. Please log in with your new password.")
            return redirect('accounts:login')
    else:
        form = ResetPasswordForm()

    return render(request, 'accounts/reset_password.html', {'form': form})


from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth import update_session_auth_hash
from django.shortcuts import get_object_or_404
from .models import Address
from .forms import UserProfileForm, AddressForm
from orders.models import Order
from cart.models import Wishlist


@login_required
def profile_view(request):
    """
    Customer profile dashboard: update profile details, change password,
    and view summary of recent orders and addresses.
    """
    user = request.user
    profile_form = UserProfileForm(instance=user)
    password_form = PasswordChangeForm(user=user)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_profile':
            profile_form = UserProfileForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, "Profile details updated successfully.")
                return redirect('accounts:profile')
        elif action == 'change_password':
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                user_obj = password_form.save()
                update_session_auth_hash(request, user_obj)
                messages.success(request, "Your password has been changed successfully.")
                return redirect('accounts:profile')

    recent_orders = Order.objects.filter(user=user).order_by('-created_at')[:3]
    default_address = Address.objects.filter(user=user, is_default=True, is_active=True).first()
    wishlist_count = Wishlist.objects.filter(user=user).count()

    context = {
        'profile_form': profile_form,
        'password_form': password_form,
        'recent_orders': recent_orders,
        'default_address': default_address,
        'wishlist_count': wishlist_count,
    }
    return render(request, 'accounts/profile.html', context)


@login_required
def address_list_view(request):
    """
    Customer address book management.
    """
    addresses = Address.objects.filter(user=request.user, is_active=True).order_by('-is_default', '-created_at')
    return render(request, 'accounts/addresses.html', {'addresses': addresses})


@login_required
def address_add_view(request):
    """
    Add a new delivery address to the customer's account.
    """
    next_url = request.GET.get('next', reverse('accounts:addresses'))
    if request.method == 'POST':
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            # If this is the user's first active address, make it default automatically
            if not Address.objects.filter(user=request.user, is_active=True).exists():
                address.is_default = True
            address.save()
            messages.success(request, "New address added successfully.")
            return redirect(next_url)
    else:
        form = AddressForm()

    return render(request, 'accounts/address_form.html', {'form': form, 'title': 'Add New Address', 'next_url': next_url})


@login_required
def address_edit_view(request, address_id):
    """
    Edit an existing delivery address.
    """
    address = get_object_or_404(Address, id=address_id, user=request.user, is_active=True)
    next_url = request.GET.get('next', reverse('accounts:addresses'))

    if request.method == 'POST':
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, "Address updated successfully.")
            return redirect(next_url)
    else:
        form = AddressForm(instance=address)

    return render(request, 'accounts/address_form.html', {'form': form, 'title': 'Edit Address', 'address': address, 'next_url': next_url})


@login_required
def address_delete_view(request, address_id):
    """
    Delete a delivery address.
    """
    address = get_object_or_404(Address, id=address_id, user=request.user)
    next_url = request.GET.get('next', reverse('accounts:addresses'))
    was_default = address.is_default
    address.delete()

    # If the deleted address was default, set another address as default
    if was_default:
        next_addr = Address.objects.filter(user=request.user, is_active=True).first()
        if next_addr:
            next_addr.is_default = True
            next_addr.save()

    messages.info(request, "Address deleted successfully.")
    return redirect(next_url)


@login_required
def address_set_default_view(request, address_id):
    """
    Sets a delivery address as default.
    """
    address = get_object_or_404(Address, id=address_id, user=request.user, is_active=True)
    address.is_default = True
    address.save()
    messages.success(request, f"'{address.full_name} ({address.city})' set as your default delivery address.")
    next_url = request.GET.get('next', reverse('accounts:addresses'))
    return redirect(next_url)
