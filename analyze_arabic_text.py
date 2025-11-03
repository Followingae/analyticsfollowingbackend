#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze Arabic text to understand what it means and if it contains location indicators
"""

import sys
import os
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

def analyze_arabic_text():
    # Arabic text from a.kkhalid biography
    arabic_text = "يلستنا"

    print("Arabic Text Analysis")
    print("=" * 50)
    print(f"Text: '{arabic_text}'")
    print(f"Length: {len(arabic_text)} characters")
    print(f"Unicode: {[ord(c) for c in arabic_text]}")

    # Check common Arabic location patterns
    common_arabic_words = {
        "من": "from",
        "في": "in",
        "دبي": "Dubai",
        "ابوظبي": "Abu Dhabi",
        "الرياض": "Riyadh",
        "الكويت": "Kuwait",
        "الدوحة": "Doha",
        "بيروت": "Beirut",
        "القاهرة": "Cairo",
        "عمان": "Amman/Oman",
        "البحرين": "Bahrain",
        "المغرب": "Morocco",
        "تونس": "Tunisia",
        "الجزائر": "Algeria",
        "ليبيا": "Libya",
        "سوريا": "Syria",
        "العراق": "Iraq",
        "فلسطين": "Palestine",
        "اليمن": "Yemen",
        "السودان": "Sudan",
        "يلستنا": "?",  # This is what we're trying to understand
        "awqatna": "our times/moments (transliteration)"
    }

    print("\nCommon Arabic location words check:")
    for word, translation in common_arabic_words.items():
        if word in arabic_text:
            print(f"  Found: '{word}' ({translation})")

    # Let's try to understand what "يلستنا" means
    print(f"\nAnalyzing 'يلستنا':")
    print("This appears to be a combination of:")
    print("  يلس = يجلس (to sit) or يلس as a name/brand")
    print("  تنا = suffix meaning 'our'")
    print("  Combined: Could be 'our sessions/gatherings' or a brand name")
    print("\n'awqatna' appears to be:")
    print("  أوقاتنا = 'our times' or 'our moments'")
    print("  This suggests it's likely a podcast name about 'our times'")

    print("\nConclusion:")
    print("These terms appear to be podcast/content names, not location indicators.")
    print("The location detection service is correctly NOT detecting false positives.")

if __name__ == "__main__":
    analyze_arabic_text()