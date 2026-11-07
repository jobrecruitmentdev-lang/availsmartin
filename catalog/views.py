import json
from decimal import Decimal
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Min, Max, Count, Avg, Case, When, F, DecimalField
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.template.loader import render_to_string
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.urls import reverse

from .models import (
    Category, Brand, Product, ProductColor,
    ProductImage, ProductVariant, ProductSpecification,
    Review, Banner
)
from cart.models import Wishlist


def _get_user_wishlist_ids(user):
    """Returns a set of product IDs saved by the user in their wishlist."""
    if user and user.is_authenticated:
        return set(Wishlist.objects.filter(user=user).values_list('product_id', flat=True))
    return set()


def home_view(request):
    """
    Homepage view with slim hero banner, category tiles, trending items,
    new arrivals, best deals, and trust strip.
    """
    banners = Banner.objects.filter(is_active=True).order_by('sort_order')
    categories = Category.objects.filter(parent__isnull=True, is_active=True).prefetch_related('children').order_by('sort_order')[:8]
    
    # Trending (Featured)
    featured_products = (
        Product.objects.filter(is_featured=True, is_active=True)
        .select_related('brand', 'category')
        .prefetch_related('colors__images', 'variants')[:8]
    )
    
    # New Arrivals
    new_arrivals = (
        Product.objects.filter(is_active=True)
        .select_related('brand', 'category')
        .prefetch_related('colors__images', 'variants')
        .order_by('-created_at')[:8]
    )
    
    # Best Deals (highest discount percentage)
    best_deals = (
        Product.objects.filter(is_active=True, discount_percent__gt=0)
        .select_related('brand', 'category')
        .prefetch_related('colors__images', 'variants')
        .order_by('-discount_percent')[:8]
    )

    wishlist_ids = _get_user_wishlist_ids(request.user)

    context = {
        'banners': banners,
        'categories': categories,
        'featured_products': featured_products,
        'new_arrivals': new_arrivals,
        'best_deals': best_deals,
        'wishlist_ids': wishlist_ids,
    }
    return render(request, 'catalog/home.html', context)


def _get_category_descendants(category):
    """Recursively returns category IDs for a category and all its children."""
    descendant_ids = [category.id]
    children = category.children.filter(is_active=True)
    for child in children:
        descendant_ids.extend(_get_category_descendants(child))
    return descendant_ids


def catalog_view(request, slug=None):
    """
    High-level filtered catalog listing supporting both traditional GET
    and AJAX dynamic filter requests.
    """
    # 1. Base Queryset with price annotation for accurate ordering
    effective_price_expr = Case(
        When(discount_price__isnull=False, discount_price__gt=0, discount_price__lt=F('base_price'), then=F('discount_price')),
        default=F('base_price'),
        output_field=DecimalField(max_digits=10, decimal_places=2)
    )

    queryset = (
        Product.objects.filter(is_active=True)
        .select_related('brand', 'category')
        .prefetch_related('colors__images', 'variants')
        .annotate(price_val=effective_price_expr)
    )

    # 2. Extract Query Parameters
    selected_category = None
    cat_ids = None
    category_slug = slug or request.GET.get('category')
    if category_slug:
        selected_category = Category.objects.filter(slug=category_slug, is_active=True).first()
        if selected_category:
            cat_ids = _get_category_descendants(selected_category)
            queryset = queryset.filter(category_id__in=cat_ids)

    # Brand filter (can be multiple)
    selected_brands = request.GET.getlist('brand')
    if selected_brands:
        queryset = queryset.filter(brand__slug__in=selected_brands)

    # Price bounds filter
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        try:
            queryset = queryset.filter(price_val__gte=Decimal(min_price))
        except (ValueError, TypeError):
            pass
    if max_price:
        try:
            queryset = queryset.filter(price_val__lte=Decimal(max_price))
        except (ValueError, TypeError):
            pass

    # Color filter
    selected_colors = request.GET.getlist('color')
    if selected_colors:
        queryset = queryset.filter(colors__color_name__in=selected_colors).distinct()

    # Size filter
    selected_sizes = request.GET.getlist('size')
    if selected_sizes:
        queryset = queryset.filter(variants__size__in=selected_sizes).distinct()

    # Rating filter
    rating_filter = request.GET.get('rating')
    if rating_filter:
        try:
            queryset = queryset.filter(rating_avg__gte=Decimal(rating_filter))
        except (ValueError, TypeError):
            pass

    # Discount filter (e.g. 10%, 20%, 50%)
    discount_filter = request.GET.get('discount')
    if discount_filter:
        try:
            queryset = queryset.filter(discount_percent__gte=int(discount_filter))
        except (ValueError, TypeError):
            pass

    # In-stock only
    in_stock_only = request.GET.get('in_stock') in ['1', 'true', 'on']
    if in_stock_only:
        queryset = queryset.filter(variants__stock_quantity__gt=0, variants__is_active=True).distinct()

    # Sorting
    sort = request.GET.get('sort', 'newest')
    if sort == 'price_low':
        queryset = queryset.order_by('price_val', 'id')
    elif sort == 'price_high':
        queryset = queryset.order_by('-price_val', '-id')
    elif sort == 'rating':
        queryset = queryset.order_by('-rating_avg', '-rating_count')
    elif sort == 'popular':
        queryset = queryset.order_by('-rating_count', '-rating_avg')
    elif sort == 'discount':
        queryset = queryset.order_by('-discount_percent')
    else:  # newest
        queryset = queryset.order_by('-created_at')

    # Distinct
    queryset = queryset.distinct()

    # 3. Pagination (12 items per page)
    page_num = request.GET.get('page', 1)
    paginator = Paginator(queryset, 12)
    try:
        products_page = paginator.page(page_num)
    except PageNotAnInteger:
        products_page = paginator.page(1)
    except EmptyPage:
        products_page = paginator.page(paginator.num_pages)

    # 4. Aggregates for filter sidebar choices
    all_categories = Category.objects.filter(parent__isnull=True, is_active=True).prefetch_related('children').order_by('sort_order')
    available_brands = Brand.objects.filter(is_active=True, products__is_active=True).annotate(pcount=Count('products')).filter(pcount__gt=0).order_by('name')
    
    # Available unique colors and sizes (cleanly deduplicated with real product counts)
    color_qs = ProductColor.objects.filter(is_active=True, product__is_active=True)
    if cat_ids:
        available_colors = color_qs.filter(product__category_id__in=cat_ids).values('color_name', 'color_hex').annotate(pcount=Count('product', distinct=True)).order_by('color_name')
        if not available_colors.exists():
            available_colors = color_qs.values('color_name', 'color_hex').annotate(pcount=Count('product', distinct=True)).order_by('color_name')
    else:
        available_colors = color_qs.values('color_name', 'color_hex').annotate(pcount=Count('product', distinct=True)).order_by('color_name')

    size_qs = ProductVariant.objects.filter(is_active=True, product__is_active=True).exclude(size='')
    if cat_ids:
        available_sizes = size_qs.filter(product__category_id__in=cat_ids).values_list('size', flat=True).distinct().order_by('size')
    else:
        available_sizes = size_qs.values_list('size', flat=True).distinct().order_by('size')

    # Catalog overall price range for slider
    price_aggregate = Product.objects.filter(is_active=True).aggregate(
        min_p=Min('base_price'),
        max_p=Max('base_price')
    )
    catalog_min_price = int(price_aggregate['min_p'] or 0)
    catalog_max_price = int(price_aggregate['max_p'] or 10000)

    # 5. Build Active Filters List for Chips UI
    active_filters = []
    if selected_category:
        active_filters.append({'type': 'category', 'label': f"Category: {selected_category.name}", 'value': selected_category.slug})
    for b in selected_brands:
        brand_obj = Brand.objects.filter(slug=b).first()
        active_filters.append({'type': 'brand', 'label': f"Brand: {brand_obj.name if brand_obj else b}", 'value': b})
    if min_price:
        active_filters.append({'type': 'min_price', 'label': f"Min: ₹{min_price}", 'value': min_price})
    if max_price:
        active_filters.append({'type': 'max_price', 'label': f"Max: ₹{max_price}", 'value': max_price})
    for c in selected_colors:
        active_filters.append({'type': 'color', 'label': f"Color: {c}", 'value': c})
    for s in selected_sizes:
        active_filters.append({'type': 'size', 'label': f"Size: {s}", 'value': s})
    if rating_filter:
        active_filters.append({'type': 'rating', 'label': f"{rating_filter}★ & Above", 'value': rating_filter})
    if discount_filter:
        active_filters.append({'type': 'discount', 'label': f"{discount_filter}%+ Off", 'value': discount_filter})
    if in_stock_only:
        active_filters.append({'type': 'in_stock', 'label': "In Stock Only", 'value': '1'})

    wishlist_ids = _get_user_wishlist_ids(request.user)

    # 6. Response Handling: AJAX JSON vs Normal Page Render
    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        request.GET.get('ajax') == '1' or
        request.GET.get('format') == 'json'
    )

    context = {
        'products': products_page,
        'total_count': paginator.count,
        'selected_category': selected_category,
        'selected_brands': selected_brands,
        'selected_colors': selected_colors,
        'selected_sizes': selected_sizes,
        'min_price': min_price or catalog_min_price,
        'max_price': max_price or catalog_max_price,
        'catalog_min_price': catalog_min_price,
        'catalog_max_price': catalog_max_price,
        'rating_filter': rating_filter,
        'discount_filter': discount_filter,
        'in_stock_only': in_stock_only,
        'sort': sort,
        'all_categories': all_categories,
        'available_brands': available_brands,
        'available_colors': available_colors,
        'available_sizes': available_sizes,
        'active_filters': active_filters,
        'wishlist_ids': wishlist_ids,
    }

    if is_ajax:
        html = render_to_string('catalog/partials/product_grid.html', context, request=request)
        return JsonResponse({
            'status': 'success',
            'html': html,
            'total_count': paginator.count,
            'active_filters': active_filters,
            'page': products_page.number,
            'num_pages': paginator.num_pages,
            'has_next': products_page.has_next(),
            'has_previous': products_page.has_previous(),
        })

    return render(request, 'catalog/listing.html', context)


def search_autocomplete_view(request):
    """
    Live autocomplete search endpoint returning products with thumbnails,
    categories, and brands as JSON for the header live search dropdown.
    """
    query = request.GET.get('q', '').strip()
    if len(query) < 2:
        return JsonResponse({'products': [], 'categories': [], 'brands': []})

    # Matching products
    products_qs = (
        Product.objects.filter(
            Q(name__icontains=query) | Q(tags__icontains=query) | Q(brand__name__icontains=query),
            is_active=True
        )
        .select_related('brand', 'category')
        .prefetch_related('colors__images')[:5]
    )

    products = []
    for p in products_qs:
        prim = p.primary_image
        thumb_url = prim.thumbnail.url if prim and prim.thumbnail else (prim.image.url if prim else '')
        products.append({
            'id': p.id,
            'name': p.name,
            'slug': p.slug,
            'brand': p.brand.name if p.brand else 'AvailSmart',
            'category': p.category.name,
            'price': str(p.effective_price),
            'base_price': str(p.base_price),
            'has_discount': p.has_discount,
            'discount_percent': p.discount_percent,
            'thumbnail': thumb_url,
            'url': reverse('catalog:product_detail', kwargs={'slug': p.slug}),
        })

    # Matching categories
    categories_qs = Category.objects.filter(name__icontains=query, is_active=True)[:3]
    categories = []
    for c in categories_qs:
        categories.append({
            'name': c.name,
            'slug': c.slug,
            'url': reverse('catalog:category_listing', kwargs={'slug': c.slug}),
        })

    # Matching brands
    brands_qs = Brand.objects.filter(name__icontains=query, is_active=True)[:3]
    brands = []
    for b in brands_qs:
        brands.append({
            'name': b.name,
            'slug': b.slug,
            'logo': b.logo.url if b.logo else '',
            'url': f"/catalog/?brand={b.slug}",
        })

    return JsonResponse({
        'query': query,
        'products': products,
        'categories': categories,
        'brands': brands,
    })


def search_view(request):
    """
    Full search results page with keywords matched against title, descriptions,
    tags, brands, and categories, combined with full catalog filtering capabilities.
    """
    query = request.GET.get('q', '').strip()
    
    # Delegate to catalog listing view while passing search context
    effective_price_expr = Case(
        When(discount_price__isnull=False, discount_price__gt=0, discount_price__lt=F('base_price'), then=F('discount_price')),
        default=F('base_price'),
        output_field=DecimalField(max_digits=10, decimal_places=2)
    )

    queryset = (
        Product.objects.filter(is_active=True)
        .select_related('brand', 'category')
        .prefetch_related('colors__images', 'variants')
        .annotate(price_val=effective_price_expr)
    )

    if query:
        queryset = queryset.filter(
            Q(name__icontains=query) |
            Q(short_description__icontains=query) |
            Q(full_description__icontains=query) |
            Q(tags__icontains=query) |
            Q(brand__name__icontains=query) |
            Q(category__name__icontains=query) |
            Q(sku__icontains=query)
        )

    # Apply other filters from GET parameters
    selected_brands = request.GET.getlist('brand')
    if selected_brands:
        queryset = queryset.filter(brand__slug__in=selected_brands)

    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if min_price:
        try:
            queryset = queryset.filter(price_val__gte=Decimal(min_price))
        except (ValueError, TypeError):
            pass
    if max_price:
        try:
            queryset = queryset.filter(price_val__lte=Decimal(max_price))
        except (ValueError, TypeError):
            pass

    selected_colors = request.GET.getlist('color')
    if selected_colors:
        queryset = queryset.filter(colors__color_name__in=selected_colors).distinct()

    selected_sizes = request.GET.getlist('size')
    if selected_sizes:
        queryset = queryset.filter(variants__size__in=selected_sizes).distinct()

    rating_filter = request.GET.get('rating')
    if rating_filter:
        try:
            queryset = queryset.filter(rating_avg__gte=Decimal(rating_filter))
        except (ValueError, TypeError):
            pass

    in_stock_only = request.GET.get('in_stock') in ['1', 'true', 'on']
    if in_stock_only:
        queryset = queryset.filter(variants__stock_quantity__gt=0, variants__is_active=True).distinct()

    sort = request.GET.get('sort', 'newest')
    if sort == 'price_low':
        queryset = queryset.order_by('price_val', 'id')
    elif sort == 'price_high':
        queryset = queryset.order_by('-price_val', '-id')
    elif sort == 'rating':
        queryset = queryset.order_by('-rating_avg', '-rating_count')
    elif sort == 'popular':
        queryset = queryset.order_by('-rating_count', '-rating_avg')
    elif sort == 'discount':
        queryset = queryset.order_by('-discount_percent')
    else:
        queryset = queryset.order_by('-created_at')

    queryset = queryset.distinct()

    paginator = Paginator(queryset, 12)
    page_num = request.GET.get('page', 1)
    try:
        products_page = paginator.page(page_num)
    except (PageNotAnInteger, EmptyPage):
        products_page = paginator.page(1)

    all_categories = Category.objects.filter(parent__isnull=True, is_active=True).prefetch_related('children').order_by('sort_order')
    available_brands = Brand.objects.filter(is_active=True, products__is_active=True).annotate(pcount=Count('products')).filter(pcount__gt=0).order_by('name')
    color_qs = ProductColor.objects.filter(is_active=True, product__is_active=True)
    available_colors = color_qs.values('color_name', 'color_hex').annotate(pcount=Count('product', distinct=True)).order_by('color_name')
    available_sizes = ProductVariant.objects.filter(is_active=True, product__is_active=True).exclude(size='').values_list('size', flat=True).distinct().order_by('size')

    wishlist_ids = _get_user_wishlist_ids(request.user)

    context = {
        'query': query,
        'products': products_page,
        'total_count': paginator.count,
        'selected_brands': selected_brands,
        'selected_colors': selected_colors,
        'selected_sizes': selected_sizes,
        'min_price': min_price or 0,
        'max_price': max_price or 10000,
        'catalog_min_price': 0,
        'catalog_max_price': 10000,
        'rating_filter': rating_filter,
        'in_stock_only': in_stock_only,
        'sort': sort,
        'all_categories': all_categories,
        'available_brands': available_brands,
        'available_colors': available_colors,
        'available_sizes': available_sizes,
        'wishlist_ids': wishlist_ids,
        'is_search_page': True,
    }

    is_ajax = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest' or
        request.GET.get('ajax') == '1' or
        request.GET.get('format') == 'json'
    )
    if is_ajax:
        html = render_to_string('catalog/partials/product_grid.html', context, request=request)
        return JsonResponse({
            'status': 'success',
            'html': html,
            'total_count': paginator.count,
        })

    return render(request, 'catalog/search.html', context)


def product_detail_view(request, slug):
    """
    Rich interactive product detail page with:
    - Dynamic color swatch switcher (gallery changes to that color's images)
    - Variant size selector with live price & inventory display
    - Description, Specifications, and Reviews tabs
    - Related products carousel
    """
    product = get_object_or_404(
        Product.objects.select_related('brand', 'category')
        .prefetch_related(
            'colors__images',
            'variants__product_color',
            'specifications',
            'reviews__user'
        ),
        slug=slug,
        is_active=True
    )

    # 1. Structure Color & Image Map for Alpine.js
    colors_data = []
    for c in product.colors.filter(is_active=True):
        images_list = []
        for img in c.images.all():
            images_list.append({
                'id': img.id,
                'url': img.image.url,
                'thumb': img.thumbnail.url if img.thumbnail else img.image.url,
                'alt': img.alt_text or f"{product.name} - {c.color_name}",
                'is_primary': img.is_primary,
            })
        colors_data.append({
            'id': c.id,
            'name': c.color_name,
            'hex': c.color_hex,
            'images': images_list,
        })

    # 2. Structure Variant Map for Alpine.js
    variants_data = []
    for v in product.variants.filter(is_active=True):
        variants_data.append({
            'id': v.id,
            'color_id': v.product_color_id,
            'color_name': v.product_color.color_name,
            'size': v.size,
            'sku': v.sku,
            'price': str(v.effective_price),
            'stock': v.stock_quantity,
            'is_in_stock': v.is_in_stock,
        })

    # 3. Reviews & Rating Statistics
    approved_reviews = product.reviews.filter(is_approved=True).select_related('user').order_by('-created_at')
    total_reviews = approved_reviews.count()

    # Calculate star breakdown counts & percentages
    star_counts = {5: 0, 4: 0, 3: 0, 2: 1, 1: 0}
    for r in approved_reviews:
        if r.rating in star_counts:
            star_counts[r.rating] += 1

    star_percentages = {}
    for star, count in star_counts.items():
        star_percentages[star] = round((count / total_reviews * 100), 1) if total_reviews > 0 else 0

    # User review status
    user_has_reviewed = False
    if request.user.is_authenticated:
        user_has_reviewed = product.reviews.filter(user=request.user).exists()

    # 4. Related Products
    related_products = (
        Product.objects.filter(
            Q(category=product.category) | Q(brand=product.brand),
            is_active=True
        )
        .exclude(id=product.id)
        .select_related('brand', 'category')
        .prefetch_related('colors__images', 'variants')[:4]
    )

    wishlist_ids = _get_user_wishlist_ids(request.user)
    is_wishlisted = product.id in wishlist_ids

    context = {
        'product': product,
        'colors_json': json.dumps(colors_data),
        'variants_json': json.dumps(variants_data),
        'colors_data': colors_data,
        'variants_data': variants_data,
        'reviews': approved_reviews,
        'total_reviews': total_reviews,
        'star_counts': star_counts,
        'star_percentages': star_percentages,
        'user_has_reviewed': user_has_reviewed,
        'related_products': related_products,
        'wishlist_ids': wishlist_ids,
        'is_wishlisted': is_wishlisted,
    }
    return render(request, 'catalog/detail.html', context)


@login_required
@require_POST
def add_review_view(request, slug):
    """
    Submits a customer rating and review for a product.
    Requires user authentication; review is saved with is_approved=False for admin moderation.
    """
    product = get_object_or_404(Product, slug=slug, is_active=True)

    # Check if already reviewed
    existing_review = Review.objects.filter(user=request.user, product=product).first()
    if existing_review:
        messages.warning(request, "You have already submitted a review for this product.")
        return redirect('catalog:product_detail', slug=slug)

    try:
        rating = int(request.POST.get('rating', 5))
        if rating < 1 or rating > 5:
            rating = 5
    except (ValueError, TypeError):
        rating = 5

    comment = request.POST.get('comment', '').strip()
    if not comment:
        messages.error(request, "Please enter your review feedback.")
        return redirect('catalog:product_detail', slug=slug)

    Review.objects.create(
        user=request.user,
        product=product,
        rating=rating,
        comment=comment,
        is_approved=False  # Requires admin approval via custom admin panel
    )

    messages.success(request, "Thank you! Your review has been submitted and is pending moderation.")
    return redirect('catalog:product_detail', slug=slug)


def robots_txt_view(request):
    """
    Dynamic robots.txt response preventing crawler indexing of admin and user account routes.
    """
    lines = [
        "User-agent: *",
        "Disallow: /benzo/",
        "Disallow: /django-admin/",
        "Disallow: /accounts/",
        "Disallow: /cart/",
        "Disallow: /orders/",
        "Disallow: /checkout/",
        "Allow: /",
        "Allow: /catalog/",
        "Allow: /media/",
        "Allow: /static/",
        f"Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml_view(request):
    """
    Generates standard XML sitemap for search engine crawlers.
    """
    base_url = f"{request.scheme}://{request.get_host()}"
    urls = [
        {'loc': f"{base_url}/", 'priority': '1.0', 'changefreq': 'daily'},
        {'loc': f"{base_url}/catalog/", 'priority': '0.9', 'changefreq': 'daily'},
    ]

    # Categories
    for cat in Category.objects.filter(is_active=True):
        urls.append({
            'loc': f"{base_url}/catalog/{cat.slug}/",
            'lastmod': cat.updated_at.strftime('%Y-%m-%d'),
            'priority': '0.8',
            'changefreq': 'weekly',
        })

    # Products
    for p in Product.objects.filter(is_active=True):
        urls.append({
            'loc': f"{base_url}/product/{p.slug}/",
            'lastmod': p.updated_at.strftime('%Y-%m-%d'),
            'priority': '0.9',
            'changefreq': 'weekly',
        })

    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for u in urls:
        xml_lines.append('  <url>')
        xml_lines.append(f"    <loc>{u['loc']}</loc>")
        if 'lastmod' in u:
            xml_lines.append(f"    <lastmod>{u['lastmod']}</lastmod>")
        xml_lines.append(f"    <changefreq>{u['changefreq']}</changefreq>")
        xml_lines.append(f"    <priority>{u['priority']}</priority>")
        xml_lines.append('  </url>')
    xml_lines.append('</urlset>')

    return HttpResponse("\n".join(xml_lines), content_type="application/xml")


def story_view(request):
    """The Studio Craft Story: Manifesto, Clay Harvesting, Artisans, Slow Living."""
    return render(request, 'catalog/story.html')


def contact_view(request):
    """Concierge & Studio Support Desk."""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        email = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        if name and email and message:
            messages.success(request, f"Thank you, {name}. Your note has been received by our studio concierge. We will respond within 24 hours.")
            return redirect('catalog:contact')
        else:
            messages.error(request, "Please fill in all required fields before submitting your enquiry.")
    return render(request, 'catalog/contact.html')


def faqs_view(request):
    """Studio Care Guide & Frequently Asked Questions."""
    return render(request, 'catalog/faqs.html')


def privacy_view(request):
    """Studio Ethics & Privacy Policy."""
    return render(request, 'catalog/privacy.html')


def terms_view(request):
    """Terms of Craft & Purchase."""
    return render(request, 'catalog/terms.html')
