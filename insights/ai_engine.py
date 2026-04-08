import os
import re
import json
from groq import Groq

# =========================================================
# CONFIG
# =========================================================

ALLOWED_CATEGORIES = [
    "Food","Groceries","Travel","Rent","Income","Utilities","Entertainment",
    "Healthcare","Shopping","Electronics","Stationery","Others","Assets",
    "Losing","Prize Winning","Fitness","loan","EMI"
]

LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "llama-3.1-8b-instant")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None
CORRECTIONS_FILE = os.getenv("CORRECTIONS_FILE", "human_corrections.json")

# =========================================================
# SYSTEM PROMPT
# =========================================================
SYSTEM_PROMPT = f"""
You are an expert financial transaction classifier.

Your task:
Classify ONE transaction into EXACTLY ONE category from:

{ALLOWED_CATEGORIES}

Rules:
• Choose ONLY from the allowed categories
• Do NOT create new categories
• Do NOT add subcategories

CATEGORY DEFINITIONS
... (keep your detailed definitions here unchanged) ...
OUTPUT FORMAT (STRICT JSON ONLY)
{{
 "category": "<one of allowed categories>",
 "transaction_type": "INCOME or EXPENSE"
}}
"""

# =========================================================
# HUMAN CORRECTION STORE
# =========================================================
def _load_corrections() -> dict:
    if not os.path.exists(CORRECTIONS_FILE):
        return {}
    try:
        with open(CORRECTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_corrections(corrections: dict) -> None:
    try:
        with open(CORRECTIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(corrections, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[WARN] Could not save corrections: {e}")

def _normalize_key(text: str) -> str:
    text = text.lower()
    text = re.sub(r"(₹|rs\.?)\s*\d+(\.\d+)?", "", text)
    text = re.sub(r"\d+(\.\d+)?\s*(rs|₹)", "", text)
    text = re.sub(r"\b\d+(\.\d+)?\b", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def _check_human_correction(text_lower: str) -> dict | None:
    corrections = _load_corrections()
    if not corrections:
        return None
    input_key = _normalize_key(text_lower)
    input_words = set(input_key.split())
    for stored_key, correction in corrections.items():
        stored_words = set(stored_key.split())
        if input_key == stored_key:
            return correction
        overlap = len(stored_words & input_words) / len(stored_words)
        if overlap >= 0.70:
            return correction
    return None

# =========================================================
# SAFE JSON EXTRACTION
# =========================================================
def _extract_json(content: str):
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except Exception:
        return None

# =========================================================
# MAIN AI CLASSIFIER
# =========================================================
def predict_category(text: str):
    from datetime import date, timedelta
    from dateutil import parser as date_parser

    result = {
        "amount": None,
        "category": "Others",
        "transaction_type": "EXPENSE",
        "date": date.today(),
    }

    if not text or len(text.strip()) < 2:
        return result

    text_lower = text.lower()

    # Amount extraction
    for p in [r"₹\s*(\d+(?:\.\d+)?)", r"rs\.?\s*(\d+(?:\.\d+)?)",
              r"(\d+(?:\.\d+)?)\s*rs", r"\b(\d+(?:\.\d+)?)\b"]:
        m = re.search(p, text_lower)
        if m:
            try:
                result["amount"] = float(m.group(1))
                break
            except Exception:
                pass

    # Date extraction
    today = date.today()
    if "today" in text_lower:
        result["date"] = today
    elif "yesterday" in text_lower:
        result["date"] = today - timedelta(days=1)
    else:
        try:
            parsed = date_parser.parse(text, fuzzy=True)
            result["date"] = parsed.date()
        except Exception:
            pass

    # Human correction
    correction = _check_human_correction(text_lower)
    if correction:
        result["category"] = correction["category"]
        result["transaction_type"] = correction["transaction_type"]
        return result

    # LLM classification (main path)
    if not client:
        return result
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0,
        )
        content = response.choices[0].message.content.strip()
        data = _extract_json(content)
        if not data:
            raise ValueError("Invalid JSON")
        category = data.get("category", "Others")
        txn_type = data.get("transaction_type", "EXPENSE").upper()
        if category not in ALLOWED_CATEGORIES:
            category = "Others"
        if txn_type not in ["INCOME", "EXPENSE"]:
            txn_type = "EXPENSE"
        result["category"] = category
        result["transaction_type"] = txn_type
        return result
    except Exception:
        return result
