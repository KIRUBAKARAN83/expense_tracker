import os
import re
import requests # pyright: ignore[reportMissingModuleSource]

# =========================================================
# GROQ CLIENT
# =========================================================

def get_groq_headers():
    """
    Return headers for Groq API requests.
    Fails immediately if API key is missing.
    """
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set in environment variables")
    return {"Authorization": f"Bearer {api_key}"}


# =========================================================
# AUDIO TRANSCRIPTION (Groq)
# =========================================================

def transcribe_groq(file_path, lang="ta"):
    """
    Transcribe audio file using Groq transcription model.
    Supports Tamil ('ta') and English ('en').
    """
    url = os.getenv("GROQ_TRANSCRIBE_URL")
    model = os.getenv("GROQ_MODEL", "whisper-large-v3")  # default Groq Whisper model

    if not url:
        raise ValueError("GROQ_TRANSCRIBE_URL is not set in environment variables")

    headers = get_groq_headers()
    with open(file_path, "rb") as audio_file:
        files = {"file": (os.path.basename(file_path), audio_file)}
        data = {"model": model, "language": lang}
        resp = requests.post(url, headers=headers, files=files, data=data, timeout=60)
        resp.raise_for_status()
        result = resp.json()

    # Groq returns 'text' or 'transcript'
    return result.get("text") or result.get("transcript") or ""


# =========================================================
# FINANCE TEXT PARSER
# =========================================================

def parse_finance_text(text):
    """
    Extract:
    - amount
    - category
    - transaction_type

    Works for:
    - "Add 500 to groceries"
    - "Spent 200 for food"
    - "Received 1000 salary"
    - Tamil mixed speech also
    """

    if not text:
        return None

    clean_text = text.lower().strip()

    # ----------------------------
    # 1️⃣ Extract Amount
    # ----------------------------
    amount_match = re.search(r"(\d+(\.\d+)?)", clean_text)
    amount = float(amount_match.group(1)) if amount_match else None

    if not amount:
        return None   # No valid transaction

    # ----------------------------
    # 2️⃣ Determine Transaction Type
    # ----------------------------
    income_keywords = [
        "income", "received", "earned", "salary",
        "credit", "deposit", "profit"
    ]

    expense_keywords = [
        "spent", "expense", "paid", "buy",
        "purchased", "debited"
    ]

    txn_type = "EXPENSE"

    if any(word in clean_text for word in income_keywords):
        txn_type = "INCOME"
    elif any(word in clean_text for word in expense_keywords):
        txn_type = "EXPENSE"

    # ----------------------------
    # 3️⃣ Extract Category
    # ----------------------------
    category_match = re.search(
        r"(?:to|for|on)\s+([a-zA-Z]+)",
        clean_text,
        re.IGNORECASE
    )

    if category_match:
        category = category_match.group(1)
    else:
        # Fallback logic
        common_categories = [
            "food", "grocery", "rent", "fuel",
            "shopping", "travel", "entertainment",
            "salary", "investment", "medical"
        ]

        category = "Other"
        for cat in common_categories:
            if cat in clean_text:
                category = cat
                break

    return {
        "amount": amount,
        "category": category.capitalize(),
        "transaction_type": txn_type,
    }
