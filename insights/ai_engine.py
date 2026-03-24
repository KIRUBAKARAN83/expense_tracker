import os
import re
import json
from groq import Groq

# =========================================================
# CONFIG
# =========================================================

ALLOWED_CATEGORIES = [
    "Food",
    "Groceries",
    "Travel",
    "Rent",
    "Income",
    "Utilities",
    "Entertainment",
    "Healthcare",
    "Shopping",
    "Electronics",
    "Stationery",
    "Others",
    "Assets",
    "Losing",
    "Prize Winning",
    "Fitness"
    
]

LLM_MODEL = os.getenv("GROQ_LLM_MODEL", "llama-3.1-8b-instant")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Initialize client once (important for performance)
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


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

Food:
Ready-to-eat items or eating outside and all indian dishes,tamil nadu dishes.
Examples: tea, coffee, snacks, hotel, restaurant, lunch, 
dinner.

Groceries:
Food items bought for home consumption.
Examples: milk, rice, vegetables, biscuit, bread, oil, sugar.

Travel:
Transportation or movement.
Examples: petrol, fuel, taxi, bus, train, flight.

Income:
Money received.
Examples: salary, credited money, bonus, refund.

Utilities:
Recurring household bills.
Examples: electricity, water bill, internet, recharge.

Entertainment:
Leisure spending.
Examples: movie, streaming, OTT, gaming.

Healthcare:
Medical spending.
Examples: doctor, hospital, medicine.

Stationery:
Office or study supplies.
Examples: pen, pencil, notebook, diary.

Shopping:
Retail purchases not related to food.
Examples: clothes, shoes, cosmetics.

Electronics:
Electronic devices.
Examples: phone, laptop, TV, gadgets.

Rent:
Accommodation payments.
Examples: house rent, lease.

Assets:
Investment or asset purchase.
Examples: gold, stocks, mutual funds, land.

prize winning: Money won.
Examples: gambling win, lottery win, contest prize.

Fitness: Money spent on fitness ,fitness-related activities and gym equipments,
sports equipments.
Examples: gym membership, fitness equipment, sportswear,buying hockey sticks,football.

Losing:
Money lost.
Examples: gambling loss, scam loss, theft.

IMPORTANT:

• If money is received → INCOME
• Otherwise → EXPENSE
• If unclear → Others

OUTPUT FORMAT (STRICT JSON ONLY)

{{
 "category": "<one of allowed categories>",
 "transaction_type": "INCOME or EXPENSE"
}}
"""


# =========================================================
# QUICK RULE CLASSIFIER (FAST PATH)
# =========================================================

def _rule_based_prediction(text_lower: str):
    """
    Fast rule detection for high-confidence cases.
    If rule fails → return None → LLM handles it.
    """

    # Normalize
    text_lower = text_lower.lower()

    # ===============================
    # INCOME
    # ===============================
    income_keywords = [
        "salary","credited","received","bonus","refund",
        "payment received","income","earn","earned"
    ]

    if any(k in text_lower for k in income_keywords):
        return {"category": "Income", "transaction_type": "INCOME"}


    # ===============================
    # FOOD (ready-to-eat)
    # ===============================
    food_keywords = [
        "tea","coffee","snack","breakfast","lunch","dinner",
        "hotel","restaurant","meals",
        "idli","idly","dosa","vada","pongal","parotta","chapati","roti",
        "biryani","fried rice","noodles","shawarma",
        "pizza","burger","sandwich","pasta",
        "juice","cooldrink","soft drink","cake","ice cream"
    ]

    if any(k in text_lower for k in food_keywords):
        return {"category": "Food", "transaction_type": "EXPENSE"}


    # ===============================
    # GROCERIES (home food items)
    # ===============================
    grocery_keywords = [
        "milk","rice","vegetable","vegetables","onion","tomato",
        "bread","egg","oil","sugar","salt","atta","flour",
        "dal","lentils","biscuit","grocery","supermarket"
    ]

    if any(k in text_lower for k in grocery_keywords):
        return {"category": "Groceries", "transaction_type": "EXPENSE"}


    # ===============================
    # TRAVEL
    # ===============================
    travel_keywords = [
        "bus","train","metro","taxi","auto","uber","ola",
        "petrol","diesel","fuel","flight","ticket","toll"
    ]

    if any(k in text_lower for k in travel_keywords):
        return {"category": "Travel", "transaction_type": "EXPENSE"}


    # ===============================
    # SHOPPING
    # ===============================
    shopping_keywords = [
        "dress","shirt","pant","jeans","tshirt","saree",
        "shoe","shoes","watch","bag","cosmetics",
        "amazon","flipkart","shopping","clothes"
    ]

    if any(k in text_lower for k in shopping_keywords):
        return {"category": "Shopping", "transaction_type": "EXPENSE"}


    # ===============================
    # ELECTRONICS
    # ===============================
    electronics_keywords = [
        "phone","mobile","laptop","charger","earphone",
        "headphone","tv","tablet","battery","keyboard",
        "mouse","monitor","electronics"
    ]

    if any(k in text_lower for k in electronics_keywords):
        return {"category": "Electronics", "transaction_type": "EXPENSE"}


    # ===============================
    # HEALTHCARE
    # ===============================
    healthcare_keywords = [
        "doctor","hospital","clinic","medicine","tablet",
        "pharmacy","medical","treatment","scan","lab"
    ]

    if any(k in text_lower for k in healthcare_keywords):
        return {"category": "Healthcare", "transaction_type": "EXPENSE"}


    # ===============================
    # UTILITIES
    # ===============================
    utilities_keywords = [
        "electricity","current bill","water bill",
        "internet","wifi","recharge","mobile recharge",
        "gas bill"
    ]

    if any(k in text_lower for k in utilities_keywords):
        return {"category": "Utilities", "transaction_type": "EXPENSE"}
    
    fitness_keywords = [
        "gym","fitness","yoga","sportswear","dumbbell",
        "treadmill","exercise","workout","whey protein","sports equipment",
        "skipping rope","fitness tracker","parallettes","resistance band"
    ]

    if any(k in text_lower for k in fitness_keywords):
        return {"category": "Fitness", "transaction_type": "EXPENSE"}


    # ===============================
    # RENT
    # ===============================
    rent_keywords = ["rent","house rent","room rent","lease"]

    if any(k in text_lower for k in rent_keywords):
        return {"category": "Rent", "transaction_type": "EXPENSE"}


    # ===============================
    # LOSS
    # ===============================
    loss_keywords = ["lost","gambling","bet","betting","scam","theft"]

    if any(k in text_lower for k in loss_keywords):
        return {"category": "Losing", "transaction_type": "EXPENSE"}


    # ===============================
    # NOTHING MATCHED → USE LLM
    # ===============================
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
    
def extract_amount(text: str):
    """
    Extract amount from text like:
    'rs 50', '₹50', '50rs', 'spent 200', etc.
    """

    if not text:
        return None

    text = text.lower()

    patterns = [
        r"₹\s*(\d+(?:\.\d+)?)",
        r"rs\.?\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*rs",
        r"\b(\d+(?:\.\d+)?)\b"
    ]

    for p in patterns:
        match = re.search(p, text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass

    return None


# =========================================================
# MAIN AI CLASSIFIER
# =========================================================

def predict_category(text: str):
    """
    AI-powered transaction parser.

    Extracts:
    - amount
    - category
    - transaction_type
    - date
    """

    from datetime import date, timedelta
    from dateutil import parser as date_parser # pyright: ignore[reportMissingModuleSource]
    import re

    # -----------------------------------------------------
    # DEFAULT RESULT
    # -----------------------------------------------------
    result = {
        "amount": None,
        "category": "Others",
        "transaction_type": "EXPENSE",
        "date": date.today(),
    }

    if not text or len(text.strip()) < 2:
        return result

    text_lower = text.lower()

    # -----------------------------------------------------
    # 1️⃣ AMOUNT EXTRACTION
    # -----------------------------------------------------
    amount_patterns = [
        r"₹\s*(\d+(?:\.\d+)?)",
        r"rs\.?\s*(\d+(?:\.\d+)?)",
        r"(\d+(?:\.\d+)?)\s*rs",
        r"\b(\d+(?:\.\d+)?)\b"
    ]

    for p in amount_patterns:
        m = re.search(p, text_lower)
        if m:
            try:
                result["amount"] = float(m.group(1))
                break
            except Exception:
                pass

    # -----------------------------------------------------
    # 2️⃣ DATE EXTRACTION
    # -----------------------------------------------------
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

    # -----------------------------------------------------
    # 3️⃣ RULE BASED CATEGORY (FAST)
    # -----------------------------------------------------
    rule = _rule_based_prediction(text_lower)
    if rule:
        result["category"] = rule["category"]
        result["transaction_type"] = rule["transaction_type"]
        return result

    # -----------------------------------------------------
    # 4️⃣ LLM CLASSIFICATION
    # -----------------------------------------------------
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

        category = data.get("category", "Others").title()
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