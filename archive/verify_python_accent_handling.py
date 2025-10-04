#!/usr/bin/env python3
"""
Verify how Python's current UDF handles accents.
"""

import unicodedata
import re

def clean_text_aggressive(text: str) -> str:
    """Python version - exact match to manager code."""
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', text)
    text = re.sub(r'\s*[\(\[].*?[\)\]]', '', text)
    text = re.sub(r'feat(?:\.|uring)?.*', '', text, flags=re.IGNORECASE)
    text = text.lower()
    text = re.sub(r'[^\w\s]', '', text, flags=re.UNICODE)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

test_cases = [
    "Beyoncé",
    "Björk",
    "Café Tacvba",
    "Mühleisen",
]

print("Testing Python UDF accent handling:")
print("=" * 60)

for original in test_cases:
    result = clean_text_aggressive(original)
    print(f"{original:20} → {result}")

    # Check if accents were removed
    has_accent_in_result = any(unicodedata.category(c) == 'Mn' or ord(c) > 127 for c in result)
    status = "KEEPS ACCENTS" if has_accent_in_result else "REMOVES ACCENTS"
    print(f"{' '*20}   ({status})")

print("\n" + "=" * 60)
print("FINDING: Python re.sub(r'[^\\w\\s]', '', text, flags=re.UNICODE)")
print("         keeps accented letters (é, ö, ü) because:")
print("         \\w with UNICODE flag matches [a-zA-Z0-9_] + accented letters")
print("         [^\\w\\s] only removes punctuation, NOT accents")
print("=" * 60)
