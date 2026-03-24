import re
from datetime import date, timedelta
from dateutil import parser as date_parser
from .ai_engine import predict_category


# ==============================================
# AMOUNT EXTRACTION
# ==============================================

def extract_amount(text: str):

    text = text.lower()

    # Handle 10k, 5k, 2m
    match = re.search(r"(\d+(?:\.\d+)?)\s*(k|m)", text)
    if match:
        num = float(match.group(1))
        unit = match.group(2)

        if unit == "k":
            return num * 1000
        if unit == "m":
            return num * 1000000

    patterns = [
        r"₹\s*(\d+(?:\.\d+)?)",
        r"rs\.?\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*rs",
        r"\b(\d+(?:\.\d+)?)\b"
    ]

    for p in patterns:
        m = re.search(p, text)
        if m:
            try:
                return float(m.group(1))
            except:
                pass

    return None
# ==============================================
# DATE EXTRACTION
# ==============================================

def extract_date(text: str):
    """Extract date from text using keywords and dateutil parser.extract date from month names
    , explicit keywords, and safe parsing.
    keywords: today, yesterday, tomorrow, last week,
      last month, weekdays (Monday, Tuesday, etc.), "5th August", "Aug 5", "2023-08-05"""

    text_lower = text.lower()
    today = date.today()

    # ----------------------------
    # Explicit keywords
    # ----------------------------

    if "today" in text_lower:
        return today

    if "yesterday" in text_lower:
        return today - timedelta(days=1)

    if "tomorrow" in text_lower:
        return today + timedelta(days=1)
    if "last month" in text_lower:
        first_day = today.replace(day=1)
        return first_day - timedelta(days=1)

    if "last week" in text_lower:
        return today - timedelta(days=7)

    # ----------------------------
    # Weekday detection
    # ----------------------------

    weekdays = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    for day, idx in weekdays.items():
        if day in text_lower:
            today_idx = today.weekday()
            diff = today_idx - idx
            if diff < 0:
                diff += 7
            return today - timedelta(days=diff)

    # ----------------------------
    # Day-of-month (1st, 2nd, 3rd)
    # ----------------------------

    match = re.search(r"\b(\d{1,2})(st|nd|rd|th)\b", text_lower)
    if match:
        day = int(match.group(1))
        try:
            return date(today.year, today.month, day)
        except:
            pass

    # ----------------------------
    # Safe parser fallback
    # ----------------------------

    cleaned = re.sub(r"\b\d+(?:\.\d+)?\b", "", text_lower)

    try:
        parsed = date_parser.parse(cleaned, fuzzy=True)

        if parsed.year < 2000 or parsed.year > today.year + 5:
            return today

        return parsed.date()

    except:
        return today


# ==============================================
# FULL TRANSACTION PARSER
# ==============================================

def parse_transaction_text(text: str):

    if not text:
        return {
            "amount": None,
            "category": "Others",
            "transaction_type": "EXPENSE",
            "date": date.today()
        }

    amount = extract_amount(text)
    txn_date = extract_date(text)

    ai = predict_category(text)

    return {
        "amount": amount,
        "category": ai["category"],
        "transaction_type": ai["transaction_type"],
        "date": txn_date
    }