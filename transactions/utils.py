# transactions/utils.py
import os
import re
import logging
from groq import Groq  # for direct Groq API usage in transcription

logger = logging.getLogger(__name__)

# -----------------------
# Groq client helper
# -----------------------
def get_client():
    """
    Return a Groq client initialized from GROQ_API_KEY environment variable.
    Raises ValueError if key is missing.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")
    return Groq(api_key=api_key)


def transcribe_audio(file_obj, model="whisper-1", **kwargs):
    """
    Transcribe an audio file-like object using Groq Whisper.
    Returns the transcribed text (string).
    """
    client = get_client()
    resp = client.audio.transcriptions.create(model=model, file=file_obj, **kwargs)
    text = getattr(resp, "text", None)
    if text is None and isinstance(resp, dict):
        text = resp.get("text") or resp.get("transcript")
    if text is None:
        logger.debug("Transcription response: %r", resp)
        raise RuntimeError("Transcription did not return text")
    return text

# -----------------------
# Amount normalization
# -----------------------
MULTIPLIERS = {
    "k": 1_000,
    "thousand": 1_000,
    "m": 1_000_000,
    "million": 1_000_000,
    "l": 100_000,      # 'L' or 'l' for lakh (India)
    "lakh": 100_000,
    "cr": 10_000_000,  # crore shorthand
    "crore": 10_000_000,
}

_amount_re = re.compile(
    r"""
    (?P<num>\d+(?:,\d{3})*(?:\.\d+)?)
    (?:\s*(?P<unit>[kKmMlL]|thousand|million|lakh|crore|cr))?
    """,
    re.VERBOSE,
)

def normalize_amount(value):
    """
    Convert a parsed amount (string or number) to float.
    Accepts: "20,000", "20k", "2 lakh", 20000, etc.
    """
    if value is None:
        raise ValueError("No amount provided")

    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    if s == "":
        raise ValueError("Empty amount string")

    s = s.replace("₹", "").replace("Rs.", "").replace("INR", "").replace("rs", "").strip()

    m = _amount_re.search(s)
    if not m:
        try:
            return float(s.replace(",", "").replace(" ", ""))
        except Exception:
            raise ValueError(f"Could not parse amount from '{value}'")

    num = m.group("num")
    unit = (m.group("unit") or "").lower()

    num_clean = num.replace(",", "").replace(" ", "")
    try:
        base = float(num_clean)
    except Exception:
        raise ValueError(f"Invalid numeric value '{num}'")

    if unit:
        multiplier = MULTIPLIERS.get(unit, 1)
        return base * multiplier

    return base

# -----------------------
# Finance text parser
# -----------------------
_amount_extract_re = re.compile(
    r"""
    (?P<amount>\d+(?:,\d{3})*(?:\.\d+)?)
    (?:\s*(?P<unit>[kKmMlL]|thousand|million|lakh|crore|cr))?
    """,
    re.VERBOSE,
)

_category_re = re.compile(
    r"(?:for|on|to|spent on|spent for)\s+([A-Za-z][A-Za-z0-9 &-]+)",
    re.IGNORECASE,
)

def parse_finance_text(text):
    """
    Parse a finance-related text and return dict with amount, category, transaction_type.
    """
    if not text:
        return {"amount": None, "category": "Other", "transaction_type": "EXPENSE"}

    text = text.strip()
    lower = text.lower()

    txn_type = "INCOME" if any(w in lower for w in ("income", "received", "salary", "credited")) else "EXPENSE"

    # Amount
    amount = None
    m = _amount_extract_re.search(text)
    if m:
        amt = m.group("amount")
        unit = m.group("unit") or ""
        amount = f"{amt}{unit}".strip()

    # Category
    cat = None
    cm = _category_re.search(text)
    if cm:
        cat = cm.group(1).strip()
    elif m:
        after = text[m.end():].strip()
        after = re.split(r"[.,;]", after)[0].strip()
        words = after.split()
        # skip leftover numeric fragments like "00"
        while words and re.match(r"^\d+$", words[0]):
            words.pop(0)
        if words:
            cat = " ".join(words[:2])
    if not cat:
        cat = "Other"

    category = cat.title()

    logger.debug("Parsed finance text: amount=%r, category=%r, type=%r", amount, category, txn_type)

    return {
        "amount": amount,
        "category": category,
        "transaction_type": txn_type,
    }
