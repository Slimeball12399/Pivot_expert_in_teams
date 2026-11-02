from datetime import date, datetime, timedelta, timezone

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from phonenumber_field.phonenumber import PhoneNumber

from accounts.validators import (
    MIN_AGE,
    age_on,
    validate_danish_phone_number,
    validate_min_age,
)

from .utils import FIXED_NOW, frozen_now

TODAY = FIXED_NOW.date()


class AgeOnTests(SimpleTestCase):
    def test_counts_full_years(self):
        cases = [
            # (birth date, today, expected age)
            (date(2000, 6, 15), date(2026, 6, 15), 26),  # birthday today
            (date(2000, 6, 16), date(2026, 6, 15), 25),  # birthday tomorrow
            (date(2000, 6, 14), date(2026, 6, 15), 26),  # birthday yesterday
            (date(2008, 2, 29), date(2027, 2, 28), 18),  # leap day: not yet in a non-leap year
            (date(2008, 2, 29), date(2027, 3, 1), 19),   # leap day: counts from 1 March
        ]
        for birth_date, today, expected in cases:
            with self.subTest(birth_date=birth_date, today=today):
                self.assertEqual(age_on(birth_date, today), expected)


class ValidateMinAgeTests(SimpleTestCase):
    def setUp(self):
        patcher = frozen_now()
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_validate_min_age(self):
        with self.subTest("accepts old enough"):
            for birth_date in [
                date(TODAY.year - MIN_AGE, TODAY.month, TODAY.day),  # turns MIN_AGE today
                date(TODAY.year - 40, 1, 1),
            ]:
                validate_min_age(birth_date)  # must not raise

        with self.subTest("rejects too young"):
            birth_date = date(TODAY.year - MIN_AGE, TODAY.month, TODAY.day + 1)  # turns MIN_AGE tomorrow
            with self.assertRaises(ValidationError) as ctx:
                validate_min_age(birth_date)
            self.assertEqual(ctx.exception.code, "too_young")

        with self.subTest("rejects a birth date in the future"):
            with self.assertRaises(ValidationError) as ctx:
                validate_min_age(TODAY + timedelta(days=1))
            self.assertEqual(ctx.exception.code, "future_birth_date")

        with self.subTest("uses the UTC date"):
            # 23:30 UTC on 14 June is already 15 June in Copenhagen,
            # but in UTC the 15 June birthday hasn't happened yet.
            with frozen_now(datetime(2026, 6, 14, 23, 30, tzinfo=timezone.utc)):
                with self.assertRaises(ValidationError):
                    validate_min_age(date(2026 - MIN_AGE, 6, 15))


class ValidateDanishPhoneNumberTests(SimpleTestCase):
    def test_validate_danish_phone_number(self):
        with self.subTest("accepts a Danish number"):
            validate_danish_phone_number(PhoneNumber.from_string("+4520123456"))

        with self.subTest("ignores an empty value"):
            # Blank is handled by the field itself (blank=True), not this validator.
            validate_danish_phone_number("")

        for number in ["+36201234567", "+46701234567", "+299321000"]:
            with self.subTest("rejects a foreign number", number=number):
                with self.assertRaises(ValidationError):
                    validate_danish_phone_number(PhoneNumber.from_string(number))
