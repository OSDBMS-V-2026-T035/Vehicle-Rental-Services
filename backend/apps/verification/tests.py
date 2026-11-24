from django.test import SimpleTestCase

from .services import validate_aadhaar, validate_aadhaar_last4, validate_gstin, validate_pan


class IndianIdentityFormatTests(SimpleTestCase):
    def test_validates_pan_format_and_category_code(self):
        self.assertTrue(validate_pan("abcpd1234f"))
        self.assertTrue(validate_pan("JUAPD7426L"))
        self.assertFalse(validate_pan("ABCP1234F"))
        self.assertFalse(validate_pan("ABCPD12345F"))

    def test_validates_gstin_format_and_exact_length(self):
        self.assertTrue(validate_gstin("07ABCPD1234F1Z5"))
        self.assertFalse(validate_gstin("07ABCPD1234F1Z"))

    def test_aadhaar_last_four_requires_exact_ascii_digits(self):
        self.assertTrue(validate_aadhaar_last4("1234"))
        self.assertFalse(validate_aadhaar_last4("12 34"))
        self.assertFalse(validate_aadhaar_last4("１２３４"))

    def test_full_aadhaar_requires_exactly_twelve_digits(self):
        self.assertTrue(validate_aadhaar("1234 5678 9012")[0])
        self.assertTrue(validate_aadhaar("012345678901")[0])
        self.assertFalse(validate_aadhaar("12345678901")[0])
        self.assertFalse(validate_aadhaar("1234567890123")[0])
        self.assertFalse(validate_aadhaar("2363x0176x6987")[0])

    def test_full_aadhaar_rejects_six_or_more_consecutive_repeated_digits(self):
        self.assertFalse(validate_aadhaar("999999999999")[0])
        self.assertFalse(validate_aadhaar("888888999999")[0])
        self.assertFalse(validate_aadhaar("444444455555")[0])
        self.assertFalse(validate_aadhaar("123450000001")[0])
        self.assertTrue(validate_aadhaar("123455678901")[0])

