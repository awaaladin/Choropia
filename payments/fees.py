"""
Choropia's seller fee, in one place. Integer kobo in, integer kobo out; no floats anywhere.

The fee is charged on each slice of the price at that slice's own rate (like income-tax bands), so
crossing a band boundary never makes a seller worse off:

    slice of the price            verified seller   unverified seller
    first ₦50,000                      5%                 6%
    ₦50,000.01 – ₦500,000              3%                 3.5%
    ₦500,000.01 – ₦2,000,000           0.5%               0.5%
    above ₦2,000,000                   0.05%              0.05%

The exact total is rounded half up to the kobo once (never per slice), then raised to MIN_FEE_KOBO
(default ₦200). The fee never exceeds the price itself, so a seller's net can't go negative on a
tiny sale. There is no upper cap.

The buyer never pays this; it comes out of the seller's payout.
"""
from django.conf import settings

# (upper bound of the band in kobo, or None for "and above"; rate in hundredths of a percent / basis points)
BANDS_VERIFIED = (
    (5_000_000, 500),  # ₦50,000 at 5%
    (50_000_000, 300),  # ₦500,000 at 3%
    (200_000_000, 50),  # ₦2,000,000 at 0.5%
    (None, 5),  # above at 0.05%
)
BANDS_UNVERIFIED = (
    (5_000_000, 600),
    (50_000_000, 350),
    (200_000_000, 50),
    (None, 5),
)
BASIS = 10_000  # basis points per 100%

DEFAULT_MIN_FEE_KOBO = 20_000  # ₦200


def bands_for(verified: bool):
    return BANDS_VERIFIED if verified else BANDS_UNVERIFIED


def min_fee_kobo() -> int:
    return int(getattr(settings, "MIN_FEE_KOBO", DEFAULT_MIN_FEE_KOBO))


def _round_half_up(numerator: int, denominator: int) -> int:
    """numerator/denominator rounded half up, for non-negative integers."""
    return (2 * numerator + denominator) // (2 * denominator)


def fee_kobo(amount_kobo: int, verified: bool) -> int:
    """Choropia's fee on a sale of `amount_kobo`, in kobo."""
    if isinstance(amount_kobo, bool) or not isinstance(amount_kobo, int):
        raise TypeError("amount_kobo must be an int (kobo), never a float or Decimal")
    if amount_kobo <= 0:
        return 0

    exact = 0  # in kobo × BASIS, so the sum stays an exact integer
    lower = 0
    for upper, rate in bands_for(verified):
        top = amount_kobo if upper is None else min(amount_kobo, upper)
        if top > lower:
            exact += (top - lower) * rate
        if upper is None or amount_kobo <= upper:
            break
        lower = upper

    fee = max(_round_half_up(exact, BASIS), min_fee_kobo())
    return min(fee, amount_kobo)


def split_kobo(amount_kobo: int, verified: bool):
    """(fee, seller_net): always adds back up to amount_kobo."""
    fee = fee_kobo(amount_kobo, verified)
    return fee, amount_kobo - fee


def bands_table(verified: bool):
    """The bands as plain data for the apps: [{"from_kobo", "to_kobo" (None = and above), "rate_bp"}]."""
    rows, lower = [], 0
    for upper, rate in bands_for(verified):
        rows.append({"from_kobo": lower, "to_kobo": upper, "rate_bp": rate})
        lower = upper or lower
    return rows
