# Fix the search function in main_server.py
import re

# Read the new search logic
with open('search_logic.py', 'r', encoding='utf-8') as f:
    new_search = f.read()

# Read main_server
with open('main_server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find and replace the search_chunks_in_query function
# Find start: async def search_chunks_in_query
# Find end: next @app or async def at same indentation

pattern = r'(async def search_chunks_in_query.*?)(\n@app|\nasync def \w+|\Z)'

# Use raw string for replacement to avoid backslash issues
replacement = lambda m: new_search + m.group(2)

new_content = re.sub(pattern, replacement, content, flags=re.DOTALL | re.MULTILINE)

if new_content != content:
    with open('main_server.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("✓ Search function replaced successfully")
else:
    print("✗ No match found - pattern mismatch")
