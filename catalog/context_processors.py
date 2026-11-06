from catalog.models import Category
from cart.models import Cart, Wishlist


def nav_context(request):
    """
    Context processor to make top-level navigation categories,
    cart item count, and wishlist item count available across all templates.
    """
    context = {}
    
    # 1. Navigation categories (Parent categories with active children)
    try:
        context['nav_categories'] = Category.objects.filter(
            parent__isnull=True,
            is_active=True
        ).prefetch_related('children').order_by('sort_order', 'name')
    except Exception:
        context['nav_categories'] = []

    # 2. Cart item count
    cart_count = 0
    try:
        if request.user.is_authenticated:
            user_cart = Cart.objects.filter(user=request.user).first()
            if user_cart:
                cart_count = user_cart.total_items
        elif request.session.session_key:
            guest_cart = Cart.objects.filter(session_key=request.session.session_key).first()
            if guest_cart:
                cart_count = guest_cart.total_items
    except Exception:
        cart_count = 0
    context['cart_count'] = cart_count

    # 3. Wishlist count
    wishlist_count = 0
    try:
        if request.user.is_authenticated:
            wishlist_count = Wishlist.objects.filter(user=request.user).count()
    except Exception:
        wishlist_count = 0
    context['wishlist_count'] = wishlist_count

    return context
