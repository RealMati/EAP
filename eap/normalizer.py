"""Amharic text normalization and script utilities."""

import re
import unicodedata

# Amharic character equivalence classes (homophones)
# Multiple Ge'ez characters map to the same sound
CHAR_NORMALIZE_MAP = {
    # ha variants → ሀ
    "ሐ": "ሀ", "ሑ": "ሁ", "ሒ": "ሂ", "ሓ": "ሃ", "ሔ": "ሄ", "ሕ": "ህ", "ሖ": "ሆ",
    "ኀ": "ሀ", "ኁ": "ሁ", "ኂ": "ሂ", "ኃ": "ሃ", "ኄ": "ሄ", "ኅ": "ህ", "ኆ": "ሆ",
    # sa variants → ሰ
    "ሠ": "ሰ", "ሡ": "ሱ", "ሢ": "ሲ", "ሣ": "ሳ", "ሤ": "ሴ", "ሥ": "ስ", "ሦ": "ሶ",
    # a variants → አ
    "ዐ": "አ", "ዑ": "ኡ", "ዒ": "ኢ", "ዓ": "ኣ", "ዔ": "ኤ", "ዕ": "እ", "ዖ": "ኦ",
    # tsa variants → ጸ
    "ፀ": "ጸ", "ፁ": "ጹ", "ፂ": "ጺ", "ፃ": "ጻ", "ፄ": "ጼ", "ፅ": "ጽ", "ፆ": "ጾ",
}

# SERA-like transliteration map (Ge'ez base consonant → Latin)
# Only base forms; vowel orders follow Ge'ez pattern (ä, u, i, a, e, @, o)
SERA_CONSONANTS = {
    "ሀ": "h", "ለ": "l", "ሐ": "h", "መ": "m", "ሠ": "s", "ረ": "r", "ሰ": "s",
    "ሸ": "sh", "ቀ": "q", "ቐ": "q", "በ": "b", "ቨ": "v", "ተ": "t", "ቸ": "ch",
    "ኀ": "h", "ነ": "n", "ኘ": "ny", "አ": "", "ከ": "k", "ኸ": "kh", "ወ": "w",
    "ዐ": "", "ዘ": "z", "ዠ": "zh", "የ": "y", "ደ": "d", "ጀ": "j", "ገ": "g",
    "ጠ": "t", "ጨ": "ch", "ጰ": "p", "ጸ": "ts", "ፀ": "ts", "ፈ": "f", "ፐ": "p",
}

VOWEL_SUFFIXES = ["a", "u", "i", "a", "e", "", "o"]


def detect_script(text: str) -> str:
    """Detect whether text is ETHIOPIC, LATIN, or MIXED."""
    ethiopic = sum(1 for c in text if "\u1200" <= c <= "\u137F")
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    total = ethiopic + latin
    if total == 0:
        return "UNKNOWN"
    ratio = ethiopic / total
    if ratio > 0.7:
        return "ETHIOPIC"
    elif ratio < 0.3:
        return "LATIN"
    return "MIXED"


def normalize_amharic(text: str) -> str:
    """Normalize Amharic homophone characters to canonical forms."""
    return "".join(CHAR_NORMALIZE_MAP.get(c, c) for c in text)


def transliterate_to_latin(text: str) -> str:
    """Convert Ge'ez script to Latin approximation for cross-script matching."""
    result = []
    for char in text:
        code = ord(char)
        if 0x1200 <= code <= 0x137F:
            # Find the base consonant row and vowel order
            # Ge'ez is organized in rows of 7 (base + 6 vowel forms)
            # We iterate known base characters
            matched = False
            for base_char, latin in SERA_CONSONANTS.items():
                base_code = ord(base_char)
                offset = code - base_code
                if 0 <= offset < 7:
                    vowel = VOWEL_SUFFIXES[offset]
                    result.append(latin + vowel)
                    matched = True
                    break
            if not matched:
                result.append(char)
        elif char == " ":
            result.append(" ")
        elif char.isascii():
            result.append(char.lower())
    return "".join(result)


def strip_amharic_genitive(text: str) -> str:
    """Strip common Amharic morphological prefixes from words in an address string.

    Prefixes stripped (all require ≥2 Ethiopic chars to follow, preventing accidental roots):
      የ  (yä-)  — genitive/possessive:  የስታድየም  → ስታድየም
      ከ  (kä-)  — ablative/from:        ከቤቱ      → ቤቱ
      በ  (bä-)  — locative/in/by:       በቦሌ      → ቦሌ
      ወደ (wädä-)— directional/toward:   ወደሆቴሉ   → ሆቴሉ
      እስከ (ïskä-)— until/up to:         እስከቦሌ    → ቦሌ

    Also strips the Amharic definite article suffix -ው/-ኑ/-ቱ/-ዋ when attached to ≥3-char stems,
    since "ሆቴሉ" (the hotel) should match "ሆቴል".
    """
    # Multi-char prefixes first (order matters)
    text = re.sub(r"\bእስከ(?=[ሀ-፿]{2})", "", text)
    text = re.sub(r"\bወደ(?=[ሀ-፿]{2})", "", text)
    # Single-char prefixes
    text = re.sub(r"\b[የከበ](?=[ሀ-፿]{2})", "", text)
    # Definite suffix: -ው, -ኑ, -ቱ, -ዋ attached to Ethiopic stem of ≥3 chars
    # Strip only when the suffix character itself is Ethiopic and word is ≥4 chars total
    text = re.sub(r"([ሀ-፿]{3,})[ውኑቱዋ]\b", r"\1", text)
    return text


def normalize_latin_phonetic(text: str) -> str:
    """Collapse phonetically equivalent Latin spellings used in Ethiopian address transliteration.

    Handles the three most common c/k/q, ph/f variants so that
    "mercato" == "merkato" == "meqato" after normalization.
    Rules (applied in order, left-to-right):
      ph  → f          (phone → fone)
      c+h stays ch     (protected before the c→k rule)
      qu  → k          (queue → k, rare but exists)
      q   → k          (qirqos → kirkos)
      c   → k          (mercato → merkato, circa → kirka)
    All comparisons are case-insensitive; output is lowercase.
    """
    t = text.lower()
    t = t.replace("ph", "f")
    # Protect digraph 'ch' by temporarily substituting it
    t = t.replace("ch", "\x00")
    t = t.replace("qu", "k")
    t = t.replace("q", "k")
    t = t.replace("c", "k")
    t = t.replace("\x00", "ch")  # restore 'ch'
    return t


def normalize_text(text: str) -> str:
    """Full normalization pipeline for any input text."""
    # Unicode normalize
    text = unicodedata.normalize("NFC", text)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Normalize Amharic homophones
    text = normalize_amharic(text)
    return text


# Common Amharic spatial/directional words → English
AMHARIC_KEYWORDS = {
    "ጀርባ": "behind",
    "ኋላ": "behind",
    "ፊት": "front",
    "ፊት ለፊት": "opposite",
    "አጠገብ": "near",
    "ቅርብ": "near",
    "አካባቢ": "area",
    "ውስጥ": "inside",
    "ላይ": "on",
    "ስር": "under",
    "ቀኝ": "right",
    "ግራ": "left",
    "መንገድ": "road",
    "ጎዳና": "street",
    "ሆቴል": "hotel",
    "ቤተክርስቲያን": "church",
    "መስጊድ": "mosque",
    "ሆስፒታል": "hospital",
    "ትምህርት ቤት": "school",
    "ቤተ መንግስት": "palace",
    "አደባባይ": "square",
    "ገበያ": "market",
    "ሞል": "mall",
    "ወሬዳ": "woreda",
    "ቀበሌ": "kebele",
}
