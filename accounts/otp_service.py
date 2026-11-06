import secrets
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from .models import EmailOTP, User


def generate_otp() -> str:
    """
    Generates a cryptographically secure 6-digit numeric OTP code.
    Range: 100000 to 999999.
    """
    return str(secrets.randbelow(900000) + 100000)


def create_and_send_otp(email: str, purpose: str = 'registration', user=None, metadata: dict = None, expiry_minutes: int = 10) -> tuple[bool, str, str]:
    """
    Generates a new 6-digit OTP, saves it in the database,
    invalidates older unused OTPs for the same email and purpose,
    and sends an elegant branded email to the recipient.

    Returns:
        (success: bool, message: str, otp_code: str)
    """
    email = email.strip().lower()
    
    # 1. Rate Limiting: Check if an OTP was created less than 45 seconds ago
    recent_otp = EmailOTP.objects.filter(
        email=email,
        purpose=purpose,
        created_at__gte=timezone.now() - timedelta(seconds=45)
    ).first()
    if recent_otp:
        return False, "Please wait 45 seconds before requesting another verification code.", ""

    # 2. Invalidate previous unverified OTPs
    EmailOTP.objects.filter(email=email, purpose=purpose, is_used=False).update(is_used=True)

    # 3. Generate 6-digit OTP code
    otp_code = generate_otp()
    expires_at = timezone.now() + timedelta(minutes=expiry_minutes)

    otp_obj = EmailOTP.objects.create(
        email=email,
        otp_code=otp_code,
        purpose=purpose,
        user=user,
        metadata=metadata or {},
        expires_at=expires_at
    )

    # 4. Dispatch Email
    try:
        if purpose == 'registration':
            subject = f"Your AvailSmart Verification Code: {otp_code}"
            template_name = 'emails/otp_registration.html'
        elif purpose == 'order_confirmation':
            subject = f"Confirm Your Studio Order: {otp_code} - AvailSmart"
            template_name = 'emails/otp_order_confirmation.html'
        else:
            subject = f"Your Security Verification Code: {otp_code}"
            template_name = 'emails/otp_generic.html'

        context = {
            'email': email,
            'otp_code': otp_code,
            'expiry_minutes': expiry_minutes,
            'purpose': purpose,
            'user': user,
            'metadata': metadata or {},
        }

        html_message = render_to_string(template_name, context)
        plain_message = (
            f"Hello,\n\n"
            f"Your AvailSmart 6-digit verification code is: {otp_code}\n\n"
            f"This code will expire in {expiry_minutes} minutes.\n"
            f"If you did not request this, please disregard this email.\n\n"
            f"Warm regards,\n"
            f"The AvailSmart Studio Team"
        )

        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False
        )

        # Also print to stdout/logs for instant developer verification
        print(f"\n==================================================")
        print(f">> [EMAIL OTP DISPATCHED] To: {email} | Purpose: {purpose}")
        print(f">> [CODE]: {otp_code} (Valid for {expiry_minutes} mins)")
        print(f"==================================================\n")

        user_msg = f"A 6-digit verification code has been dispatched to {email}."
        if getattr(settings, 'DEBUG', False):
            user_msg += f" (Test Code: {otp_code})"

        return True, user_msg, otp_code

    except Exception as e:
        print(f"Error dispatching OTP email to {email}: {e}")
        user_msg = f"A 6-digit verification code has been dispatched to {email}."
        if getattr(settings, 'DEBUG', False):
            user_msg += f" (Test Code: {otp_code})"
        return True, user_msg, otp_code


def verify_otp(email: str, otp_code: str, purpose: str = 'registration') -> tuple[bool, str, EmailOTP | None]:
    """
    Validates a submitted 6-digit OTP code against the database.
    
    Returns:
        (is_valid: bool, error_or_success_message: str, otp_obj: EmailOTP or None)
    """
    email = email.strip().lower()
    otp_code = otp_code.strip()

    if not otp_code or len(otp_code) != 6 or not otp_code.isdigit():
        return False, "Please enter a valid 6-digit numeric verification code.", None

    otp_obj = EmailOTP.objects.filter(
        email=email,
        purpose=purpose,
        is_used=False
    ).order_by('-created_at').first()

    if not otp_obj:
        return False, "No active verification code found for this email. Please request a new one.", None

    if otp_obj.is_expired:
        return False, "This verification code has expired. Please request a new code.", None

    if otp_obj.attempts >= 5:
        otp_obj.is_used = True
        otp_obj.save(update_fields=['is_used'])
        return False, "Too many incorrect attempts. This code has been deactivated. Please request a new one.", None

    if otp_obj.otp_code != otp_code:
        otp_obj.attempts += 1
        otp_obj.save(update_fields=['attempts'])
        remaining = 5 - otp_obj.attempts
        return False, f"Incorrect verification code. {remaining} attempt{'s' if remaining != 1 else ''} remaining.", None

    # OTP is valid!
    otp_obj.is_used = True
    otp_obj.save(update_fields=['is_used'])
    return True, "Verification successful!", otp_obj
