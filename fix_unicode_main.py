#!/usr/bin/env python3
"""
Fix Unicode characters in main.py - Replace emojis with text
"""

def fix_unicode_in_main():
    """Remove all Unicode emoji characters from main.py"""
    file_path = "main.py"
    
    # Read the file
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace Unicode emojis with text
    replacements = {
        '🔍': '[SEARCH]',
        '✅': '[SUCCESS]',
        '❌': '[ERROR]',
        '💥': '[ERROR]',
        '🎉': '[SUCCESS]',
        '🎯': '[TARGET]',
        '🚀': '[TRIGGER]',
        '📸': '[CDN]',
        '⚠️': '[WARNING]',
    }
    
    for emoji, text in replacements.items():
        content = content.replace(emoji, text)
    
    # Write back to file
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("Unicode characters replaced in main.py:")
    for emoji, text in replacements.items():
        print(f"  {emoji} -> {text}")

if __name__ == "__main__":
    fix_unicode_in_main()
    print("\nUnicode fix completed!")