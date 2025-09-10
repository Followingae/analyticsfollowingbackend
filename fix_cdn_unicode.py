#!/usr/bin/env python3
"""
Fix Unicode characters in CDN service files
"""

def fix_unicode_in_files():
    """Remove all Unicode emoji characters from CDN related files"""
    
    files_to_fix = [
        "app/services/cdn_image_service.py",
        "app/workers/cdn_background_worker.py", 
        "app/tasks/cdn_processing_tasks.py",
        "app/services/cdn_queue_manager.py",
        "app/services/startup_initialization.py",
        "restart_cdn_workers.py"
    ]
    
    # Replace Unicode emojis with text
    replacements = {
        '[SEARCH]': '[SEARCH]',
        '[SUCCESS]': '[SUCCESS]',
        '[ERROR]': '[ERROR]',
        '[ERROR]': '[ERROR]',
        '[SUCCESS]': '[SUCCESS]',
        '[TARGET]': '[TARGET]',
        '[TRIGGER]': '[TRIGGER]',
        '[CDN]': '[CDN]',
        '[WARNING]': '[WARNING]',
        '[PROCESS]': '[PROCESS]',
        '[TIMEOUT]': '[TIMEOUT]',
        '[REPAIR]': '[REPAIR]',
        '[ANALYTICS]': '[STATS]',
        '[DOCS]': '[DOCS]',
        '[SCHEDULE]': '[SCHEDULE]',
        '[MONITOR]': '[MONITOR]',
        '[TOOLS]': '[TOOLS]',
        '[CHECK]': '[CHECK]',
        '[BUILD]': '[BUILD]',
        '[FAST]': '[FAST]',
        '[NETWORK]': '[NETWORK]',
        '[AUTH]': '[AUTH]',
    }
    
    fixed_files = []
    
    for file_path in files_to_fix:
        try:
            # Read the file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            for emoji, text in replacements.items():
                content = content.replace(emoji, text)
            
            # Write back to file if changed
            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                fixed_files.append(file_path)
                print(f"Fixed Unicode characters in: {file_path}")
            
        except FileNotFoundError:
            print(f"File not found: {file_path}")
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
    
    if fixed_files:
        print(f"\nUnicode characters replaced in {len(fixed_files)} files:")
        for emoji, text in replacements.items():
            print(f"  {emoji} -> {text}")
    else:
        print("No Unicode characters found to fix.")

if __name__ == "__main__":
    fix_unicode_in_files()
    print("\nCDN Unicode fix completed!")