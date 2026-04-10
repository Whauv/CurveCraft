"""Coupon schedule generation helpers."""

from __future__ import annotations

from datetime import date

import pandas as pd
from pandas.tseries.offsets import BDay, DateOffset

FREQUENCY_TO_MONTHS = {1: 12, 2: 6, 4: 3}


def generate_coupon_schedule(issue_date: date, maturity_date: date, frequency: int) -> list[date]:
    """Generate a coupon schedule with Modified Following adjustments.

    Parameters
    ----------
    issue_date : date
        Bond issue date.
    maturity_date : date
        Bond maturity date.
    frequency : int
        Coupon frequency per year.

    Returns
    -------
    list[date]
        Adjusted coupon payment dates after the issue date and including maturity.
    """
    if frequency not in FREQUENCY_TO_MONTHS:
        raise ValueError(f"Unsupported frequency: {frequency}")
    if issue_date >= maturity_date:
        raise ValueError("issue_date must be earlier than maturity_date.")

    months = FREQUENCY_TO_MONTHS[frequency]
    raw_schedule = pd.date_range(
        start=pd.Timestamp(issue_date),
        end=pd.Timestamp(maturity_date),
        freq=DateOffset(months=months),
    )
    if raw_schedule.empty or raw_schedule[-1].date() != maturity_date:
        raw_schedule = raw_schedule.append(pd.DatetimeIndex([pd.Timestamp(maturity_date)]))

    payment_dates: list[date] = []
    for scheduled_date in raw_schedule:
        scheduled = scheduled_date.date()
        if scheduled <= issue_date:
            continue
        payment_dates.append(adjust_modified_following(scheduled))
    return payment_dates


def adjust_modified_following(payment_date: date) -> date:
    """Adjust a payment date using the Modified Following convention."""
    timestamp = pd.Timestamp(payment_date)
    if _is_business_day(timestamp):
        return payment_date

    following = (timestamp + BDay(1)).date()
    if following.month != payment_date.month:
        preceding = (timestamp - BDay(1)).date()
        return preceding
    return following


def _is_business_day(timestamp: pd.Timestamp) -> bool:
    """Return whether a timestamp falls on a weekday."""
    return bool(timestamp.dayofweek < 5)

