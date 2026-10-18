from django.test import SimpleTestCase

from .services import validate_aadhaar, validate_aadhaar_last4, validate_gstin, validate_pan


class IndianIdentityFormatTests(SimpleTestCase):
    def test_validates_pan_format_and_category_code(self):
        self.assertTrue(validate_pan("abcp1234f"))
        self.assertFalse(validate_pan("ABCDE1234F"))
        self.assertFalse(validate_pan("ABCP12345F"))

    def test_validates_gstin_format_and_exact_length(self):
        self.assertTrue(validate_gstin("07ABCP1234F1Z5"))
        self.assertFalse(validate_gstin("07ABCP1234F1Z"))

    def test_aadhaar_last_four_requires_exact_ascii_digits(self):
        self.assertTrue(validate_aadhaar_last4("1234"))
        self.assertFalse(validate_aadhaar_last4("12 34"))
        self.assertFalse(validate_aadhaar_last4("１２３４"))

    def test_full_aadhaar_requires_valid_verhoeff_checksum(self):
        self.assertTrue(validate_aadhaar("2363 0176 6987")[0])
        self.assertFalse(validate_aadhaar("2363 0176 6988")[0])
        self.assertFalse(validate_aadhaar("2363x0176x6987")[0])

