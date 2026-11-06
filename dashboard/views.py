import time
import json
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Sum, Count, Q, F, Case, When, Value, IntegerField
from django.utils import timezone
from django.utils.text import slugify
from datetime import timedelta

from accounts.forms import AdminLoginForm
from accounts.models import User
from catalog.models import (
    Product, Category, Brand, ProductColor, ProductImage,
    ProductVariant, ProductSpecification, Review, Banner
)
from cart.models import Coupon
from orders.models import Order, OrderItem, Payment
from .forms import CategoryForm, BrandForm, ProductBaseForm, CouponForm, BannerForm


def is_staff_or_superuser(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)


# ==========================================
# AUTHENTICATION
# ==========================================
def admin_login_view(request):
    if is_staff_or_superuser(request.user):
        return redirect('dashboard:index')

    session = request.session
    now = time.time()
    lockout_until = session.get('admin_lockout_until', 0)
    if now < lockout_until:
        remaining = int(lockout_until - now)
        messages.error(request, f"Admin portal locked due to repeated failed attempts. Please wait {remaining} seconds.")
        return render(request, 'dashboard/login.html', {'form': AdminLoginForm(), 'is_locked': True, 'remaining': remaining})

    if request.method == 'POST':
        form = AdminLoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email'].strip().lower()
            password = form.cleaned_data['password']

            user = authenticate(request, email=email, password=password)
            if user is not None:
                if not (user.is_staff or user.is_superuser):
                    messages.error(request, "Access Denied: You do not have staff administrator privileges.")
                elif not user.is_active:
                    messages.error(request, "This administrator account is disabled.")
                else:
                    login(request, user)
                    session.pop('admin_attempts', None)
                    session.pop('admin_lockout_until', None)
                    messages.success(request, f"Welcome to the AvailSmart Admin Portal, {user.name}!")
                    next_url = request.GET.get('next')
                    return redirect(next_url if next_url and (next_url.startswith('/avail-admin') or next_url.startswith('/admin')) else 'dashboard:index')
            else:
                attempts = session.get('admin_attempts', 0) + 1
                session['admin_attempts'] = attempts
                if attempts >= 5:
                    session['admin_lockout_until'] = now + 300
                    session['admin_attempts'] = 0
                    messages.error(request, "Too many failed admin login attempts. Portal locked for 5 minutes.")
                else:
                    messages.error(request, f"Invalid administrative credentials. Attempt {attempts}/5.")
    else:
        form = AdminLoginForm()

    return render(request, 'dashboard/login.html', {'form': form})


def admin_logout_view(request):
    logout(request)
    messages.info(request, "Logged out from AvailSmart Admin Panel.")
    return redirect('dashboard:login')


# ==========================================
# DASHBOARD OVERVIEW & ANALYTICS (CHART.JS)
# ==========================================
@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def admin_dashboard(request):
    total_products = Product.objects.count()
    total_orders = Order.objects.count()
    total_users = User.objects.filter(is_staff=False).count()
    total_sales = Order.objects.filter(payment_status='completed').aggregate(sum=Sum('total'))['sum'] or 0
    
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    orders_today = Order.objects.filter(created_at__gte=today_start).count()
    
    low_stock_variants = ProductVariant.objects.select_related('product', 'product_color').filter(
        stock_quantity__lte=15, is_active=True
    ).order_by('stock_quantity')[:8]
    
    recent_orders = Order.objects.select_related('user').order_by('-created_at')[:6]
    pending_reviews_count = Review.objects.filter(is_approved=False).count()

    # Last 7 Days Sales Trend for Chart.js
    chart_labels = []
    chart_sales = []
    chart_order_counts = []
    for i in range(6, -1, -1):
        day = timezone.now().date() - timedelta(days=i)
        day_start = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.min.time()))
        day_end = timezone.make_aware(timezone.datetime.combine(day, timezone.datetime.max.time()))
        
        day_orders = Order.objects.filter(created_at__range=(day_start, day_end))
        day_sales = day_orders.filter(payment_status='completed').aggregate(sum=Sum('total'))['sum'] or 0
        
        chart_labels.append(day.strftime('%b %d'))
        chart_sales.append(float(day_sales))
        chart_order_counts.append(day_orders.count())

    context = {
        'total_products': total_products,
        'total_orders': total_orders,
        'total_users': total_users,
        'total_sales': total_sales,
        'orders_today': orders_today,
        'low_stock_variants': low_stock_variants,
        'recent_orders': recent_orders,
        'pending_reviews_count': pending_reviews_count,
        'chart_labels_json': json.dumps(chart_labels),
        'chart_sales_json': json.dumps(chart_sales),
        'chart_orders_json': json.dumps(chart_order_counts),
        'active_menu': 'dashboard',
    }
    return render(request, 'dashboard/dashboard.html', context)


# ==========================================
# CATEGORIES CRUD
# ==========================================
@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def category_list(request):
    query = request.GET.get('q', '').strip()
    level = request.GET.get('level', 'all').strip()

    categories = Category.objects.select_related('parent').annotate(
        direct_count=Count('products', distinct=True),
        child_count=Count('children__products', distinct=True),
        family_id=Case(
            When(parent__isnull=True, then=F('id')),
            default=F('parent_id'),
            output_field=IntegerField()
        ),
        is_child=Case(
            When(parent__isnull=True, then=Value(0)),
            default=Value(1),
            output_field=IntegerField()
        )
    )

    # Filter counts for tabs
    total_count = Category.objects.count()
    parents_count = Category.objects.filter(parent__isnull=True).count()
    subcategories_count = Category.objects.filter(parent__isnull=False).count()

    if query:
        categories = categories.filter(Q(name__icontains=query) | Q(description__icontains=query))

    if level == 'parents':
        categories = categories.filter(parent__isnull=True).order_by('sort_order', 'name')
    elif level == 'subcategories':
        categories = categories.filter(parent__isnull=False).order_by('parent__name', 'sort_order', 'name')
    else:
        # Hierarchical grouping: Family ID -> Parent first -> Child indented
        categories = categories.order_by('family_id', 'is_child', 'sort_order', 'name')

    paginator = Paginator(categories, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    for cat in page_obj:
        cat.total_items_count = cat.direct_count + cat.child_count

    return render(request, 'dashboard/categories/list.html', {
        'page_obj': page_obj,
        'query': query,
        'level': level,
        'total_count': total_count,
        'parents_count': parents_count,
        'subcategories_count': subcategories_count,
        'active_menu': 'categories',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def category_add(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES)
        if form.is_valid():
            category = form.save()
            messages.success(request, f"Category '{category.name}' created successfully!")
            return redirect('dashboard:category_list')
    else:
        form = CategoryForm()

    return render(request, 'dashboard/categories/form.html', {
        'form': form,
        'title': 'Add New Category',
        'active_menu': 'categories',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def category_edit(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        form = CategoryForm(request.POST, request.FILES, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, f"Category '{category.name}' updated successfully!")
            return redirect('dashboard:category_list')
    else:
        form = CategoryForm(instance=category)

    return render(request, 'dashboard/categories/form.html', {
        'form': form,
        'category': category,
        'title': f"Edit Category: {category.name}",
        'active_menu': 'categories',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk)
    if request.method == 'POST':
        cat_name = category.name
        category.delete()
        messages.success(request, f"Category '{cat_name}' deleted successfully.")
    return redirect('dashboard:category_list')


# ==========================================
# BRANDS CRUD
# ==========================================
@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def brand_list(request):
    query = request.GET.get('q', '').strip()
    brands = Brand.objects.annotate(product_count=Count('products')).order_by('name')

    if query:
        brands = brands.filter(name__icontains=query)

    paginator = Paginator(brands, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/brands/list.html', {
        'page_obj': page_obj,
        'query': query,
        'active_menu': 'brands',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def brand_add(request):
    if request.method == 'POST':
        form = BrandForm(request.POST, request.FILES)
        if form.is_valid():
            brand = form.save()
            messages.success(request, f"Brand '{brand.name}' added successfully!")
            return redirect('dashboard:brand_list')
    else:
        form = BrandForm()

    return render(request, 'dashboard/brands/form.html', {
        'form': form,
        'title': 'Add New Brand',
        'active_menu': 'brands',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def brand_edit(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if request.method == 'POST':
        form = BrandForm(request.POST, request.FILES, instance=brand)
        if form.is_valid():
            form.save()
            messages.success(request, f"Brand '{brand.name}' updated successfully!")
            return redirect('dashboard:brand_list')
    else:
        form = BrandForm(instance=brand)

    return render(request, 'dashboard/brands/form.html', {
        'form': form,
        'brand': brand,
        'title': f"Edit Brand: {brand.name}",
        'active_menu': 'brands',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def brand_delete(request, pk):
    brand = get_object_or_404(Brand, pk=pk)
    if request.method == 'POST':
        b_name = brand.name
        brand.delete()
        messages.success(request, f"Brand '{b_name}' deleted.")
    return redirect('dashboard:brand_list')


# ==========================================
# PRODUCTS CRUD (DYNAMIC COLORS, IMAGES & VARIANTS)
# ==========================================
@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def product_list(request):
    query = request.GET.get('q', '').strip()
    category_id = request.GET.get('category')
    brand_id = request.GET.get('brand')
    status = request.GET.get('status')

    products = Product.objects.select_related('category', 'brand').prefetch_related(
        'colors__images', 'variants'
    ).order_by('-created_at')

    if query:
        products = products.filter(
            Q(name__icontains=query) | Q(sku__icontains=query) | Q(tags__icontains=query)
        )
    if category_id:
        products = products.filter(category_id=category_id)
    if brand_id:
        products = products.filter(brand_id=brand_id)
    if status == 'active':
        products = products.filter(is_active=True)
    elif status == 'inactive':
        products = products.filter(is_active=False)
    elif status == 'featured':
        products = products.filter(is_featured=True)

    paginator = Paginator(products, 12)
    page_obj = paginator.get_page(request.GET.get('page'))

    categories = Category.objects.filter(is_active=True).order_by('name')
    brands = Brand.objects.filter(is_active=True).order_by('name')

    return render(request, 'dashboard/products/list.html', {
        'page_obj': page_obj,
        'categories': categories,
        'brands': brands,
        'query': query,
        'selected_category': category_id,
        'selected_brand': brand_id,
        'selected_status': status,
        'active_menu': 'products',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def product_add(request):
    if request.method == 'POST':
        form = ProductBaseForm(request.POST)
        if form.is_valid():
            product = form.save()

            # 1. Save Specifications
            spec_keys = request.POST.getlist('spec_keys[]')
            spec_values = request.POST.getlist('spec_values[]')
            for order, (k, v) in enumerate(zip(spec_keys, spec_values)):
                k, v = k.strip(), v.strip()
                if k and v:
                    ProductSpecification.objects.create(
                        product=product, key=k, value=v, sort_order=order
                    )

            # 2. Save Colors & Respective Images & Size Variants
            color_count = int(request.POST.get('color_count', 0))
            for c_idx in range(color_count):
                c_name = request.POST.get(f'color_name_{c_idx}', '').strip()
                c_hex = request.POST.get(f'color_hex_{c_idx}', '#047857').strip()
                if not c_name:
                    continue

                color = ProductColor.objects.create(
                    product=product,
                    color_name=c_name,
                    color_hex=c_hex,
                    sort_order=c_idx,
                    is_active=True,
                )

                # Color Images upload
                uploaded_images = request.FILES.getlist(f'color_images_{c_idx}')
                primary_idx_str = request.POST.get(f'primary_image_{c_idx}', '0')
                try:
                    primary_idx = int(primary_idx_str)
                except ValueError:
                    primary_idx = 0

                for img_order, img_file in enumerate(uploaded_images):
                    is_prim = (img_order == primary_idx)
                    p_img = ProductImage(
                        product_color=color,
                        image=img_file,
                        alt_text=f"{product.name} - {color.color_name}",
                        is_primary=is_prim,
                        sort_order=img_order,
                    )
                    p_img.save()

                # Color Size Variants
                v_sizes = request.POST.getlist(f'variant_size_{c_idx}[]')
                v_skus = request.POST.getlist(f'variant_sku_{c_idx}[]')
                v_prices = request.POST.getlist(f'variant_price_{c_idx}[]')
                v_stocks = request.POST.getlist(f'variant_stock_{c_idx}[]')

                for s, sku_val, p_val, st_val in zip(v_sizes, v_skus, v_prices, v_stocks):
                    s = s.strip()
                    sku_val = sku_val.strip()
                    if not sku_val:
                        sku_val = f"{product.sku}-{color.id}-{s}".replace(' ', '-').upper()

                    price_override = Decimal(p_val) if p_val and p_val.strip() else None
                    stock_qty = int(st_val) if st_val and st_val.isdigit() else 0

                    ProductVariant.objects.create(
                        product=product,
                        product_color=color,
                        size=s,
                        sku=sku_val,
                        price=price_override,
                        stock_quantity=stock_qty,
                        is_active=True,
                    )

            messages.success(request, f"Product '{product.name}' created with all colors, images, and variants!")
            return redirect('dashboard:product_list')
    else:
        form = ProductBaseForm()

    categories = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
    brands = Brand.objects.filter(is_active=True).order_by('name')

    return render(request, 'dashboard/products/form.html', {
        'form': form,
        'categories': categories,
        'brands': brands,
        'title': 'Add New Multi-Color Product',
        'active_menu': 'products',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def product_edit(request, pk):
    product = get_object_or_404(
        Product.objects.prefetch_related('colors__images', 'colors__variants', 'specifications'),
        pk=pk
    )

    if request.method == 'POST':
        form = ProductBaseForm(request.POST, instance=product)
        if form.is_valid():
            product = form.save()

            # 1. Update Specifications
            product.specifications.all().delete()
            spec_keys = request.POST.getlist('spec_keys[]')
            spec_values = request.POST.getlist('spec_values[]')
            for order, (k, v) in enumerate(zip(spec_keys, spec_values)):
                k, v = k.strip(), v.strip()
                if k and v:
                    ProductSpecification.objects.create(
                        product=product, key=k, value=v, sort_order=order
                    )

            # 2. Delete selected images
            delete_img_ids = request.POST.getlist('delete_images[]')
            if delete_img_ids:
                ProductImage.objects.filter(id__in=delete_img_ids).delete()

            # 3. Update Existing Colors & Process New Colors
            color_count = int(request.POST.get('color_count', 0))
            for c_idx in range(color_count):
                color_id = request.POST.get(f'color_id_{c_idx}')
                c_name = request.POST.get(f'color_name_{c_idx}', '').strip()
                c_hex = request.POST.get(f'color_hex_{c_idx}', '#047857').strip()
                if not c_name:
                    continue

                if color_id:
                    color = ProductColor.objects.filter(pk=color_id, product=product).first()
                    if color:
                        color.color_name = c_name
                        color.color_hex = c_hex
                        color.sort_order = c_idx
                        color.save()
                else:
                    color = ProductColor.objects.create(
                        product=product,
                        color_name=c_name,
                        color_hex=c_hex,
                        sort_order=c_idx,
                        is_active=True,
                    )

                # Set primary existing image if radio selected
                existing_primary_id = request.POST.get(f'existing_primary_{color.id}')
                if existing_primary_id:
                    ProductImage.objects.filter(product_color=color).update(is_primary=False)
                    ProductImage.objects.filter(pk=existing_primary_id, product_color=color).update(is_primary=True)

                # Upload additional new images
                new_images = request.FILES.getlist(f'color_images_{c_idx}')
                for img_order, img_file in enumerate(new_images):
                    p_img = ProductImage(
                        product_color=color,
                        image=img_file,
                        alt_text=f"{product.name} - {color.color_name}",
                        is_primary=False,
                        sort_order=img_order + 10,
                    )
                    p_img.save()

                # Update or create variants for this color
                v_ids = request.POST.getlist(f'variant_id_{c_idx}[]')
                v_sizes = request.POST.getlist(f'variant_size_{c_idx}[]')
                v_skus = request.POST.getlist(f'variant_sku_{c_idx}[]')
                v_prices = request.POST.getlist(f'variant_price_{c_idx}[]')
                v_stocks = request.POST.getlist(f'variant_stock_{c_idx}[]')

                for idx in range(len(v_sizes)):
                    v_id = v_ids[idx] if idx < len(v_ids) else None
                    s = v_sizes[idx].strip()
                    sku_val = v_skus[idx].strip() if idx < len(v_skus) else ''
                    p_val = v_prices[idx] if idx < len(v_prices) else None
                    st_val = v_stocks[idx] if idx < len(v_stocks) else '0'

                    price_override = Decimal(p_val) if p_val and p_val.strip() else None
                    stock_qty = int(st_val) if st_val and st_val.isdigit() else 0

                    if v_id:
                        ProductVariant.objects.filter(pk=v_id, product=product).update(
                            size=s,
                            sku=sku_val,
                            price=price_override,
                            stock_quantity=stock_qty,
                        )
                    else:
                        if not sku_val:
                            sku_val = f"{product.sku}-{color.id}-{s}-{idx}".replace(' ', '-').upper()
                        ProductVariant.objects.create(
                            product=product,
                            product_color=color,
                            size=s,
                            sku=sku_val,
                            price=price_override,
                            stock_quantity=stock_qty,
                            is_active=True,
                        )

            # Handle variant deletions
            del_variant_ids = request.POST.getlist('delete_variants[]')
            if del_variant_ids:
                ProductVariant.objects.filter(id__in=del_variant_ids, product=product).delete()

            messages.success(request, f"Product '{product.name}' updated successfully!")
            return redirect('dashboard:product_list')
    else:
        form = ProductBaseForm(instance=product)

    categories = Category.objects.filter(is_active=True).order_by('sort_order', 'name')
    brands = Brand.objects.filter(is_active=True).order_by('name')

    return render(request, 'dashboard/products/form.html', {
        'form': form,
        'product': product,
        'categories': categories,
        'brands': brands,
        'title': f"Edit Product: {product.name}",
        'active_menu': 'products',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        p_name = product.name
        product.delete()
        messages.success(request, f"Product '{p_name}' deleted.")
    return redirect('dashboard:product_list')


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def product_bulk_action(request):
    if request.method == 'POST':
        action = request.POST.get('bulk_action')
        selected_ids = request.POST.getlist('selected_products[]')
        
        if not selected_ids:
            messages.warning(request, "No products selected for bulk operation.")
            return redirect('dashboard:product_list')

        queryset = Product.objects.filter(id__in=selected_ids)
        if action == 'activate':
            queryset.update(is_active=True)
            messages.success(request, f"Activated {queryset.count()} selected products.")
        elif action == 'deactivate':
            queryset.update(is_active=False)
            messages.success(request, f"Deactivated {queryset.count()} selected products.")
        elif action == 'feature':
            queryset.update(is_featured=True)
            messages.success(request, f"Marked {queryset.count()} products as featured.")
        elif action == 'delete':
            count = queryset.count()
            queryset.delete()
            messages.success(request, f"Deleted {count} products.")
            
    return redirect('dashboard:product_list')


# ==========================================
# ORDERS MANAGEMENT
# ==========================================
@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def order_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status')
    payment_filter = request.GET.get('payment_status')

    orders = Order.objects.select_related('user').prefetch_related('items').order_by('-created_at')

    if query:
        orders = orders.filter(
            Q(order_number__icontains=query) | Q(user__name__icontains=query) | Q(user__email__icontains=query)
        )
    if status_filter:
        orders = orders.filter(order_status=status_filter)
    if payment_filter:
        orders = orders.filter(payment_status=payment_filter)

    paginator = Paginator(orders, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/orders/list.html', {
        'page_obj': page_obj,
        'query': query,
        'selected_status': status_filter,
        'selected_payment': payment_filter,
        'status_choices': Order.ORDER_STATUS_CHOICES,
        'payment_choices': Order.PAYMENT_STATUS_CHOICES,
        'active_menu': 'orders',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def order_detail(request, pk):
    order = get_object_or_404(
        Order.objects.select_related('user').prefetch_related('items__variant', 'payments'),
        pk=pk
    )
    return render(request, 'dashboard/orders/detail.html', {
        'order': order,
        'status_choices': Order.ORDER_STATUS_CHOICES,
        'payment_choices': Order.PAYMENT_STATUS_CHOICES,
        'active_menu': 'orders',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def order_change_status(request, pk):
    order = get_object_or_404(Order, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('order_status')
        new_payment = request.POST.get('payment_status')
        shipping_partner = request.POST.get('shipping_partner', '').strip()
        tracking_number = request.POST.get('tracking_number', '').strip()

        if new_status in dict(Order.ORDER_STATUS_CHOICES):
            order.order_status = new_status
            if new_status == 'shipped' and not order.shipped_at:
                order.shipped_at = timezone.now()
            elif new_status == 'delivered' and not order.delivered_at:
                order.delivered_at = timezone.now()

        if new_payment in dict(Order.PAYMENT_STATUS_CHOICES):
            order.payment_status = new_payment

        order.shipping_partner = shipping_partner
        order.tracking_number = tracking_number
        order.save()

        messages.success(request, f"Order #{order.order_number} status updated to {order.get_order_status_display()}!")
    return redirect('dashboard:order_detail', pk=pk)


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def order_invoice(request, pk):
    order = get_object_or_404(
        Order.objects.select_related('user').prefetch_related('items'),
        pk=pk
    )
    return render(request, 'dashboard/orders/invoice.html', {'order': order})


# ==========================================
# USERS / CUSTOMERS MANAGEMENT
# ==========================================
@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def user_list(request):
    query = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status')

    users = User.objects.annotate(order_count=Count('orders')).order_by('-date_joined')

    if query:
        users = users.filter(
            Q(name__icontains=query) | Q(email__icontains=query) | Q(phone__icontains=query)
        )
    if status_filter == 'active':
        users = users.filter(is_active=True)
    elif status_filter == 'inactive':
        users = users.filter(is_active=False)
    elif status_filter == 'staff':
        users = users.filter(is_staff=True)

    paginator = Paginator(users, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/users/list.html', {
        'page_obj': page_obj,
        'query': query,
        'selected_status': status_filter,
        'active_menu': 'users',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def user_detail(request, pk):
    customer = get_object_or_404(User.objects.prefetch_related('addresses', 'orders'), pk=pk)
    total_spent = customer.orders.filter(payment_status='completed').aggregate(sum=Sum('total'))['sum'] or 0

    return render(request, 'dashboard/users/detail.html', {
        'customer': customer,
        'total_spent': total_spent,
        'active_menu': 'users',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def user_toggle_status(request, pk):
    customer = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        customer.is_active = not customer.is_active
        customer.save()
        status_label = "activated" if customer.is_active else "deactivated"
        messages.success(request, f"User {customer.email} has been {status_label}.")
    return redirect('dashboard:user_list')


# ==========================================
# REVIEWS MANAGEMENT
# ==========================================
@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def review_list(request):
    status_filter = request.GET.get('status')
    reviews = Review.objects.select_related('user', 'product').order_by('-created_at')

    if status_filter == 'pending':
        reviews = reviews.filter(is_approved=False)
    elif status_filter == 'approved':
        reviews = reviews.filter(is_approved=True)

    paginator = Paginator(reviews, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/reviews/list.html', {
        'page_obj': page_obj,
        'selected_status': status_filter,
        'active_menu': 'reviews',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def review_approve(request, pk):
    review = get_object_or_404(Review, pk=pk)
    review.is_approved = True
    review.save()
    messages.success(request, f"Review by {review.user.name} approved.")
    return redirect('dashboard:review_list')


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def review_delete(request, pk):
    review = get_object_or_404(Review, pk=pk)
    product = review.product
    review.delete()
    product.update_rating_stats()
    messages.success(request, "Review deleted.")
    return redirect('dashboard:review_list')


# ==========================================
# COUPONS CRUD
# ==========================================
@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def coupon_list(request):
    coupons = Coupon.objects.order_by('-created_at')
    paginator = Paginator(coupons, 15)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'dashboard/coupons/list.html', {
        'page_obj': page_obj,
        'active_menu': 'coupons',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def coupon_add(request):
    if request.method == 'POST':
        form = CouponForm(request.POST)
        if form.is_valid():
            coupon = form.save()
            messages.success(request, f"Coupon '{coupon.code}' created!")
            return redirect('dashboard:coupon_list')
    else:
        form = CouponForm()

    return render(request, 'dashboard/coupons/form.html', {
        'form': form,
        'title': 'Create Promotional Coupon',
        'active_menu': 'coupons',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def coupon_edit(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    if request.method == 'POST':
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            form.save()
            messages.success(request, f"Coupon '{coupon.code}' updated!")
            return redirect('dashboard:coupon_list')
    else:
        form = CouponForm(instance=coupon)

    return render(request, 'dashboard/coupons/form.html', {
        'form': form,
        'coupon': coupon,
        'title': f"Edit Coupon: {coupon.code}",
        'active_menu': 'coupons',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def coupon_delete(request, pk):
    coupon = get_object_or_404(Coupon, pk=pk)
    code = coupon.code
    coupon.delete()
    messages.success(request, f"Coupon '{code}' deleted.")
    return redirect('dashboard:coupon_list')


# ==========================================
# HOMEPAGE BANNERS CRUD
# ==========================================
@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def banner_list(request):
    banners = Banner.objects.order_by('sort_order', '-created_at')
    return render(request, 'dashboard/banners/list.html', {
        'banners': banners,
        'active_menu': 'banners',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def banner_add(request):
    if request.method == 'POST':
        form = BannerForm(request.POST, request.FILES)
        if form.is_valid():
            banner = form.save()
            messages.success(request, f"Banner '{banner.title}' added!")
            return redirect('dashboard:banner_list')
    else:
        form = BannerForm()

    return render(request, 'dashboard/banners/form.html', {
        'form': form,
        'title': 'Add Homepage Hero Banner',
        'active_menu': 'banners',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def banner_edit(request, pk):
    banner = get_object_or_404(Banner, pk=pk)
    if request.method == 'POST':
        form = BannerForm(request.POST, request.FILES, instance=banner)
        if form.is_valid():
            form.save()
            messages.success(request, f"Banner '{banner.title}' updated!")
            return redirect('dashboard:banner_list')
    else:
        form = BannerForm(instance=banner)

    return render(request, 'dashboard/banners/form.html', {
        'form': form,
        'banner': banner,
        'title': f"Edit Banner: {banner.title}",
        'active_menu': 'banners',
    })


@user_passes_test(is_staff_or_superuser, login_url='/avail-admin/login/')
def banner_delete(request, pk):
    banner = get_object_or_404(Banner, pk=pk)
    title = banner.title
    banner.delete()
    messages.success(request, f"Banner '{title}' deleted.")
    return redirect('dashboard:banner_list')
