import json

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User


class CustomerDeletionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            phone_number="9876543210",
            password="StrongPassword1!",
            role=User.Role.ADMIN,
            is_staff=True,
            is_email_verified=True,
        )
        self.customer = User.objects.create_user(
            email="customer@example.com",
            phone_number="9876543211",
            password="StrongPassword1!",
            role=User.Role.USER,
            is_email_verified=True,
        )
        self.client.force_login(self.admin)

    def test_admin_delete_permanently_removes_customer_without_history(self):
        response = self.client.post(
            reverse("admin-user-action", args=[self.customer.id]),
            data=json.dumps({"action": "delete"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(pk=self.customer.id).exists())
        self.assertEqual(response.json()["message"], "Customer account permanently deleted.")

