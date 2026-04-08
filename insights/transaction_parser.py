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
        # singular + plural + common Tamil-English spellings
        "thousand": 1_000,   "thousands": 1_000,
        "lakh":    100_000,  "lakhs":    100_000,  "lac": 100_000, "lacs": 100_000,
        "crore":  10_000_000, "crores": 10_000_000, "cr": 10_000_000,
        "million": 1_000_000, "millions": 1_000_000,
        "billion": 1_000_000_000,
    }

    # Build total from word numbers if found
    words = text.replace("-", " ").split()
    total = 0
    current = 0
    found_word_number = False   # True once we see any digit-word (one…ninety, hundred)
    has_digit_word = False      # True once a non-multiplier number word is seen

    # Large-scale multipliers (thousand, lakh, crore, million, billion)
    LARGE = {1_000, 100_000, 10_000_000, 1_000_000, 1_000_000_000}

    for word in words:
        clean = re.sub(r"[^a-z]", "", word)
        if clean not in word_numbers:
            continue
        val = word_numbers[clean]

        if val == 0:
            continue
        elif val == 100:
            # "hundred" — only meaningful after a digit word
            if has_digit_word:
                found_word_number = True
                current = (current or 1) * 100
        elif val in LARGE:
            # Only apply multiplier if a preceding number word was seen;
            # otherwise "20 lakhs" with digit 20 should go to shorthand path
            if has_digit_word:
                found_word_number = True
                total += (current or 1) * val
                current = 0
        else:
            # ordinary digit word (one … ninety)
            found_word_number = True
            has_digit_word = True
            current += val

    if found_word_number:
        total += current
        if total > 0:
            return float(total)

    # --------------------------------------------------
    # 2️⃣ Handle shorthand: 10k, 5k, 2m, 1lakh
    # --------------------------------------------------
    match = re.search(r"(\d+(?:\.\d+)?)\s*(k|m|lakhs?|l\b|crores?|cr|billions?|millions?|thousands?)", text)
    if match:
        num = float(match.group(1))
        unit = match.group(2).strip().rstrip("s")  # normalise plural → singular
        multipliers = {
            "k":      1_000,
            "m":      1_000_000,
            "lakh":   100_000,
            "l":      100_000,
            "crore":  10_000_000,
            "cr":     10_000_000,
            "million":1_000_000,
            "billion":1_000_000_000,
            "thousand":1_000,
        }
        return num * multipliers.get(unit, 1)

    # --------------------------------------------------
    # 3️⃣ Symbol/prefix patterns: ₹20000, rs 500
    # --------------------------------------------------
    symbol_patterns = [
        r"₹\s*(\d[\d,]*(?:\.\d+)?)",
        r"rs\.?\s*(\d[\d,]*(?:\.\d+)?)",
        r"(\d[\d,]*(?:\.\d+)?)\s*rs",
    ]

    for p in symbol_patterns:
        m = re.search(p, text)
        if m:
            try:
                return float(m.group(1).replace(",", ""))
            except:
                pass

    # --------------------------------------------------
    # 4️⃣ Fallback: grab the LARGEST number in the text
    #    (fixes "20" being picked over "20000")
    # --------------------------------------------------
    all_numbers = re.findall(r"\b(\d[\d,]*(?:\.\d+)?)\b", text)
    if all_numbers:
        candidates = []
        for n in all_numbers:
            try:
                candidates.append(float(n.replace(",", "")))
            except:
                pass
        if candidates:
            return max(candidates)  # ← KEY FIX: return largest, not first

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
