import json
import os

filepath = "/Users/leul/Documents/Final_Project/EAP/data/landmarks.json"

with open(filepath, 'r', encoding='utf-8') as f:
    full_data = json.load(f)

data = full_data.get('landmarks', [])
print(f"Original count: {len(data)}")

import re
# Pure building numbers (123, 123-125, etc.) and building IDs (111279)
number_pattern = re.compile(r'^[0-9]+(-[0-9]+)?$')
# Street codes like BL_03_785, KR_02_203, Ar_06_1104, Gulele_02_451, Bole 2_333, Gulele _07_1304, 3_546
street_code_pattern = re.compile(r'^([A-Za-z]*\s?_?[0-9]{1,3}_[0-9]+|([A-Za-z]{2,3}|[A-Za-z][a-z])_[0-9]{2}|[A-Za-z]+ [0-9]+_[0-9]+).*$')
# Block patterns like "Block 65" or "Block65", but not prefixed with "Jemo 1 "
block_pattern = re.compile(r'^Block\s*[0-9]+$', re.IGNORECASE)

def is_code_or_number(name):
    return bool(number_pattern.match(name)) or bool(street_code_pattern.match(name)) or bool(block_pattern.match(name))

cleaned_data = [item for item in data if not is_code_or_number(item.get('name', ''))]

print(f"Cleaned count: {len(cleaned_data)}")

full_data['landmarks'] = cleaned_data

with open(filepath, 'w', encoding='utf-8') as f:
    json.dump(full_data, f, ensure_ascii=False, indent=2)
