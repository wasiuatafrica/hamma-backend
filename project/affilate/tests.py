from django.test import TestCase
from accounts import models as acc_models, serializers as acc_serializers, tests as acc_tests
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model


class TestAffilateProgram(acc_tests.AuthenticateUserForTesting):
    def setup(self):
        super.setup()
        print("hello")
        self.users = [
            get_user_model().objects.create_user(
                email="user1@example.com",
                password="password1",
                firstname="Prince",
                lastname="Jude"
            ),
            get_user_model().objects.create_user(
                email="user2@example.com",
                password="password2",
                firstname="David",
                lastname="Joe"
            ),
            # Add more users as needed
        ]
        
    def get_unique_url(self):
        self.url=reverse("my_referal_link")
        self.authenticate_user()
        response = self.client.get(self.url)
        print(response.data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # def test_get_all_user_success(self):
    #     self.url=reverse("manage-users")
    #     self.authenticate_user()
    #     self.user.is_staff = True
    #     self.user.save()
    #     response = self.client.get(self.url)

    #     self.assertEqual(response.status_code, status.HTTP_200_OK)
    #     print(response.data)





    



