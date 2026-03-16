"""Day count convention implementations."""

from __future__ import annotations

from datetime import date

ACTUAL_360_DAYS = 360.0
THIRTY_360_DAYS = 360.0
SUPPORTED_DAY_COUNT_CONVENTIONS = {"ACT/ACT", "30/360", "ACT/360"}


def year_fraction(
    start_date: date,
    end_date: date,
    convention: str,
    frequency: int | None = None,
) -> float:
    """Compute the year fraction between two dates.

    Parameters
    ----------
    start_date : date
        Start date of the accrual period.
    end_date : date
        End date of the accrual period.
    convention : str
        Day count convention. Supported values are ``ACT/ACT``, ``30/360``, and ``ACT/360``.
    frequency : int | None, optional
        Coupon frequency used by certain conventions. Included for interface stability.

    Returns
    -------
    float
        Year fraction between the two dates.
    """
    # frequency kept for compatibility with bond pricing and future extensions.
    if end_date < start_date:
        raise ValueError("end_date must be on or after start_date.")
    if convention not in SUPPORTED_DAY_COUNT_CONVENTIONS:
        raise ValueError(f"Unsupported day count convention: {convention}")

    if convention == "ACT/ACT":
        return _actual_actual(start_date=start_date, end_date=end_date)
    if convention == "30/360":
        return _thirty_360(start_date=start_date, end_date=end_date)
    return (end_date - start_date).days / ACTUAL_360_DAYS


def _actual_actual(start_date: date, end_date: date) -> float:
    """Return the ACT/ACT year fraction by splitting across calendar years."""
    if start_date == end_date:
        return 0.0

    accrual = 0.0
    current_start = start_date
    while current_start < end_date:
        year_end = date(current_start.year + 1, 1, 1)
        current_end = min(year_end, end_date)
        days_in_year = 366 if _is_leap_year(current_start.year) else 365
        accrual += (current_end - current_start).days / days_in_year
        current_start = current_end
    return accrual


def _thirty_360(start_date: date, end_date: date) -> float:
    """Return the 30/360 US year fraction."""
    start_day = min(start_date.day, 30)
    end_day = end_date.day
    if start_day == 30 and end_day == 31:
        end_day = 30

    numerator = (
        360 * (end_date.year - start_date.year)
        + 30 * (end_date.month - start_date.month)
        + (end_day - start_day)
    )
    return numerator / THIRTY_360_DAYS


def _is_leap_year(year: int) -> bool:
    """Return whether a calendar year is a leap year."""
    return year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)
