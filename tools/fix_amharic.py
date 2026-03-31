import json
import re

def is_ethiopic(text):
    return any('\u1200' <= char <= '\u137f' for char in text)

def strip_latin(text):
    # Keep Ethiopic chars, spaces, and punctuation that might be used
    cleaned = re.sub(r'[a-zA-Z0-9\(\)\|\-]+', '', text)
    # clean extra whitespace
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def fix_landmarks(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for landmark in data.get('landmarks', []):
        amharic = landmark.get('amharic', '')
        if not amharic:
            continue
            
        has_ethiopic = is_ethiopic(amharic)
        has_latin = any('a' <= char <= 'z' or 'A' <= char <= 'Z' for char in amharic)
        
        if has_ethiopic and has_latin:
            # Strip latin and see if result is good
            stripped = strip_latin(amharic)
            if stripped:
                landmark['amharic'] = stripped
            else:
                # If everything was latin and some punctuation, we might need a better strip or it was just latin
                pass
        # If it's ONLY latin (and punctuation), we should ideally translate.
        # But for now let's just mark which ones they are.

    with open(filepath + '.tmp', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    fix_landmarks('/Users/leul/Documents/Final_Project/EAP/data/landmarks.json')
