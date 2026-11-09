from django.test import SimpleTestCase, override_settings

from payments import fees

N = 100  # kobo per naira


class RequiredFeeTableTests(SimpleTestCase):
    """The table from the spec, exactly."""

    TABLE = (
        # naira, verified fee, unverified fee
        (2_000, 200, 200),
        (8_000, 400, 480),
        (185_000, 6_550, 7_725),
        (450_000, 14_500, 17_000),
        (4_500_000, 24_750, 27_500),
    )

    def test_required_values(self):
        for naira, verified, unverified in self.TABLE:
            self.assertEqual(fees.fee_kobo(naira * N, True), verified * N, f"verified ₦{naira}")
            self.assertEqual(fees.fee_kobo(naira * N, False), unverified * N, f"unverified ₦{naira}")


class SliceBoundaryTests(SimpleTestCase):
    def test_exactly_at_the_first_boundary_is_all_first_band(self):
        self.assertEqual(fees.fee_kobo(50_000 * N, True), 2_500 * N)
        self.assertEqual(fees.fee_kobo(50_000 * N, False), 3_000 * N)

    def test_one_kobo_over_the_first_boundary_is_charged_at_the_second_rate(self):
        # 2,500 naira + 3% of 1 kobo (0.03 kobo) rounds away
        self.assertEqual(fees.fee_kobo(50_000 * N + 1, True), 2_500 * N)
        # 100 kobo over: + 3 kobo
        self.assertEqual(fees.fee_kobo(50_000 * N + 100, True), 2_500 * N + 3)

    def test_second_and_third_boundaries(self):
        self.assertEqual(fees.fee_kobo(500_000 * N, True), (2_500 + 13_500) * N)
        self.assertEqual(fees.fee_kobo(500_000 * N, False), (3_000 + 15_750) * N)
        self.assertEqual(fees.fee_kobo(2_000_000 * N, True), (2_500 + 13_500 + 7_500) * N)
        self.assertEqual(fees.fee_kobo(2_000_000 * N, False), (3_000 + 15_750 + 7_500) * N)

    def test_fee_never_drops_as_the_price_rises(self):
        previous = 0
        for naira in range(1, 3_000_000, 7_919):
            fee = fees.fee_kobo(naira * N, False)
            self.assertGreaterEqual(fee, previous, naira)
            previous = fee

    def test_upper_bands_are_the_same_for_both(self):
        top = 10_000_000 * N
        diff = fees.fee_kobo(top, False) - fees.fee_kobo(top, True)
        self.assertEqual(diff, (3_000 - 2_500 + 15_750 - 13_500) * N)  # only the first two bands differ


class MinimumFeeTests(SimpleTestCase):
    def test_minimum_applies(self):
        self.assertEqual(fees.fee_kobo(1_000 * N, True), 200 * N)

    def test_fee_never_exceeds_the_price(self):
        self.assertEqual(fees.fee_kobo(150 * N, True), 150 * N)
        self.assertEqual(fees.split_kobo(150 * N, True), (150 * N, 0))

    @override_settings(MIN_FEE_KOBO=50_000)
    def test_minimum_is_a_setting(self):
        self.assertEqual(fees.fee_kobo(8_000 * N, True), 500 * N)

    def test_zero_or_negative_is_no_fee(self):
        self.assertEqual(fees.fee_kobo(0, True), 0)
        self.assertEqual(fees.fee_kobo(-5, True), 0)


class RoundingTests(SimpleTestCase):
    @override_settings(MIN_FEE_KOBO=0)
    def test_rounds_half_up_once_on_the_total(self):
        # 5% of 10 kobo = 0.5 kobo -> 1 (half up)
        self.assertEqual(fees.fee_kobo(10, True), 1)
        # 5% of 9 kobo = 0.45 -> 0
        self.assertEqual(fees.fee_kobo(9, True), 0)
        # 6% of 25 kobo = 1.5 -> 2
        self.assertEqual(fees.fee_kobo(25, False), 2)

    @override_settings(MIN_FEE_KOBO=0)
    def test_rounding_is_on_the_exact_sum_not_per_slice(self):
        # verified: 2,500 naira on band 1, then 3% of 50 kobo = 1.5 kobo; total exact = 250000 + 1.5 -> 250002
        self.assertEqual(fees.fee_kobo(5_000_050, True), 250_002)

    def test_rejects_floats_and_decimals(self):
        from decimal import Decimal

        for bad in (100.0, Decimal("100"), "100", True):
            with self.assertRaises(TypeError):
                fees.fee_kobo(bad, True)

    def test_split_adds_back(self):
        for amount in (1, 99, 20_000, 5_000_001, 123_456_789, 999_999_999_99):
            for verified in (True, False):
                fee, net = fees.split_kobo(amount, verified)
                self.assertEqual(fee + net, amount)
                self.assertGreaterEqual(net, 0)
