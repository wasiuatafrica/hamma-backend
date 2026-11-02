from django.test import TestCase
from accounts import models as acc_models, serializers as acc_serializers, tests as acc_tests
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model


class TestAdminManageUserEmailSearch(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            email="admin@example.com",
            password="password123",
            is_staff=True,
        )
        user_model.objects.create_user(
            email="nexxyb@gmail.com",
            firstname="Wasiu",
            lastname="A",
        )
        self.client.force_authenticate(user=self.admin)

    def test_name_filter_matches_email_username(self):
        response = self.client.get(
            "/anyon/new/manage-users/",
            {"name": "nexxyb"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["email"], "nexxyb@gmail.com")


class TestManageUserEndPoint(acc_tests.AuthenticateUserForTesting):
    def setup(self):
        super.setup()
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
        
    def test_get_all_user_failed(self):
        self.url=reverse("manage-users")
        self.authenticate_user()
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_all_user_success(self):
        self.url=reverse("manage-users")
        self.authenticate_user()
        self.user.is_staff = True
        self.user.save()
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # def test_list_users(self):
    #     url = reverse('manage-users')
    #     response = self.client.get(url)
    #     self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_retrieve_user(self):
        self.authenticate_user()
        self.user.is_staff = True
        self.user.save()
        url = reverse('manage-users', kwargs={'user_id': self.user.id})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_update_user(self):
        self.authenticate_user()
        self.user.is_staff = True
        self.user.save()
        url = reverse('manage-users', kwargs={'user_id': self.user.id})
        data = {"is_active": False}
        response = self.client.put(url, data)
        self.assertFalse(self.user.is_active)
        # Reactivate the account for other tests
        self.user.is_active = True
        self.user.save()
        self.assertTrue(self.user.is_active)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_delete_user(self):
        self.authenticate_user()
        self.user.is_staff = True
        self.user.save()
        url = reverse('manage-users', kwargs={'user_id': self.user.id})
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)


    



