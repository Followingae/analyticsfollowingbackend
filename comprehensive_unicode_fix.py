#!/usr/bin/env python3
"""
Comprehensive Unicode Fix for main.py and all system files
Removes ALL problematic Unicode characters to fix Windows encoding issues
"""

import os
import re

def comprehensive_unicode_fix():
    """Fix all Unicode characters that cause Windows cp1252 encoding issues"""
    
    # Comprehensive Unicode mapping - covers ALL problematic characters
    unicode_replacements = {
        # Basic emojis we've seen
        '🔍': '[SEARCH]',
        '✅': '[SUCCESS]', 
        '❌': '[ERROR]',
        '💥': '[ERROR]',
        '🎉': '[SUCCESS]',
        '🎯': '[TARGET]',
        '🚀': '[TRIGGER]',
        '📸': '[CDN]',
        '⚠️': '[WARNING]',
        '🎬': '[PROCESS]',
        '⏱️': '[TIMEOUT]',
        '🔧': '[REPAIR]',
        '📊': '[STATS]',
        '📝': '[DOCS]',
        '⏰': '[SCHEDULE]',
        '👀': '[MONITOR]',
        '🛠️': '[TOOLS]',
        '✔️': '[CHECK]',
        '🔨': '[BUILD]',
        '⚡': '[FAST]',
        '🌐': '[NETWORK]',
        '🔑': '[AUTH]',
        '💳': '[PAYMENT]',
        '📈': '[ANALYTICS]',
        '🎨': '[VISUAL]',
        '💰': '[MONEY]',
        '🔒': '[SECURE]',
        '🆔': '[ID]',
        '📅': '[DATE]',
        '🧠': '[AI]',
        '🚫': '[BLOCKED]',
        '⭐': '[STAR]',
        '🌟': '[FEATURED]',
        '🎭': '[CONTENT]',
        '📱': '[MOBILE]',
        '💻': '[COMPUTER]',
        '🔄': '[SYNC]',
        '⏳': '[WAITING]',
        '🎪': '[EVENT]',
        '🚨': '[ALERT]',
        '📢': '[ANNOUNCE]',
        '💡': '[IDEA]',
        '🎤': '[AUDIO]',
        '🏆': '[AWARD]',
        '🎵': '[MUSIC]',
        '📍': '[LOCATION]',
        '🏠': '[HOME]',
        '📊': '[CHART]',
        
        # Unicode escape sequences that appear in errors
        '\\U0001f4e1': '[NETWORK]',  # 📡
        '\\U0001f4ca': '[ANALYTICS]', # 📊
        '\\U0001f50d': '[SEARCH]',   # 🔍
        '\\U0001f4a5': '[ERROR]',    # 💥
        '\\U0001f680': '[TRIGGER]',  # 🚀
        '\\U0001f527': '[REPAIR]',   # 🔧
        '\\U0001f512': '[SECURE]',   # 🔒
        '\\U0001f4b3': '[PAYMENT]',  # 💳
        '\\U0001f6a8': '[ALERT]',    # 🚨
        '\\U0001f504': '[SYNC]',     # 🔄
        
        # Actual Unicode characters (not escaped)
        '\U0001f4e1': '[NETWORK]',  # 📡
        '\U0001f4ca': '[ANALYTICS]', # 📊
        '\U0001f50d': '[SEARCH]',   # 🔍
        '\U0001f4a5': '[ERROR]',    # 💥
        '\U0001f680': '[TRIGGER]',  # 🚀
        '\U0001f527': '[REPAIR]',   # 🔧
        '\U0001f512': '[SECURE]',   # 🔒
        '\U0001f4b3': '[PAYMENT]',  # 💳
        '\U0001f6a8': '[ALERT]',    # 🚨
        '\U0001f504': '[SYNC]',     # 🔄
    }
    
    files_to_fix = [
        "main.py",
        "app/services/cdn_image_service.py",
        "app/workers/cdn_background_worker.py", 
        "app/tasks/cdn_processing_tasks.py",
        "app/services/cdn_queue_manager.py",
        "app/services/startup_initialization.py",
        "restart_cdn_workers.py",
        "fix_cdn_unicode.py",
        "test_complete_system_e2e.py",
        "app/services/ai/comprehensive_ai_manager.py",
        "app/services/ai/bulletproof_content_intelligence.py",
        "app/services/ai/ai_manager_singleton.py",
        "app/middleware/atomic_credit_gate.py"
    ]
    
    fixed_files = []
    
    for file_path in files_to_fix:
        if not os.path.exists(file_path):
            print(f"File not found: {file_path}")
            continue
            
        try:
            # Read the file with UTF-8 encoding
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            # Apply all Unicode replacements
            for unicode_char, replacement in unicode_replacements.items():
                content = content.replace(unicode_char, replacement)
            
            # Additional regex-based replacements for escaped Unicode
            content = re.sub(r'\\U[0-9a-fA-F]{8}', '[UNICODE]', content)
            
            # Write back to file if changed
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                fixed_files.append(file_path)
                print(f"Fixed Unicode characters in: {file_path}")
            
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    if fixed_files:
        print(f"\nFixed Unicode characters in {len(fixed_files)} files")
        print("All problematic Unicode characters replaced with text equivalents")
    else:
        print("No Unicode characters found to fix.")

if __name__ == "__main__":
    comprehensive_unicode_fix()
    print("\nComprehensive Unicode fix completed!")