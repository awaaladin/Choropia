from datetime import timedelta
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts import otp
from accounts import pin as pin_service
from accounts.models import TransactionPin, User

URL = "/api/v1/account/pin/"


def make_user(email="seller@example.com", password="correct horse 9"):
    user = User.objects.create_user(email=email, password=password)
    return user


class PinRulesTests(TestCase):
    def test_new_pin_must_be_four_digits_and_not_obvious(self):
        for bad in ("", "123", "12345", "12a4", "0000", "1111", "1234", "4321", "6789", "9876"):
            with self.assertRaises(ValueError, msg=bad):
                pin_service.validate_new_pin(bad)
        for good in ("2580", "1357", "9024", "1123"):
            self.assertEqual(pin_service.validate_new_pin(good), good)

    def test_only_a_hash_is_stored(self):
        user = make_user()
        pin_service.set_pin(user, "2580")
        row = TransactionPin.objects.get(user=user)
        self.assertNotIn("2580", row.pin_hash)
        self.assertTrue(row.pin_hash.startswith(("md5$", "pbkdf2", "argon2", "bcrypt", "scrypt")))

    def test_right_pin_passes_and_resets_the_count(self):
        user = make_user()
        pin_service.set_pin(user, "2580")
        with self.assertRaises(pin_service.PinError):
            pin_service.verify_pin(user, "1357")
        pin_service.verify_pin(user, "2580")
        self.assertEqual(TransactionPin.objects.get(user=user).failed_attempts, 0)

    def test_no_pin_and_wrong_pin_give_the_same_error(self):
        with_pin, without = make_user("a@example.com"), make_user("b@example.com")
        pin_service.set_pin(with_pin, "2580")
        with self.assertRaises(pin_service.PinError) as wrong:
            pin_service.verify_pin(with_pin, "1357")
        with self.assertRaises(pin_service.PinError) as missing:
            pin_service.verify_pin(without, "1357")
        self.assertEqual((wrong.exception.code, wrong.exception.message), (missing.exception.code, missing.exception.message))
        self.assertEqual(missing.exception.code, "pin_invalid")

    @override_settings(PIN_MAX_ATTEMPTS=5, PIN_LOCK_MINUTES=15)
    def test_five_wrong_pins_lock_it_for_fifteen_minutes_even_for_the_right_pin(self):
        user = make_user()
        pin_service.set_pin(user, "2580")
        codes = []
        for _ in range(5):
            with self.assertRaises(pin_service.PinError) as err:
                pin_service.verify_pin(user, "1357")
            codes.append(err.exception.code)
        self.assertEqual(codes, ["pin_invalid"] * 4 + ["pin_locked"])
        with self.assertRaises(pin_service.PinError) as err:
            pin_service.verify_pin(user, "2580")
        self.assertEqual(err.exception.code, "pin_locked")
        self.assertGreater(err.exception.retry_after, 14 * 60)

        later = timezone.now() + timedelta(minutes=16)
        with mock.patch("django.utils.timezone.now", return_value=later):
            pin_service.verify_pin(user, "2580")  # unlocked


class PinEndpointTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_requires_login(self):
        self.assertEqual(APIClient().get(URL).status_code, 401)

    def test_status_then_first_set(self):
        self.assertEqual(self.client.get(URL).json()["has_pin"], False)
        r = self.client.post(URL, {"pin": "2580"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertTrue(r.json()["has_pin"])
        self.assertNotIn("2580", r.content.decode())

    def test_obvious_pin_is_refused(self):
        self.assertEqual(self.client.post(URL, {"pin": "1234"}, format="json").status_code, 400)

    def test_change_needs_proof(self):
        self.client.post(URL, {"pin": "2580"}, format="json")
        self.assertEqual(self.client.post(URL, {"pin": "1357"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(URL, {"pin": "1357", "old_pin": "9024"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(URL, {"pin": "1357", "password": "wrong"}, format="json").status_code, 400)
        self.assertEqual(self.client.post(URL, {"pin": "1357", "old_pin": "2580"}, format="json").status_code, 200)
        pin_service.verify_pin(self.user, "1357")

    def test_password_resets_a_locked_pin(self):
        self.client.post(URL, {"pin": "2580"}, format="json")
        for _ in range(5):
            self.client.post(URL, {"pin": "1357", "old_pin": "9024"}, format="json")
        self.assertTrue(self.client.get(URL).json()["locked"])
        r = self.client.post(URL, {"pin": "1357", "password": "correct horse 9"}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        self.assertFalse(r.json()["locked"])

    def test_emailed_code_resets_the_pin_for_people_without_a_password(self):
        self.user.set_unusable_password()
        self.user.save()
        self.client.post(URL, {"pin": "2580"}, format="json")
        with self.captureOnCommitCallbacks(execute=True):
            self.assertEqual(self.client.post(URL + "reset-code/").status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        code = _code_from(mail.outbox[0])
        self.assertEqual(self.client.post(URL, {"pin": "1357", "email_code": "000000"}, format="json").status_code, 400)
        r = self.client.post(URL, {"pin": "1357", "email_code": code}, format="json")
        self.assertEqual(r.status_code, 200, r.content)
        pin_service.verify_pin(self.user, "1357")


def _code_from(message):
    import re

    bodies = [message.body] + [alt[0] for alt in getattr(message, "alternatives", [])]
    for body in bodies:
        found = re.search(r"\b(\d{6})\b", body)
        if found:
            return found.group(1)
    raise AssertionError("no code in email")
