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


class TestAdminManageUserExport(APITestCase):
    def setUp(self):
        user_model = get_user_model()
        self.admin = user_model.objects.create_user(
            email="admin@example.com",
            password="password123",
            is_staff=True,
        )
        for i in range(14):
            user_model.objects.create_user(
                email=f"export{i}@example.com",
                password="password123",
                firstname="Export",
                lastname=str(i),
                is_active=i % 2 == 0,
            )

    def test_export_returns_all_users_unpaginated(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/anyon/new/manage-users/", {"export": "true"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(len(response.data), 15)

    def test_export_respects_filters(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get(
            "/anyon/new/manage-users/",
            {"export": "true", "is_active": "false", "name": "export"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 7)
        self.assertTrue(all(not u["is_active"] for u in response.data))

    def test_export_requires_admin(self):
        user = get_user_model().objects.get(email="export0@example.com")
        self.client.force_authenticate(user=user)
        response = self.client.get("/anyon/new/manage-users/", {"export": "true"})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_without_export_flag_still_paginated(self):
        self.client.force_authenticate(user=self.admin)
        response = self.client.get("/anyon/new/manage-users/")

        self.assertEqual(response.data["count"], 15)
        self.assertEqual(len(response.data["results"]), 10)


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


    



