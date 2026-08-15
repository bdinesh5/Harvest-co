from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from app.models import (
    Category, SubCategory, Product, Cart, CartItem,
    Wishlist, Order, OrderItem, Profile
)
from app.context_processors import wishlist_count, cart_count
from app.services.invoice import generate_order_invoice_pdf



class ModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='password123', email='tester@example.com')
        self.category = Category.objects.create(name='Clothing', description='Apparel')
        self.subcategory = SubCategory.objects.create(category=self.category, name='Shirts')
        self.product = Product.objects.create(
            category=self.category,
            subcategory=self.subcategory,
            name='Linen Shirt',
            price=Decimal('1299.00'),
            rating=4.5,
            is_sale=True,
            is_limited=False
        )

    def test_model_string_representations(self):
        self.assertEqual(str(self.category), 'Clothing')
        self.assertEqual(str(self.subcategory), 'Clothing → Shirts')
        self.assertEqual(str(self.product), 'Linen Shirt')

        profile, _ = Profile.objects.get_or_create(user=self.user)
        self.assertEqual(str(profile), "tester's profile")

        cart, _ = Cart.objects.get_or_create(user=self.user)
        self.assertEqual(str(cart), "tester's cart")

        item = CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        self.assertEqual(str(item), "2 × Linen Shirt")
        self.assertEqual(item.get_subtotal(), Decimal('2598.00'))

        wishlist = Wishlist.objects.create(user=self.user, product=self.product)
        self.assertEqual(str(wishlist), "tester ♡ Linen Shirt")

    def test_cart_aggregations_and_empty_state(self):
        cart, _ = Cart.objects.get_or_create(user=self.user)
        self.assertEqual(cart.get_count(), 0)
        self.assertEqual(cart.get_total(), 0)

        item = CartItem.objects.create(cart=cart, product=self.product, quantity=3)
        self.assertEqual(cart.get_count(), 3)
        self.assertEqual(cart.get_total(), Decimal('3897.00'))

    def test_order_status_steps(self):
        order = Order.objects.create(
            user=self.user,
            total=Decimal('1299.00'),
            delivery_charge=Decimal('49.00'),
            grand_total=Decimal('1348.00'),
            status='confirmed',
            payment_method='card',
            payment_status='paid'
        )
        steps = order.get_status_steps()
        self.assertEqual(len(steps), 5)
        # 'confirmed' is the 2nd step (idx 1): step 0 is completed, step 1 is active
        self.assertTrue(steps[0]['completed'])
        self.assertFalse(steps[0]['active'])
        self.assertTrue(steps[1]['active'])
        self.assertFalse(steps[1]['completed'])


class ContextProcessorTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='tester', password='password123')
        self.category = Category.objects.create(name='Decor')
        self.product = Product.objects.create(category=self.category, name='Vase', price=Decimal('499.00'))

    def test_unauthenticated_context_processor(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.context.get('cart_count'), 0)
        self.assertEqual(response.context.get('wishlist_count'), 0)

    def test_authenticated_context_processor(self):
        self.client.login(username='tester', password='password123')
        cart, _ = Cart.objects.get_or_create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)
        Wishlist.objects.create(user=self.user, product=self.product)

        response = self.client.get(reverse('marketplace'))
        self.assertEqual(response.context.get('cart_count'), 2)
        self.assertEqual(response.context.get('wishlist_count'), 1)


class CartAndWishlistViewsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='shopper', password='password123')
        self.client.login(username='shopper', password='password123')
        self.category = Category.objects.create(name='Ceramics')
        self.product = Product.objects.create(category=self.category, name='Mug', price=Decimal('300.00'))

    def test_add_to_cart_ajax(self):
        # GET should be rejected (405)
        res_get = self.client.get(reverse('add_to_cart', args=[self.product.id]))
        self.assertEqual(res_get.status_code, 405)

        # POST should add product
        res_post = self.client.post(reverse('add_to_cart', args=[self.product.id]))
        self.assertEqual(res_post.status_code, 200)
        data = res_post.json()
        self.assertTrue(data['added'])
        self.assertEqual(data['quantity'], 1)
        self.assertEqual(data['count'], 1)

        # Second POST increments quantity
        res_post2 = self.client.post(reverse('add_to_cart', args=[self.product.id]))
        self.assertEqual(res_post2.json()['quantity'], 2)

    def test_update_and_remove_cart_ajax(self):
        cart, _ = Cart.objects.get_or_create(user=self.user)
        item = CartItem.objects.create(cart=cart, product=self.product, quantity=2)

        # Increase
        res_inc = self.client.post(reverse('update_cart', args=[item.id]), {'action': 'increase'})
        self.assertEqual(res_inc.status_code, 200)
        self.assertEqual(res_inc.json()['quantity'], 3)

        # Decrease
        res_dec = self.client.post(reverse('update_cart', args=[item.id]), {'action': 'decrease'})
        self.assertEqual(res_dec.json()['quantity'], 2)

        # Remove
        res_rem = self.client.post(reverse('remove_from_cart', args=[item.id]))
        self.assertEqual(res_rem.status_code, 200)
        self.assertTrue(res_rem.json()['removed'])
        self.assertEqual(res_rem.json()['count'], 0)

    def test_toggle_wishlist_ajax(self):
        # Toggle on
        res_on = self.client.post(reverse('toggle_wishlist', args=[self.product.id]))
        self.assertEqual(res_on.status_code, 200)
        self.assertTrue(res_on.json()['wishlisted'])
        self.assertEqual(res_on.json()['count'], 1)

        # Toggle off
        res_off = self.client.post(reverse('toggle_wishlist', args=[self.product.id]))
        self.assertEqual(res_off.status_code, 200)
        self.assertFalse(res_off.json()['wishlisted'])
        self.assertEqual(res_off.json()['count'], 0)


class OrderAndCheckoutTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='buyer', password='password123')
        self.client.login(username='buyer', password='password123')
        self.category = Category.objects.create(name='Leather')
        self.product = Product.objects.create(category=self.category, name='Wallet', price=Decimal('899.00'))

    def test_checkout_redirects_when_cart_empty(self):
        response = self.client.get(reverse('checkout'))
        self.assertRedirects(response, reverse('cart'))

    def test_place_order_flow_and_pdf_generation(self):
        # Put item in cart
        cart, _ = Cart.objects.get_or_create(user=self.user)
        CartItem.objects.create(cart=cart, product=self.product, quantity=2)

        # Checkout page loads
        res_checkout = self.client.get(reverse('checkout'))
        self.assertEqual(res_checkout.status_code, 200)

        # Place Order
        order_data = {
            'payment_method': 'upi',
            'full_name': 'Buyer John',
            'phone': '9876543210',
            'address': '123 Main St',
            'city': 'Chennai',
            'state': 'Tamil Nadu',
            'pincode': '600001',
        }
        res_place = self.client.post(reverse('place_order'), order_data)
        order = Order.objects.filter(user=self.user).first()
        self.assertIsNotNone(order)
        self.assertRedirects(res_place, reverse('order_success', args=[order.id]))

        # Check cart is cleared
        self.assertEqual(cart.items.count(), 0)

        # Check order items
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().name, 'Wallet')
        self.assertEqual(order.total, Decimal('1798.00'))
        self.assertEqual(order.grand_total, Decimal('1847.00'))
        self.assertEqual(order.payment_status, 'paid')

        # Test PDF Invoice endpoint
        res_pdf = self.client.get(reverse('order_pdf', args=[order.id]))
        self.assertEqual(res_pdf.status_code, 200)
        self.assertEqual(res_pdf['Content-Type'], 'application/pdf')
        self.assertTrue(res_pdf.content.startswith(b'%PDF'))
        self.assertIn(f'MyShop_Invoice_Order_{order.id}.pdf', res_pdf['Content-Disposition'])

        # Test direct service function
        pdf_bytes = generate_order_invoice_pdf(order)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b'%PDF'))


class AuthAndNavigationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='user1', password='pass12345Password!', email='user1@example.com',
            first_name='John', last_name='Doe'
        )
        self.category = Category.objects.create(name='Electronics')
        self.subcategory = SubCategory.objects.create(category=self.category, name='Audio')
        self.product = Product.objects.create(
            category=self.category, subcategory=self.subcategory,
            name='Headphones', price=Decimal('2499.00'), rating=4.8, is_sale=True
        )

    def test_public_pages(self):
        res_about = self.client.get(reverse('about'))
        self.assertEqual(res_about.status_code, 200)

        res_home = self.client.get(reverse('home'))
        self.assertEqual(res_home.status_code, 200)

    def test_login_and_logout(self):
        # Invalid login
        res_fail = self.client.post(reverse('login'), {'username': 'user1', 'password': 'wrongpassword'})
        self.assertEqual(res_fail.status_code, 200)
        self.assertContains(res_fail, 'Invalid username or password')

        # Valid login
        res_login = self.client.post(reverse('login'), {'username': 'user1', 'password': 'pass12345Password!'})
        self.assertRedirects(res_login, reverse('marketplace'))

        # Logout
        res_logout = self.client.get(reverse('logout'))
        self.assertRedirects(res_logout, reverse('home'))

    def test_signup(self):
        signup_data = {
            'username': 'newuser',
            'email': 'newuser@example.com',
            'first_name': 'New',
            'last_name': 'User',
            'password1': 'secret123Pass!',
            'password2': 'secret123Pass!',
        }
        res_signup = self.client.post(reverse('signup'), signup_data)
        self.assertRedirects(res_signup, reverse('marketplace'))
        self.assertTrue(User.objects.filter(username='newuser').exists())

    def test_marketplace_filtering_and_search(self):
        self.client.login(username='user1', password='pass12345Password!')

        # Filter by category
        res_cat = self.client.get(reverse('marketplace') + f'?category={self.category.id}')
        self.assertEqual(res_cat.status_code, 200)
        self.assertContains(res_cat, 'Headphones')

        # Filter by search
        res_search = self.client.get(reverse('marketplace') + '?q=Headphones')
        self.assertEqual(res_search.status_code, 200)
        self.assertContains(res_search, 'Headphones')

        # Sort by price_low
        res_sort = self.client.get(reverse('marketplace') + '?sort=price_low')
        self.assertEqual(res_sort.status_code, 200)

    def test_product_detail_view(self):
        self.client.login(username='user1', password='pass12345Password!')
        res_pd = self.client.get(reverse('product_detail', args=[self.product.id]))
        self.assertEqual(res_pd.status_code, 200)
        self.assertContains(res_pd, 'Headphones')

    def test_profile_update(self):
        self.client.login(username='user1', password='pass12345Password!')
        update_data = {
            'action': 'update_info',
            'first_name': 'Johnny',
            'last_name': 'Doe',
            'email': 'johnny@example.com',
            'phone': '9123456780',
            'address': '456 New Road',
            'city': 'Madurai',
            'state': 'Tamil Nadu',
        }
        res_update = self.client.post(reverse('profile'), update_data)
        self.assertRedirects(res_update, reverse('profile'))
        self.user.refresh_from_db()
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Johnny')
        self.assertEqual(self.user.profile.city, 'Madurai')


