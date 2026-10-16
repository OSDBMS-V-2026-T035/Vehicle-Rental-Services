from django.test import TestCase

from apps.accounts.models import User
from .models import Notification
from .services import notify_user


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
