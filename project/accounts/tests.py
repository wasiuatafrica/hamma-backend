from django.test import TestCase
from Accounts import models
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken


class CustomUserTestCase(TestCase):
    def setUp(self):
        '''Setup a custom user for testing'''
        self.user = models.CustomUser.objects.create(
            email="nwafor@gmail.com",
            firstname="Ebube",
            lastname="David",
            is_active=True,
        )
        self.user.set_password('password123')
        self.user.save()
        self.access_token= RefreshToken.for_user(self.user).access_token

    def test_custom_user_creation(self):
        '''Test the custom user creation'''
        user= models.CustomUser.objects.get(id=self.user.id)
        self.assertEqual(user.email, "nwafor@gmail.com")
        self.assertEqual(user.twofa_type, "email")
        self.assertTrue(self.user.has_2fa)

    def test_custom_user_profile(self):
        # Test if a profile is being created for the user
        user_profile= models.Profile.objects.filter(user=self.user).exists()
        self.assertTrue(user_profile)

class TwoFactorTokenTestCase(CustomUserTestCase):
    def setUp(self):
        '''Setup a custom user and 2FA token for testing'''
        super().setUp()  # Call the setup method of the parent class
        self.token = models.TwoFactorToken.objects.create(user=self.user)

    def create_test_user_token(self):
        
        self.assertEqual(self.token.user.id, self.user.id)

    def test_custom_user_2fa_token(self):
        user_token= models.TwoFactorToken.objects.get(id=self.token.id)
        self.assertIsNotNone(user_token)
        self.assertEqual(len(user_token.token), 8)

class CustomUserAPITestEndpoint(CustomUserTestCase,APITestCase):
    def setUp(self):
        '''Setup a custom user and 2FA token for testing'''
        super().setUp()  # Call the setup method of the parent class

    def test_create_object_success(self):
        url=reverse('register')
        data=  {
            "email":"nwafor15@gmail.com",
            "password":"Nwafor6.com",
            "firstname":"Glory",
            "lastname":"Ebube"
    }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_create_object_failure(self):
        url=reverse('register')
        data=  {
            # "email":"nwafor15@gmail.com",
            "password":"Nwafor6.com",
            "firstname":"Glory",
            "lastname":"Ebube"
    }
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_resend_reg_token_200(self):
        url=reverse('register')
        data=  {
            "email":self.user.email
        }
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_resend_reg_token_400(self):
        url=reverse('register')
        data=  {
            "email":"Nwafor6.com"
        }
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

class TestVerifyTokenEndpoint(TwoFactorTokenTestCase,APITestCase):
    def setUp(self):
        '''Setup a custom user and 2FA token for testing'''
        super().setUp()  # Call the setup method of the parent class

    def verify_token_success(self):
        url=reverse('verify_token')
        data=  {
            "user_email":self.user.email,
            "token":self.token.token
        }
        response = self.client.put(url, data)
        self.assertIsSuccessful(response)

    def verify_token_failed(self):
        url=reverse('verify_token')
        data=  {
            "user_email":self.user.email,
            "token":1234
        }
        response = self.client.put(url, data)
        self.assertEqual(response.status_code, status=status.HTTP_400_BAD_REQUEST)

class AuthenticateUserForTesting(CustomUserTestCase, APITestCase):

    '''
        This creates a user from  the and authenticate the users using the jwt.
        so we can use this class for other authenticated routes/enpoints.
    
    '''
    def setUp(self):
        super().setUp()  # Call the setup method of the parent class

    def authenticate_user(self):
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.access_token}')

class TestProfileView(AuthenticateUserForTesting):
    
    def setUp(self):
        super().setUp()  # Call the setup method of the parent class
        self.url = reverse('profile')
        self.data = {
                    "address":"Abujeeee",
                    "paypal_address":"sdf",
                    "phone":"!23456789",
                    "bank_name":"fcmb",
                    "account_number":"2345678"
                }
    def test_get_profile_authenticated(self):
        self.authenticate_user()  # Ensure user is authenticated
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)
        self.assertIn('user', response.data)
        # Add more assertions based on your expected response

    def test_update_profile_authenticated(self):
        self.authenticate_user()  # Ensure user is authenticated
        response = self.client.put(self.url, self.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('detail', response.data)
        self.assertIn('user', response.data)
        # Add more assertions based on your expected response

class TestSetOrOff2FAEndPoint(AuthenticateUserForTesting):
    def setUp(self):
        super().setUp()  # Call the setup method of the parent class
        self.url = reverse('2fa_on_off')
        self.data={
            "action":"sms"
        }
    
    def test_set_2fa(self):
        self.authenticate_user()
        response=self.client.post(self.url, self.data)
        self.assertIn('detail', response.data)
        print(response.content)

class TestLoginWithEmailViewEndPoint(CustomUserTestCase):
    def setUp(self):
        super().setUp()  # Call the setup method of the parent class
        self.url = reverse('login')
        self.data={
            "email":self.user.email,
            "password":"password123"
        }
        response=self.client.post(self.url, self.data)
        self.assertIn('detail', response.data)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

class TestDashBoardUpdatePassword(AuthenticateUserForTesting):

    def setUp(self):
        super().setUp()  # Call the setup method of the parent class
        self.url = reverse('update-password-dashboard')
        self.data={
            "current_password":'password123',
            "new_password1":"12345",
            "new_password2":"12345"
        }
        

    def test_change_password_success(self):
        self.authenticate_user()
        response=self.client.post(self.url, self.data)
        self.assertIn('detail', response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_change_password_failure(self):
        _data={
        "current_password":'password123',
        "new_password1":"12344",
        "new_password2":"12345"
    }
        self.authenticate_user()
        response=self.client.post(self.url, _data)
        self.assertIn('detail', response.data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

