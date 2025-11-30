#!/usr/bin/env python3
"""Fix all emoji characters in the Post Analytics Worker"""

import re

# Read the file
with open('app/workers/post_analytics_worker.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Replace emoji characters
replacements = {
    '🚀': '[INIT]',
    '✅': '[SUCCESS]',
    '❌': '[ERROR]',
    '⚠️': '[WARNING]',
    '📊': '[ANALYTICS]',
    '🔍': '[PROCESSING]',
    '🎉': '[COMPLETE]'
}

for emoji, replacement in replacements.items():
    content = content.replace(emoji, replacement)

# Write back
with open('app/workers/post_analytics_worker.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed all emoji characters in post_analytics_worker.py")