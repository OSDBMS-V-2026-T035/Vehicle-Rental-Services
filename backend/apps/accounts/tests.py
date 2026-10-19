from datetime import timedelta
import json
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from .models import ShopkeeperProfile, User
from .views import _booking_redirect


class BookingRedirectTests(SimpleTestCase):
    def test_preserves_a_valid_local_checkout_handoff(self):
        pickup = timezone.localdate() + timedelta(days=1)
        return_date = pickup + timedelta(days=2)
        result = _booking_redirect(
            f"/user-portal/?vehicle_id=42&pickup_date={pickup}&return_date={return_date}&ignored=value"
        )
        self.assertEqual(
            result,
            f"/user-portal/?vehicle_id=42&pickup_date={pickup}&return_date={return_date}&checkout=1",
        )

    def test_rejects_external_or_invalid_booking_redirects(self):
        self.assertEqual(_booking_redirect("https://example.com/user-portal/?vehicle_id=1"), "/user-portal/")
        self.assertEqual(_booking_redirect("/user-portal/?vehicle_id=0&pickup_date=2026-01-01&return_date=2026-01-02"), "/user-portal/")
        self.assertEqual(_booking_redirect("/user-portal/?vehicle_id=1&pickup_date=not-a-date&return_date=2026-01-02"), "/user-portal/")


class LoginViewTests(TestCase):
    def test_verified_user_can_log_in_and_receives_customer_redirect(self):
        user = User.objects.create_user(
            email="renter@example.com",
            phone_number="9876543210",
            password="CorrectHorseBattery1!",
            role=User.Role.USER,
            is_email_verified=True,
        )

        with patch("apps.accounts.views.verify_captcha", return_value=True):
            response = self.client.post(
                "/api/auth/login/",
                data=json.dumps({
                    "identifier": user.email,
                    "password": "CorrectHorseBattery1!",
                    "role": User.Role.USER,
                    "captcha_id": "test-captcha",
                    "captcha_answer": "ABCDE",
                }),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["redirect"], "/user-portal/")
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.pk))

    def test_correct_password_with_wrong_role_explains_the_required_access_tab(self):
        User.objects.create_user(
            email="admin@example.com",
            phone_number="9876543211",
            password="CorrectHorseBattery1!",
            role=User.Role.ADMIN,
            is_email_verified=True,
        )

        with patch("apps.accounts.views.verify_captcha", return_value=True):
            response = self.client.post(
                "/api/auth/login/",
                data=json.dumps({
                    "identifier": "admin@example.com",
                    "password": "CorrectHorseBattery1!",
                    "role": User.Role.USER,
                    "captcha_id": "test-captcha",
                    "captcha_answer": "ABCDE",
                }),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 403)
        self.assertIn("Administrator access", response.json()["message"])

    def test_reset_request_never_claims_the_otp_is_shown_in_the_page(self):
        User.objects.create_user(
            email="renter@example.com",
            phone_number="9876543212",
            password="CorrectHorseBattery1!",
            is_email_verified=True,
        )

        with patch("apps.accounts.views.send_otp", return_value=(None, "brevo", None)):
            response = self.client.post(
                "/api/auth/password-reset/send-otp/",
                data=json.dumps({"email": "renter@example.com"}),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn("Check Inbox and Spam", response.json()["message"])
        self.assertNotIn("displayed below", response.json()["message"])

    def test_all_supported_roles_can_log_in_through_their_matching_access_tab(self):
        accounts = (
            (User.Role.USER, "user@example.com", "9876543213", "/user-portal/"),
            (User.Role.ADMIN, "admin@example.com", "9876543214", "/control-panel/"),
            (User.Role.SHOPKEEPER, "shop@example.com", "9876543215", "/shopkeeper/"),
        )
        for role, email, phone, expected_redirect in accounts:
            with self.subTest(role=role):
                user = User.objects.create_user(
                    email=email,
                    phone_number=phone,
                    password="CorrectHorseBattery1!",
                    role=role,
                    is_email_verified=True,
                )
                if role == User.Role.SHOPKEEPER:
                    ShopkeeperProfile.objects.create(
                        user=user,
                        shop_name="Test Rentals",
                        shop_address="Dehradun, Uttarakhand",
                    )
                with patch("apps.accounts.views.verify_captcha", return_value=True):
                    response = self.client.post(
                        "/api/auth/login/",
                        data=json.dumps({
                            "identifier": email,
                            "password": "CorrectHorseBattery1!",
                            "role": role,
                            "captcha_id": "test-captcha",
                            "captcha_answer": "ABCDE",
                        }),
                        content_type="application/json",
                    )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["redirect"], expected_redirect)

