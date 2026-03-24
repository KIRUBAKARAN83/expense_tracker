import re
from datetime import date, timedelta
from dateutil import parser as date_parser
from .ai_engine import predict_category


# ==============================================
# AMOUNT EXTRACTION
# ==============================================

def extract_amount(text: str):
    text = text.lower().strip()

    # --------------------------------------------------
    # 1️⃣ Handle written numbers: "twenty thousand", etc.
    # --------------------------------------------------
    word_numbers = {
        "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
        "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
        "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
        "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
        "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
        "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
        "eighty": 80, "ninety": 90, "hundred": 100,
        "thousand": 1000, "lakh": 100000, "million": 1000000,
    }

    # ✅ FIX 1: Only extract EXACT whole-word matches to avoid
    # "stone" matching "one", "phone" matching "one", etc.
    word_tokens = re.findall(r"\b([a-z]+)\b", text.replace("-", " "))
    number_words_found = [w for w in word_tokens if w in word_numbers]

    if number_words_found:
        total = 0
        current = 0
        chunk = 0  # accumulates within a group (e.g. "two hundred")

        for word in word_tokens:
            if word not in word_numbers:
                continue

            val = word_numbers[word]

            if val == 100:
                # ✅ FIX 2: "two hundred" → chunk = 2*100 = 200
                chunk = (chunk or 1) * 100

            elif val >= 1000:
                # "thousand" / "lakh" / "million"
                # ✅ FIX 2: "two hundred thousand" → total += 200 * 1000
                total += (chunk + current) * val
                chunk = 0
                current = 0

            else:
                # simple digit words: one, two ... ninety
                current += val

        # add remaining
        total += chunk + current

        if total > 0:
            return float(total)

    # --------------------------------------------------
    # 2️⃣ Handle shorthand: 10k, 5k, 2m, 1lakh, 2cr
    # --------------------------------------------------
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(crore|lakh|million|thousand|cr|lac|k|m)\b",
        text
    )
    if match:
        num = float(match.group(1))
        unit = match.group(2).strip()
        multipliers = {
            "k":        1_000,
            "thousand": 1_000,
            "m":        1_000_000,
            "million":  1_000_000,
            "lakh":     100_000,
            "lac":      100_000,
            "crore":    10_000_000,
            "cr":       10_000_000,
        }
        return num * multipliers.get(unit, 1)

    # --------------------------------------------------
    # 3️⃣ Symbol/prefix patterns: ₹20000, rs 500, 500rs
    # --------------------------------------------------
    symbol_patterns = [
        r"₹\s*(\d[\d,]*(?:\.\d+)?)",
        r"rs\.?\s*(\d[\d,]*(?:\.\d+)?)",
        r"(\d[\d,]*(?:\.\d+)?)\s*rs\b",
    ]

    for p in symbol_patterns:
        m = re.search(p, text)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except Exception:
                pass

    # --------------------------------------------------
    # 4️⃣ Fallback: grab the LARGEST number in the text
    #    ✅ FIX 3: returns largest, not first
    #    Prevents "spent 20000 on food at 8pm" picking "8" or "20"
    # --------------------------------------------------
    all_numbers = re.findall(r"\b(\d[\d,]*(?:\.\d+)?)\b", text)
    if all_numbers:
        candidates = []
        for n in all_numbers:
            try:
                candidates.append(float(n.replace(",", "")))
            except Exception:
                pass
        if candidates:
            # ✅ Filter out likely non-amounts: years, times, tiny numbers
            # Ignore numbers that look like years (2020-2030) or hours (1-24)
            # unless they are the only number
            meaningful = [
                c for c in candidates
                if not (2000 <= c <= 2100)   # skip years
                and not (c <= 24 and len(candidates) > 1)  # skip hour-like if others exist
            ]
            if meaningful:
                return max(meaningful)
            return max(candidates)

    return None


# ==============================================
# DATE EXTRACTION
# ==============================================

def extract_date(text: str):
    """
    Extract date from text using keywords and dateutil parser.
    Supports: today, yesterday, tomorrow, last week, last month,
    weekdays (Monday–Sunday), "5th August", "Aug 5", "2023-08-05"
    """
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
        "monday":    0,
        "tuesday":   1,
        "wednesday": 2,
        "thursday":  3,
        "friday":    4,
        "saturday":  5,
        "sunday":    6,
    }

    for day_name, idx in weekdays.items():
        if day_name in text_lower:
            today_idx = today.weekday()
            diff = today_idx - idx
            if diff < 0:
                diff += 7
            # ✅ if diff == 0 it means today, return today
            return today - timedelta(days=diff)

    # ----------------------------
    # Day-of-month: "5th", "3rd"
    # ----------------------------
    match = re.search(r"\b(\d{1,2})(st|nd|rd|th)\b", text_lower)
    if match:
        day = int(match.group(1))
        try:
            return date(today.year, today.month, day)
        except ValueError:
            pass  # invalid day like 31st in a 30-day month

    # ----------------------------
    # Safe dateutil parser fallback
    # ✅ Strip plain numbers first so "spent 500" doesn't parse
    #    "500" as a date component
    # ----------------------------
    cleaned = re.sub(r"\b\d+(?:\.\d+)?\b", "", text_lower).strip()

    try:
        parsed = date_parser.parse(cleaned, fuzzy=True)

        if parsed.year < 2000 or parsed.year > today.year + 5:
            return today

        return parsed.date()

    except Exception:
        return today


# ==============================================
# FULL TRANSACTION PARSER
# ==============================================

def parse_transaction_text(text: str):

    if not text or not text.strip():
        return {
            "amount": None,
            "category": "Others",
            "transaction_type": "EXPENSE",
            "date": date.today(),
        }

    amount   = extract_amount(text)
    txn_date = extract_date(text)
    ai       = predict_category(text)

    return {
        "amount":           amount,
        "category":         ai["category"],
        "transaction_type": ai["transaction_type"],
        "date":             txn_date,
    }
