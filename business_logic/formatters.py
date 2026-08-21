from datetime import datetime, date
import jdatetime
from typing import Union

PERSIAN_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
LATIN_DIGITS = "0123456789"

TRANS_LATIN_TO_PERSIAN = str.maketrans(LATIN_DIGITS, PERSIAN_DIGITS)
TRANS_PERSIAN_TO_LATIN = str.maketrans(PERSIAN_DIGITS, LATIN_DIGITS)


def to_persian_digits(str_val: Union[str, int, float]) -> str:
    """Converts standard Latin digits to Persian digits."""
    return str(str_val).translate(TRANS_LATIN_TO_PERSIAN)


def to_latin_digits(str_val: str) -> str:
    """Converts Persian digits to standard Latin digits."""
    return str(str_val).translate(TRANS_PERSIAN_TO_LATIN)


def gregorian_to_shamsi(dt_or_str: Union[datetime, date, str]) -> str:
    """
    Converts Gregorian date or YYYY-MM-DD string to Shamsi YYYY/MM/DD string.
    """
    if not dt_or_str:
        return ""
    if isinstance(dt_or_str, str):
        try:
            d = datetime.strptime(dt_or_str.split()[0], "%Y-%m-%d").date()
        except ValueError:
            return dt_or_str
    elif isinstance(dt_or_str, datetime):
        d = dt_or_str.date()
    else:
        d = dt_or_str

    j_date = jdatetime.date.fromgregorian(date=d)
    return j_date.strftime("%Y/%m/%d")


def shamsi_to_gregorian(shamsi_str: str) -> str:
    """
    Converts Shamsi YYYY/MM/DD or YYYY-MM-DD string to Gregorian YYYY-MM-DD string.
    """
    if not shamsi_str:
        return ""
    normalized = to_latin_digits(shamsi_str).replace("-", "/").strip()
    parts = normalized.split("/")
    if len(parts) != 3:
        return shamsi_str
    try:
        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
        g_date = jdatetime.date(year, month, day).togregorian()
        return g_date.strftime("%Y-%m-%d")
    except Exception:
        return shamsi_str


def get_current_shamsi_date() -> str:
    """Returns today's Shamsi date formatted as YYYY/MM/DD."""
    return jdatetime.date.today().strftime("%Y/%m/%d")


def format_currency(amount: float, unit: str = "toman", use_persian_digits: bool = True) -> str:
    """
    Formats a numeric amount with thousands separator and unit label (تومان / ریال).
    """
    val = float(amount or 0)
    if unit.lower() == "rial":
        # If input is in Toman and unit requested is Rial, or stored as base Toman
        formatted_num = f"{int(val):,}"
        unit_label = "ریال"
    else:
        formatted_num = f"{int(val):,}"
        unit_label = "تومان"

    if use_persian_digits:
        formatted_num = to_persian_digits(formatted_num)

    return f"{formatted_num} {unit_label}"
