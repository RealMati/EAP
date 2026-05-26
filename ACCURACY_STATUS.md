# EAP Accuracy Status and Improvements

This document tracks accuracy across every milestone and the technical changes behind each improvement.

---

## Accuracy History by Milestone (BASELINE — Rule-based only)

> **Note:** Milestones 1–3 were measured against `addis_landmarks.json` (original smaller database).
> Milestones 4–6 use `data/landmarks.json` (consolidated, 7,891 landmarks). The database switch
> caused a temporary regression between milestones 3 and 4 before fixes were applied.

| # | Milestone | Commit(s) | Subcity | English LM | Amharic LM | Mixed LM | Translit. LM | **Overall LM** |
| :- | :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | Initial baseline | — | — | — | — | — | — | **57.1%** |
| 2 | Subcity-constrained matching + noise filtering | `4efe942` `4ffacfe` | — | — | — | — | — | **70.6%** |
| 3 | Alias conflict + phonetic fixes | `e22e63b` `15a7bf4` | — | 90.3% | 65.0% | 69.0% | 82.1% | **78.2%** |
| 4 | Database consolidation + auto-fill subcities *(regression)* | `c3a0ab4` `00f358a` | — | 74.2% | 60.0% | 72.4% | 82.1% | **73.9%** |
| 5 | GPS coordinate fix + soft subcity penalty | `2252477` `548d640` | 90.8% | 80.6% | 70.0% | 72.4% | 82.1% | **77.3%** |
| 6 | Phonetic normalization, spelling fixes, dedup | `0ccb9ba` | **93.3%** | **90.3%** | **95.0%** | **86.2%** | **92.3%** | **90.7%** |

**Total improvement from initial baseline: 57.1% → 90.7% (+33.6%)**

---

## Latest Results — May 2026 (Milestone 6)

### BASELINE (Rule-based only — no ML, no semantic search)

| Category | Subcity Accuracy | Landmark Accuracy | Avg Confidence |
| :--- | ---: | ---: | ---: |
| **English Only** | 87.1% | 90.3% | 86.0% |
| **Transliterated Amharic** | 94.9% | 92.3% | 84.2% |
| **Mixed (Amharic + English)** | 93.1% | 86.2% | 87.6% |
| **Pure Amharic** | 100.0% | 95.0% | 77.6% |
| **OVERALL** | **93.3%** | **90.7%** | **84.4%** |

### Change vs. Milestone 5

| Metric | Milestone 5 | Milestone 6 | Δ |
| :--- | ---: | ---: | ---: |
| Overall Subcity | 90.8% | 93.3% | **+2.5%** |
| Overall Landmark | 77.3% | 90.7% | **+13.4%** |
| English Landmark | 80.6% | 90.3% | **+9.7%** |
| Amharic Landmark | 70.0% | 95.0% | **+25.0%** |
| Mixed Landmark | 72.4% | 86.2% | **+13.8%** |
| Transliterated Landmark | 82.1% | 92.3% | **+10.2%** |

---

## Technical Improvements & Commits

### Commit: `0ccb9ba` — Phonetic normalization, spelling fixes, dedup
**Accuracy: 77.3% → 90.7% landmark (+13.4%), 90.8% → 93.3% subcity (+2.5%)**

#### 1. Phonetic Latin normalization (`eap/normalizer.py`)
Added `normalize_latin_phonetic()` — collapses phonetically equivalent spellings common in Ethiopian address transliteration:
- `ph → f` (phone → fone)
- `ch` protected (kept as digraph)
- `qu → k`, `q → k`, `c → k` (mercato → merkato, qirqos → kirkos)

These forms are used for **exact matching only** (stored in a separate `_phonetic_to_landmark` dict at score 95.0), deliberately excluded from the fuzzy pool to prevent spurious `token_sort_ratio` collisions between unrelated words (e.g. "karavan hotel" matching "sharatan hotel" query).

#### 2. Two-pass landmark loading with single-word-name gate (`eap/landmark_index.py`)
Introduced a two-pass load strategy:
- **Pass 1:** Collect all single-word landmark names (e.g. "Merkato", "Bole", "Stadium").
- **Pass 2:** When adding first-word shortcuts for multi-word names, skip if the first word is already a canonical single-word landmark.

This prevents "Merkato Market" from stealing the `_form_to_landmark["merkato"]` slot away from the canonical "Merkato" entry. Only single-word names act as blockers — "Bole Medhanealem" still contributes a "bole" shortcut since "Bole" is a subcity, not a single-word landmark in the DB.

#### 3. Bulk English spelling normalization (`data/landmarks.json`)
- **49 name renames:** `Mickael` / `Mikael` / `Mika'El` / `Micheal` → `Michael`; `Medhanialem` / `MedhaneAlem` → `Medhanealem`
- **19 alias renames:** Same corrections applied to alias fields throughout the database.
- **Impact:** Fixed 10+ Michael church failures and 3+ Medhanealem church failures in a single pass.

#### 4. Amharic morphological prefix/suffix stripping (`eap/normalizer.py`)
Added `strip_amharic_genitive()` — strips common Amharic morphological affixes before landmark queries:

| Prefix/Suffix | Meaning | Example |
| :--- | :--- | :--- |
| `የ-` (yä-) | genitive/possessive | የስታድየም → ስታድየም |
| `ከ-` (kä-) | ablative/from | ከቤቱ → ቤቱ |
| `በ-` (bä-) | locative/in/by | በቦሌ → ቦሌ |
| `ወደ-` (wädä-) | directional/toward | ወደሆቴሉ → ሆቴሉ |
| `እስከ-` (ïskä-) | until/up to | እስከቦሌ → ቦሌ |
| `-ው/-ኑ/-ቱ/-ዋ` | definite suffix | ሆቴሉ → ሆቴ (the hotel) |

All prefixes require ≥2 Ethiopic characters to follow, preventing accidental root stripping on short words.

#### 5. Removed duplicate and invalid entries (`data/landmarks.json`)
- **`ቦሌ ታክሲ` deleted entirely** — not a landmark (user-flagged).
- **`ካዛንቺስ` (id=366) deleted** — structural duplicate of canonical `Kazanchis` (id=14) at identical coordinates. Its alias "Kazanchis" was overwriting the `_form_to_landmark["kazanchis"]` slot in last-write-wins order, causing queries for "Kazanchis" to return the Amharic-named duplicate instead of the canonical English entry, failing the substring match test.

#### 6. Subcity alias additions (`data/subcities.json`)
- Added `"ኮልፌ"` (Amharic) to Kolfe Keranio aliases for Amharic-script subcity detection.

#### 7. ML/transformer NER disabled by default (`eap/parser.py`)
Changed `use_transformer_ner` default from `True` to `False`. Rule-based NER is deterministic, faster, and more accurate for this domain — the transformer model was causing "black box" failures and data-scarcity degradation on Amharic text.

---

### Commit: `548d640`
**Title:** fix: replace hard subcity filter with 20-point penalty in landmark matching
- **Soft Subcity Penalty:** Replaced hard exclusion of cross-subcity landmarks with a −20 point score penalty. Same-subcity matches still win by 20 points, but famous cross-subcity landmarks remain reachable as fallbacks when no same-subcity match exists.
- **Early-Exit Fix:** The exact-match early exit now only triggers when all results are full-score (≥100), preventing penalised exact matches from cutting off the fuzzy search prematurely.
- **Impact:** +6.4% English, +10.0% Amharic, +3.4% Overall (BASELINE).

### Commit: `2252477`
**Title:** fix: correct GPS coordinates for 34 landmarks using OSM Overpass data
- **Coordinate Corrections:** Updated GPS coordinates for 34 landmarks with >400m discrepancy vs current OSM ground truth, including Edna Mall (2.7km off), CMC (5.3km), Sar Bet (4.1km), Gerji (2.3km), Piassa (603m), and Kazanchis (480m).
- **Merkato Subcity Fix:** Corrected Merkato subcity tag from `Kolfe Keranio` → `Addis Ketema`.
- **Impact:** Improves real-world delivery GPS accuracy; does not affect test suite name-matching scores.

### Commit: `00f358a` + `c3a0ab4`
**Title:** data: update landmarks with auto-filled subcities + consolidate data source
- **Database Consolidation:** Parser switched from `addis_landmarks.json` to `data/landmarks.json` (7,911 landmarks).
- **Auto-fill Subcities:** Subcity fields populated automatically via point-in-polygon against boundary polygons. Introduced a regression (78.2% → 73.9%) because the hard subcity filter became active for 95% of landmarks, blocking valid cross-subcity references.
- **Resolution:** Fixed in commits `548d640` (soft penalty) and `2252477` (corrected coordinates).

### Commit: `4efe942`
**Title:** feat: improve rule-based parsing accuracy for real-world addresses
- **Robust Chunking:** Implemented fallback NER that splits noisy addresses by delimiters (`/`, `,`, `\n`) to isolate landmark candidates.
- **Subcity-Constrained Matching:** Refactored `LandmarkIndex.match` to filter by subcity.
- **Noise Filtering:** Added logic to remove administrative terms from landmark search queries.
- **Impact:** 57.1% → 70.6% (+13.5%).

### Commit: `4ffacfe`
**Title:** refactor: expand noise words to improve landmark matching precision
- Added 30+ noise words and regex patterns for generic terms and their Amharic equivalents (አካባቢ, ህንፃ, etc.).
- Fixed false positive where "area" matched "ARE Tewodros".

### Commit: `e22e63b`
**Title:** fix: resolve subcity-landmark alias conflict for major areas
- **Alias Decoupling:** Removed major landmarks (Meskel Square, Mexico, Piassa, Merkato) from subcity aliases so the parser doesn't strip them from landmark search text.
- **Impact:** Combined with `4ffacfe` and `15a7bf4`: 70.6% → 78.2% (+7.6%).

### Commit: `15a7bf4`
**Title:** fix: handle K/Q phonetic ambiguity for Kirkos/Qirqos
- Added "Qirqos", "Qirkos", and "Kirqos" to subcity aliases to handle the phonetic variation of the ቂ character family.

---

## Known Remaining Failures

| Address | Expected | Got | Root Cause |
| :--- | :--- | :--- | :--- |
| `ሊዴታ ታይቱ ሆቴል ጀርባ` | Taitu Hotel | Tabya Hotel | Taitu is in Lideta; fuzzy "tabya" scores higher than "taitu" within subcity |
| `Merkato Lideta` | Mercato/Merkato | Merkato (72%) | Landmark IS correct; confidence drops due to subcity mismatch (Merkato=Addis Ketema, not Lideta) |
| `መስቀል square near the stadium` | Kirkos subcity | Arada | Meskel Square boundary straddles Kirkos/Arada; subcity tagging ambiguity |

---

## Architecture Notes

- **Baseline beats ML_NER:** Rule-based deterministic approach outperforms transformer NER for this domain due to Amharic data scarcity and training distribution mismatch.
- **Phonetic exact match preferred over fuzzy:** c/k/q/ph variants handled as exact matches at score 95 rather than fuzzy pool entries — avoids token_sort_ratio noise between unrelated words sharing phonetic characters.
- **Cross-subcity soft penalty:** −20 points keeps famous cross-subcity landmarks reachable (e.g. "Merkato Lideta", "Mexico Yeka") while still preferring same-subcity matches.
