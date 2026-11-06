from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.contrib.auth.tokens import default_token_generator

User = get_user_model()


class AuthenticationAndLayoutTests(TestCase):
    def setUp(self):
        self.client = Client()
        # Normal customer
        self.customer = User.objects.create_user(
            email='testuser@example.com',
            name='Test Customer',
            password='Password@123',
            phone='+91 9988776655'
        )
        # Staff administrator
        self.admin_user = User.objects.create_superuser(
            email='adminuser@availsmart.com',
            name='Admin User',
            password='AdminPassword@123'
        )

    def test_homepage_renders(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'AvailSmart')
        self.assertContains(response, 'Sign In')

    def test_user_registration(self):
        response = self.client.post(reverse('accounts:register'), {
            'name': 'New Registered User',
            'email': 'newuser@example.com',
            'phone': '+91 9123456780',
            'password': 'SecurePassword@123',
            'confirm_password': 'SecurePassword@123',
            'terms': True
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())

    def test_user_login_success(self):
        response = self.client.post(reverse('accounts:login'), {
            'email': 'testuser@example.com',
            'password': 'Password@123',
            'remember_me': True
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Welcome back')

    def test_user_login_failure(self):
        response = self.client.post(reverse('accounts:login'), {
            'email': 'testuser@example.com',
            'password': 'WrongPassword!',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid email address or password')

    def test_user_logout(self):
        self.client.login(email='testuser@example.com', password='Password@123')
        response = self.client.get(reverse('accounts:logout'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'logged out')

    def test_forgot_password_and_reset(self):
        # 1. Request reset
        response = self.client.post(reverse('accounts:forgot_password'), {
            'email': 'testuser@example.com'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Instructions Dispatched')

        # 2. Reset password using generated token
        token = default_token_generator.make_token(self.customer)
        uidb64 = urlsafe_base64_encode(force_bytes(self.customer.pk))
        reset_url = reverse('accounts:reset_password', kwargs={'uidb64': uidb64, 'token': token})

        # Get reset page
        get_response = self.client.get(reset_url)
        self.assertEqual(get_response.status_code, 200)

        # Post new password
        post_response = self.client.post(reset_url, {
            'new_password': 'BrandNewPassword@123',
            'confirm_password': 'BrandNewPassword@123'
        }, follow=True)
        self.assertEqual(post_response.status_code, 200)

        # Verify login with new password
        login_response = self.client.post(reverse('accounts:login'), {
            'email': 'testuser@example.com',
            'password': 'BrandNewPassword@123'
        }, follow=True)
        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, 'Welcome back')

    def test_custom_admin_access_control(self):
        # 1. Unauthenticated request to /avail-admin/ redirects to /avail-admin/login/
        response = self.client.get('/avail-admin/')
        self.assertRedirects(response, '/avail-admin/login/?next=/avail-admin/')

        # 2. Customer user attempting admin login is rejected
        non_staff_login = self.client.post('/avail-admin/login/', {
            'email': 'testuser@example.com',
            'password': 'Password@123'
        })
        self.assertEqual(non_staff_login.status_code, 200)
        self.assertContains(non_staff_login, 'Access Denied')

        # 3. Staff user successfully logs in and views /avail-admin/
        admin_login = self.client.post('/avail-admin/login/', {
            'email': 'adminuser@availsmart.com',
            'password': 'AdminPassword@123'
        }, follow=True)
        self.assertEqual(admin_login.status_code, 200)
        self.assertContains(admin_login, 'Staff Control')
        self.assertContains(admin_login, 'Operations Overview')

    def test_profile_update(self):
        """Customer updates their full name and phone number."""
        self.client.login(email='testuser@example.com', password='Password@123')
        res = self.client.post(reverse('accounts:profile'), {
            'action': 'update_profile',
            'name': 'Updated Customer Name',
            'phone': '+91 9876543210'
        }, follow=True)
        self.assertEqual(res.status_code, 200)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.name, 'Updated Customer Name')

    def test_address_management(self):
        """Customer can add, edit, set default, and delete an address."""
        from accounts.models import Address
        self.client.login(email='testuser@example.com', password='Password@123')

        # Add
        res_add = self.client.post(reverse('accounts:address_add'), {
            'full_name': 'Test Delivery',
            'phone': '9988776655',
            'address_line1': '123 Emerald Street',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'pincode': '400001',
            'country': 'India',
            'address_type': 'home',
            'is_default': True
        }, follow=True)
        self.assertEqual(res_add.status_code, 200)
        addr = Address.objects.filter(user=self.customer).first()
        self.assertIsNotNone(addr)
        self.assertEqual(addr.city, 'Mumbai')
        self.assertTrue(addr.is_default)

        # Edit
        res_edit = self.client.post(reverse('accounts:address_edit', kwargs={'address_id': addr.id}), {
            'full_name': 'Test Delivery Updated',
            'phone': '9988776655',
            'address_line1': '123 Emerald Street Suite 4',
            'city': 'Mumbai',
            'state': 'Maharashtra',
            'pincode': '400001',
            'country': 'India',
            'address_type': 'work',
        }, follow=True)
        self.assertEqual(res_edit.status_code, 200)
        addr.refresh_from_db()
        self.assertEqual(addr.address_line1, '123 Emerald Street Suite 4')

        # Delete
        res_del = self.client.get(reverse('accounts:address_delete', kwargs={'address_id': addr.id}), follow=True)
        self.assertEqual(res_del.status_code, 200)
        self.assertFalse(Address.objects.filter(id=addr.id).exists())
