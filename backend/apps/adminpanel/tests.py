import json
from datetime import date, timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import ShopkeeperProfile, User
from apps.bookings.models import Booking
from apps.vehicles.models import Vehicle


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


class ProtectedAdminDocumentTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="document-admin@example.com",
            phone_number="9876543120",
            password="StrongPassword1!",
            role=User.Role.ADMIN,
            is_staff=True,
            is_email_verified=True,
        )
        self.customer = User.objects.create_user(
            email="document-customer@example.com",
            phone_number="9876543121",
            password="StrongPassword1!",
            is_email_verified=True,
        )
        self.profile = ShopkeeperProfile.objects.create(
            user=User.objects.create_user(
                email="document-shop@example.com",
                phone_number="9876543122",
                password="StrongPassword1!",
                role=User.Role.SHOPKEEPER,
                is_email_verified=True,
            ),
            shop_name="Document Rentals",
            shop_address="Dehradun, Uttarakhand",
            aadhaar_document=SimpleUploadedFile("aadhaar.pdf", b"private-document", content_type="application/pdf"),
        )

    def test_admin_can_read_a_review_document_through_the_protected_endpoint(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("admin-document", args=["shopkeepers", self.profile.id, "aadhaar_document"]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "private, no-store, max-age=0")
        self.assertEqual(b"".join(response.streaming_content), b"private-document")

    def test_non_admin_cannot_read_a_review_document(self):
        self.client.force_login(self.customer)

        response = self.client.get(reverse("admin-document", args=["shopkeepers", self.profile.id, "aadhaar_document"]))

        self.assertEqual(response.status_code, 403)


class AdminVehicleEditTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="inventory-admin@example.com",
            phone_number="9876543130",
            password="StrongPassword1!",
            role=User.Role.ADMIN,
            is_staff=True,
            is_email_verified=True,
        )
        owner = User.objects.create_user(
            email="inventory-shop@example.com",
            phone_number="9876543131",
            password="StrongPassword1!",
            role=User.Role.SHOPKEEPER,
            is_email_verified=True,
        )
        shop = ShopkeeperProfile.objects.create(
            user=owner,
            shop_name="Inventory Rentals",
            shop_address="Dehradun, Uttarakhand",
            verification_status=ShopkeeperProfile.VerificationStatus.VERIFIED,
        )
        self.customer = User.objects.create_user(
            email="inventory-customer@example.com",
            phone_number="9876543132",
            password="StrongPassword1!",
            is_email_verified=True,
        )
        self.vehicle = Vehicle.objects.create(
            shopkeeper=shop,
            vehicle_type=Vehicle.VehicleType.CAR,
            brand="Inventory",
            model_name="One",
            registration_number="UK07IJ1234",
            manufacturing_year=2024,
            daily_rate="1000.00",
            quantity=3,
            available_quantity=2,
            listing_status=Vehicle.ListingStatus.APPROVED,
        )
        Booking.objects.create(
            customer=self.customer,
            vehicle=self.vehicle,
            pickup_date=date.today() + timedelta(days=1),
            return_date=date.today() + timedelta(days=2),
            total_amount="1000.00",
            status=Booking.Status.CONFIRMED,
        )
        Booking.objects.create(
            customer=self.customer,
            vehicle=self.vehicle,
            pickup_date=date.today() + timedelta(days=1),
            return_date=date.today() + timedelta(days=2),
            total_amount="1000.00",
            status=Booking.Status.CONFIRMED,
        )
        self.client.force_login(self.admin)

    def test_admin_cannot_reduce_inventory_below_active_reservations(self):
        response = self.client.post(
            reverse("admin-vehicle-action", args=[self.vehicle.id]),
            data=json.dumps({"action": "edit", "daily_rate": "1250.10", "quantity": 1}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)

    def test_admin_recalculates_available_inventory_and_preserves_decimal_rate(self):
        response = self.client.post(
            reverse("admin-vehicle-action", args=[self.vehicle.id]),
            data=json.dumps({"action": "edit", "daily_rate": "1250.10", "quantity": 2}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.vehicle.refresh_from_db()
        self.assertEqual(str(self.vehicle.daily_rate), "1250.10")
        self.assertEqual(self.vehicle.quantity, 2)
        self.assertEqual(self.vehicle.available_quantity, 0)

