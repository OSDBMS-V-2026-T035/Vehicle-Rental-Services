from django.test import TestCase
from unittest.mock import patch
from types import SimpleNamespace

from apps.accounts.models import User
from .models import Notification
from .services import notify_paid_booking_with_documents, notify_user


class NotificationDeduplicationTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="notice@example.com",
            phone_number="9876543210",
            password="safe-test-password",
        )

    def test_same_notification_event_is_stored_once(self):
        notify_user(self.user, "Payment successful", "Booking #17 was paid.", email=False)
        notify_user(self.user, "Payment successful", "Booking #17 was paid.", email=False)

        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    def test_distinct_notification_events_are_preserved(self):
        notify_user(self.user, "Payment successful", "Booking #17 was paid.", email=False)
        notify_user(self.user, "Payment successful", "Booking #18 was paid.", email=False)

        self.assertEqual(Notification.objects.filter(user=self.user).count(), 2)

    @patch("apps.notifications.services.send_transactional_email", side_effect=[RuntimeError("temporary outage"), "brevo"])
    def test_failed_email_delivery_is_retried_without_duplicate_notification(self, send_email):
        notify_user(self.user, "Security update", "Your password was changed.")
        notice = Notification.objects.get(user=self.user)
        self.assertFalse(notice.email_sent)

        notify_user(self.user, "Security update", "Your password was changed.")

        notice.refresh_from_db()
        self.assertTrue(notice.email_sent)
        self.assertEqual(send_email.call_count, 2)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)

    @patch("apps.notifications.services.send_transactional_email", side_effect=[RuntimeError("temporary outage"), "brevo"])
    @patch("apps.bookings.documents._document_bytes", return_value=b"pdf")
    def test_paid_booking_documents_retry_after_email_failure(self, _document_bytes, send_email):
        payment = SimpleNamespace(
            customer=self.user,
            booking=SimpleNamespace(id=17),
        )
        notify_paid_booking_with_documents(payment)
        notify_paid_booking_with_documents(payment)

        notice = Notification.objects.get(user=self.user)
        self.assertTrue(notice.email_sent)
        self.assertEqual(send_email.call_count, 2)
        self.assertEqual(Notification.objects.filter(user=self.user).count(), 1)
