"""Security primitives — encryption, HMAC, masking."""
from django.test import SimpleTestCase

from apps.core.security import (
    chain_hash, decrypt_value, encrypt_value,
    hash_otp, mask_phone, phone_hash, sign_hmac, sign_delivery_seal,
    verify_hmac,
)


class EncryptDecryptTests(SimpleTestCase):
    def test_roundtrip(self):
        plain = "+22671234567"
        token = encrypt_value(plain)
        self.assertNotEqual(plain, token)
        self.assertEqual(decrypt_value(token), plain)

    def test_empty_roundtrip(self):
        self.assertEqual(encrypt_value(""), "")
        self.assertEqual(decrypt_value(""), "")

    def test_mask_phone(self):
        self.assertEqual(mask_phone("+22671234567"), "********4567")
        self.assertEqual(mask_phone(""), "***")


class HmacTests(SimpleTestCase):
    def test_sign_verify(self):
        sig = sign_hmac("hello")
        self.assertTrue(verify_hmac("hello", sig))
        self.assertFalse(verify_hmac("hello", "tampered"))

    def test_seal_signature_changes_with_inputs(self):
        s1 = sign_delivery_seal("a", "b", "c")
        s2 = sign_delivery_seal("a", "b", "x")
        self.assertNotEqual(s1, s2)


class OneWayHashTests(SimpleTestCase):
    def test_phone_hash_deterministic(self):
        self.assertEqual(phone_hash("+22670123456"), phone_hash("+22670123456"))
        self.assertNotEqual(phone_hash("+22670123456"), phone_hash("+22670123457"))

    def test_otp_hash_length(self):
        self.assertEqual(len(hash_otp("123456")), 64)
