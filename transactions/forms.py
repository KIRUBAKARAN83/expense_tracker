from django import forms
from .models import Transaction, Budget


# ============================
# TRANSACTION FORM
# ============================
class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = ["amount", "category", "transaction_type", "date", "description"]
        widgets = {
            "amount": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "placeholder": "Enter amount"
            }),
            "category": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Optional (AI will auto-fill if empty)"
            }),
            "transaction_type": forms.Select(attrs={"class": "form-select"}),
            "date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date"
            }),
            "description": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Spoken text or note"
            }),
        }


# ============================
# BUDGET FORM
# ============================
class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ["category", "limit"]
        widgets = {
            "category": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "e.g. Food, Travel"
            }),
            "limit": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01",
                "placeholder": "Monthly limit (₹)"
            }),
        }
