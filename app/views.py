import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.http import JsonResponse, HttpResponse
from .models import Category, SubCategory, Product, Order, OrderItem, Profile, Wishlist, Cart, CartItem
from .services.invoice import generate_order_invoice_pdf



# ── HOME ──────────────────────────────────────────────────────────────────────
def home(request):
    if request.user.is_authenticated:
        return redirect('marketplace')
    categories = Category.objects.all()
    products = Product.objects.all().order_by('-id')[:6]
    return render(request, 'home.html', {'categories': categories, 'products': products})


# ── MARKETPLACE ───────────────────────────────────────────────────────────────
@login_required(login_url='login')
def marketplace(request):
    categories = Category.objects.prefetch_related('subcategories').all()
    selected_cat = request.GET.get('category', '')
    selected_sub = request.GET.get('sub', '')
    search_query = request.GET.get('q', '')
    sort_by = request.GET.get('sort', 'latest')

    products = Product.objects.select_related('category', 'subcategory').all()
    if selected_cat:
        products = products.filter(category__id=selected_cat)
    if selected_sub:
        products = products.filter(subcategory__id=selected_sub)
    if search_query:
        products = products.filter(name__icontains=search_query)

    sort_map = {'price_low': 'price', 'price_high': '-price',
                'rating': '-rating', 'latest': '-id'}
    if sort_by == 'sale':
        products = products.filter(is_sale=True).order_by('-id')
    else:
        products = products.order_by(sort_map.get(sort_by, '-id'))

    subcategories = []
    active_category = None
    if selected_cat:
        try:
            active_category = Category.objects.get(id=selected_cat)
            subcategories = SubCategory.objects.filter(
                category__id=selected_cat)
        except Category.DoesNotExist:
            pass

    wishlist_ids = set(Wishlist.objects.filter(
        user=request.user).values_list('product_id', flat=True))
    cart_ids = set()
    try:
        c = Cart.objects.get(user=request.user)
        cart_ids = set(c.items.values_list('product_id', flat=True))
    except Cart.DoesNotExist:
        pass

    return render(request, 'marketplace.html', {
        'categories': categories, 'subcategories': subcategories,
        'active_category': active_category, 'products': products,
        'selected_cat': selected_cat, 'selected_sub': selected_sub,
        'search_query': search_query, 'sort_by': sort_by,
        'total': products.count(), 'wishlist_ids': wishlist_ids, 'cart_ids': cart_ids,
        'sort_list': [
            ('latest', 'Latest Arrivals'), ('price_low', 'Price: Low → High'),
            ('price_high', 'Price: High → Low'), ('rating',
                                                  'Top Rated'), ('sale', 'On Sale'),
        ],
    })


# ── PRODUCT DETAIL ────────────────────────────────────────────────────────────
@login_required(login_url='login')
def product_detail(request, product_id):
    product = get_object_or_404(Product.objects.select_related(
        'category', 'subcategory'), id=product_id)
    related = Product.objects.filter(
        category=product.category).exclude(id=product.id)[:4]
    wishlist_ids = set(Wishlist.objects.filter(
        user=request.user).values_list('product_id', flat=True))
    cart_ids = set()
    try:
        c = Cart.objects.get(user=request.user)
        cart_ids = set(c.items.values_list('product_id', flat=True))
    except Cart.DoesNotExist:
        pass
    return render(request, 'product_detail.html', {
        'product': product, 'related': related,
        'wishlist_ids': wishlist_ids, 'cart_ids': cart_ids,
        'in_cart': product.id in cart_ids, 'in_wishlist': product.id in wishlist_ids,
    })


# ── CART PAGE ─────────────────────────────────────────────────────────────────
@login_required(login_url='login')
def cart(request):
    try:
        cart_obj = Cart.objects.get(user=request.user)
        items = cart_obj.items.select_related(
            'product',
            'product__category',
            'product__subcategory'
        ).all()
        total = float(cart_obj.get_total())
        count = cart_obj.get_count()
    except Cart.DoesNotExist:
        cart_obj = None
        items = []
        total = 0.0
        count = 0

    delivery = 49 if total > 0 else 0
    grand_total = total + delivery
    return render(request, 'cart.html', {
        'cart':        cart_obj,
        'items':       items,
        'total':       total,
        'count':       count,
        'delivery':    delivery,
        'grand_total': grand_total,
    })


# ── ADD TO CART (AJAX) ────────────────────────────────────────────────────────
@login_required(login_url='login')
def add_to_cart(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    product = get_object_or_404(Product, id=product_id)
    cart_obj, _ = Cart.objects.get_or_create(user=request.user)
    item, created = CartItem.objects.get_or_create(
        cart=cart_obj, product=product)
    if not created:
        item.quantity += 1
        item.save()
    return JsonResponse({'added': True, 'quantity': item.quantity, 'count': cart_obj.get_count()})


# ── UPDATE CART (AJAX) ────────────────────────────────────────────────────────
@login_required(login_url='login')
def update_cart(request, item_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    action = request.POST.get('action')
    if action == 'increase':
        item.quantity += 1
        item.save()
    elif action == 'decrease':
        if item.quantity > 1:
            item.quantity -= 1
            item.save()
        else:
            cart_ref = item.cart
            item.delete()
            return JsonResponse({'removed': True, 'count': cart_ref.get_count(), 'cart_total': str(cart_ref.get_total())})
    return JsonResponse({'removed': False, 'quantity': item.quantity, 'subtotal': str(item.get_subtotal()), 'count': item.cart.get_count(), 'cart_total': str(item.cart.get_total())})


# ── REMOVE FROM CART (AJAX) ───────────────────────────────────────────────────
@login_required(login_url='login')
def remove_from_cart(request, item_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    item = get_object_or_404(CartItem, id=item_id, cart__user=request.user)
    cart_ref = item.cart
    item.delete()
    return JsonResponse({'removed': True, 'count': cart_ref.get_count(), 'cart_total': str(cart_ref.get_total())})


# ── CHECKOUT / PAYMENT DETAILS ────────────────────────────────────────────────
@login_required(login_url='login')
def checkout(request):
    try:
        cart_obj = Cart.objects.prefetch_related(
            'items__product').get(user=request.user)
        items = cart_obj.items.select_related('product').all()
        if not items.exists():
            return redirect('cart')
    except Cart.DoesNotExist:
        return redirect('cart')

    profile, _ = Profile.objects.get_or_create(user=request.user)
    total = cart_obj.get_total()
    delivery = 49
    grand_total = total + delivery

    return render(request, 'payment_details.html', {
        'cart':        cart_obj,
        'items':       items,
        'total':       total,
        'delivery':    delivery,
        'grand_total': grand_total,
        'profile':     profile,
    })


# ── PLACE ORDER ───────────────────────────────────────────────────────────────
@login_required(login_url='login')
@transaction.atomic
def place_order(request):
    if request.method != 'POST':
        return redirect('checkout')

    try:
        cart_obj = Cart.objects.prefetch_related(
            'items__product').get(user=request.user)
        if not cart_obj.items.exists():
            return redirect('cart')
    except Cart.DoesNotExist:
        return redirect('cart')

    payment_method = request.POST.get('payment_method', 'cod')
    full_name = request.POST.get('full_name', '').strip()
    phone = request.POST.get('phone', '').strip()
    address = request.POST.get('address', '').strip()
    city = request.POST.get('city', '').strip()
    state = request.POST.get('state', '').strip()
    pincode = request.POST.get('pincode', '').strip()

    if not all([full_name, phone, address, city, state, pincode]):
        messages.error(request, 'Please fill in all delivery details.')
        return redirect('checkout')

    total = cart_obj.get_total()
    delivery = 49
    grand_total = total + delivery

    # Create order
    order = Order.objects.create(
        user=request.user,
        status='confirmed' if payment_method != 'cod' else 'pending',
        payment_method=payment_method,
        payment_status='paid' if payment_method != 'cod' else 'pending',
        total=total,
        delivery_charge=delivery,
        grand_total=grand_total,
        full_name=full_name,
        phone=phone,
        address=address,
        city=city,
        state=state,
        pincode=pincode,
        estimated_delivery=datetime.date.today() + datetime.timedelta(days=5),
    )

    # Copy cart items to order items
    for cart_item in cart_obj.items.select_related('product').all():
        OrderItem.objects.create(
            order=order,
            product=cart_item.product,
            name=cart_item.product.name,
            quantity=cart_item.quantity,
            price=cart_item.product.price,
        )

    # Clear cart
    cart_obj.items.all().delete()

    return redirect('order_success', order_id=order.id)


# ── ORDER PDF DOWNLOAD ────────────────────────────────────────────────────────
@login_required(login_url='login')
def order_pdf(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product__category'),
        id=order_id, user=request.user
    )
    pdf_bytes = generate_order_invoice_pdf(order)
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="MyShop_Invoice_Order_{order.id}.pdf"'
    return response



@login_required(login_url='login')
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order_success.html', {'order': order})


# ── MY ORDERS ─────────────────────────────────────────────────────────────────
@login_required(login_url='login')
def orders(request):
    order_list = Order.objects.filter(
        user=request.user).prefetch_related('items')
    return render(request, 'orders.html', {'orders': order_list})


# ── ORDER DETAIL ──────────────────────────────────────────────────────────────
@login_required(login_url='login')
def order_detail(request, order_id):
    order = get_object_or_404(Order.objects.prefetch_related(
        'items__product'), id=order_id, user=request.user)
    steps = order.get_status_steps()
    return render(request, 'order_detail.html', {'order': order, 'steps': steps})


# ── TOGGLE WISHLIST (AJAX) ────────────────────────────────────────────────────
@login_required(login_url='login')
def toggle_wishlist(request, product_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)
    product = get_object_or_404(Product, id=product_id)
    obj, created = Wishlist.objects.get_or_create(
        user=request.user, product=product)
    if not created:
        obj.delete()
        wishlisted = False
    else:
        wishlisted = True
    return JsonResponse({'wishlisted': wishlisted, 'count': Wishlist.objects.filter(user=request.user).count()})


# ── WISHLIST PAGE ─────────────────────────────────────────────────────────────
@login_required(login_url='login')
def wishlist(request):
    items = Wishlist.objects.filter(user=request.user).select_related(
        'product__category', 'product__subcategory')
    wishlist_ids = set(items.values_list('product_id', flat=True))
    cart_ids = set()
    try:
        c = Cart.objects.get(user=request.user)
        cart_ids = set(c.items.values_list('product_id', flat=True))
    except Cart.DoesNotExist:
        pass
    return render(request, 'wishlist.html', {'items': items, 'wishlist_ids': wishlist_ids, 'cart_ids': cart_ids, 'total': items.count()})


# ── LOGIN ─────────────────────────────────────────────────────────────────────
def login(request):
    if request.user.is_authenticated:
        return redirect('marketplace')
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user:
            auth_login(request, user)
            return redirect('marketplace')
        else:
            return render(request, 'login.html', {'error': 'Invalid username or password.'})
    return render(request, 'login.html')


# ── SIGNUP ────────────────────────────────────────────────────────────────────
def signup(request):
    if request.user.is_authenticated:
        return redirect('marketplace')
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        if password1 != password2:
            return render(request, 'signup.html', {'error': 'Passwords do not match.'})
        if User.objects.filter(username=username).exists():
            return render(request, 'signup.html', {'error': 'Username already taken.'})
        if User.objects.filter(email=email).exists():
            return render(request, 'signup.html', {'error': 'Email already registered.'})
        user = User.objects.create_user(
            username=username, email=email, password=password1, first_name=first_name, last_name=last_name)
        Profile.objects.create(user=user)
        auth_login(request, user)
        return redirect('marketplace')
    return render(request, 'signup.html')


# ── LOGOUT ────────────────────────────────────────────────────────────────────
def logout(request):
    auth_logout(request)
    return redirect('home')


# ── PROFILE ───────────────────────────────────────────────────────────────────
@login_required(login_url='login')
def profile(request):
    profile_obj, _ = Profile.objects.get_or_create(user=request.user)
    order_list = Order.objects.filter(
        user=request.user).prefetch_related('items')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'update_info':
            request.user.first_name = request.POST.get(
                'first_name', '').strip()
            request.user.last_name = request.POST.get('last_name', '').strip()
            request.user.email = request.POST.get('email', '').strip()
            request.user.save()
            profile_obj.phone = request.POST.get('phone', '').strip()
            profile_obj.address = request.POST.get('address', '').strip()
            profile_obj.city = request.POST.get('city', '').strip()
            profile_obj.state = request.POST.get('state', '').strip()
            if 'avatar' in request.FILES:
                profile_obj.avatar = request.FILES['avatar']
            profile_obj.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('profile')
        elif action == 'change_password':
            current = request.POST.get('current_password', '')
            new_pw = request.POST.get('new_password', '')
            confirm = request.POST.get('confirm_password', '')
            if not request.user.check_password(current):
                messages.error(request, 'Current password is incorrect.')
            elif new_pw != confirm:
                messages.error(request, 'New passwords do not match.')
            elif len(new_pw) < 8:
                messages.error(
                    request, 'Password must be at least 8 characters.')
            else:
                request.user.set_password(new_pw)
                request.user.save()
                auth_login(request, request.user)
                messages.success(request, 'Password changed successfully.')
            return redirect('profile')
    return render(request, 'profile.html', {'profile': profile_obj, 'orders': order_list})


# ── ABOUT ─────────────────────────────────────────────────────────────────────
def about(request):
    return render(request, 'about.html')
