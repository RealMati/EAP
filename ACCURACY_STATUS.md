# EAP Accuracy Status and Improvements

This document tracks accuracy across every milestone and the technical changes behind each improvement.

---

## Accuracy History by Milestone (BASELINE — Rule-based only)

All rows below are BASELINE mode. See the "Latest Results" section for ML_NER and FULL pipeline breakdowns.

> **Note:** Milestones 1–3 were measured against `addis_landmarks.json` (original smaller database).
> Milestones 4–5 use `data/landmarks.json` (consolidated, 7,911 landmarks). The database switch
> caused a temporary regression between milestones 3 and 4 before fixes were applied.

| # | Milestone | Commit(s) | English | Amharic | Mixed | Transliterated | **Overall** |
| :- | :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| 1 | Initial baseline | — | — | — | — | — | **57.1%** |
| 2 | Subcity-constrained matching + noise filtering | `4efe942` `4ffacfe` | — | — | — | — | **70.6%** |
| 3 | Alias conflict + phonetic fixes | `e22e63b` `15a7bf4` | 90.3% | 65.0% | 69.0% | 82.1% | **78.2%** |
| 4 | Database consolidation + auto-fill subcities *(regression)* | `c3a0ab4` `00f358a` | 74.2% | 60.0% | 72.4% | 82.1% | **73.9%** |
| 5 | GPS coordinate fix + soft subcity penalty | `2252477` `548d640` | 80.6% | 70.0% | 72.4% | 82.1% | **77.3%** |

---

## Latest Results — May 2026

### BASELINE (Rule-based only)

| Category | Subcity Accuracy | Landmark Accuracy | Avg Confidence |
| :--- | :--- | :--- | :--- |
| **English Only** | 96.8% | 80.6% | 86.6% |
| **Mixed (Amharic + English)** | 93.1% | 72.4% | 87.9% |
| **Pure Amharic** | 70.0% | 70.0% | 78.4% |
| **Transliterated** | 94.9% | 82.1% | 84.3% |
| **OVERALL** | **90.8%** | **77.3%** | **84.8%** |

### ML_NER (Transformer NER, no semantic search)

| Category | Subcity Accuracy | Landmark Accuracy | Avg Confidence |
| :--- | :--- | :--- | :--- |
| **English Only** | 96.8% | 80.6% | 86.6% |
| **Mixed (Amharic + English)** | 93.1% | 72.4% | 88.1% |
| **Pure Amharic** | 70.0% | 60.0% | 77.4% |
| **Transliterated** | 94.9% | 82.1% | 84.3% |
| **OVERALL** | **90.8%** | **75.6%** | **84.7%** |

### FULL (Transformer NER + Semantic Search)

| Category | Subcity Accuracy | Landmark Accuracy | Avg Confidence |
| :--- | :--- | :--- | :--- |
| **English Only** | 96.8% | 83.9% | 87.0% |
| **Mixed (Amharic + English)** | 93.1% | 69.0% | 88.0% |
| **Pure Amharic** | 70.0% | 55.0% | 77.4% |
| **Transliterated** | 94.9% | 82.1% | 85.1% |
| **OVERALL** | **90.8%** | **74.8%** | **85.0%** |

### Comparison to Previous Milestone (Milestone 4 → 5)
*   **Overall Landmark Accuracy:** 73.9% → **77.3%** (+3.4%)
*   **English Landmark Accuracy:** 74.2% → **80.6%** (+6.4%)
*   **Amharic Landmark Accuracy:** 60.0% → **70.0%** (+10.0%)
*   **Starting Point (Initial Baseline):** 57.1% (Total improvement to date: **+20.2%**)

---

## Technical Improvements & Commits

### Commit: `548d640`
**Title:** fix: replace hard subcity filter with 20-point penalty in landmark matching
- **Soft Subcity Penalty:** Replaced hard exclusion of cross-subcity landmarks with a −20 point score penalty. Same-subcity matches still win by 20 points, but famous cross-subcity landmarks (e.g. "Mexico area Yeka", "Taitu Hotel" from a Lideta address) remain reachable as fallbacks when no same-subcity match exists.
- **Early-Exit Fix:** The exact-match early exit now only triggers when all results are full-score (≥100), preventing penalised exact matches from cutting off the fuzzy search prematurely.
- **Impact:** +6.4% English, +10.0% Amharic, +3.4% Overall (BASELINE).

### Commit: `2252477`
**Title:** fix: correct GPS coordinates for 34 landmarks using OSM Overpass data
- **Coordinate Corrections:** Updated GPS coordinates for 34 landmarks with >400m discrepancy vs current OSM ground truth, including Edna Mall (2.7km off), CMC (5.3km), Sar Bet (4.1km), Gerji (2.3km), Piassa (603m), and Kazanchis (480m).
- **Merkato Subcity Fix:** Corrected Merkato subcity tag from `Kolfe Keranio` → `Addis Ketema`.
- **Root Cause:** Wrong coordinates were present in the original landmark database, causing incorrect subcity inference via point-in-polygon and wrong delivery GPS coordinates returned to couriers.
- **Impact:** Improves real-world delivery accuracy; does not affect test suite scores (which evaluate name matching, not coordinate precision).

### Commit: `00f358a` + `c3a0ab4`
**Title:** data: update landmarks with auto-filled subcities + consolidate data source
- **Database Consolidation:** Parser switched from `addis_landmarks.json` to `data/landmarks.json` (7,911 landmarks).
- **Auto-fill Subcities:** Subcity fields populated automatically via point-in-polygon against boundary polygons. Introduced a regression (78.2% → 73.9%) because the hard subcity filter became active for 95% of landmarks, blocking valid cross-subcity references.
- **Resolution:** Fixed in commits `548d640` (soft penalty) and `2252477` (corrected coordinates).

### Commit: `4efe942`
**Title:** feat: improve rule-based parsing accuracy for real-world addresses
- **Robust Chunking:** Implemented a fallback NER mechanism that splits noisy real-world addresses by delimiters (`/`, `,`, `\n`) to isolate potential landmark candidates.
- **Subcity-Constrained Matching:** Refactored `LandmarkIndex.match` to allow filtering by subcity. The parser now prioritizes landmarks within the detected subcity, preventing false positives from other areas.
- **Noise Filtering:** Added logic to remove known administrative terms and area names from landmark search queries.
- **Impact:** Overall accuracy 57.1% → 70.6% (+13.5%).

### Commit: `4ffacfe`
**Title:** refactor: expand noise words to improve landmark matching precision
- **Expanded Noise List:** Added over 30 new noise words and regex patterns to filter out generic terms like "area", "building", "floor", "street", "road", and their Amharic equivalents (e.g., "አካባቢ", "ህንፃ").
- **Precision Fix:** Resolved specific false positives where "area" was incorrectly matched to "ARE Tewodros".

### Commit: `e22e63b`
**Title:** fix: resolve subcity-landmark alias conflict for major areas
- **Alias Decoupling:** Removed major landmarks (Meskel Square, Mexico, Piassa, Merkato) from subcity aliases in `subcities.json`. This prevents the parser from "stripping" these landmarks from the search text after identifying the subcity.
- **Smarter Query Building:** Refactored `_build_landmark_queries` to preserve original cleaned text even after noise removal, ensuring that high-value area names aren't lost during pre-processing.
- **Impact:** Combined with `4ffacfe` and `15a7bf4`: overall 70.6% → 78.2% (+7.6%).

### Commit: `15a7bf4`
**Title:** fix: handle K/Q phonetic ambiguity for Kirkos/Qirqos
- **Phonetic Normalization:** Added "Qirqos", "Qirkos", and "Kirqos" to spelling corrections and subcity aliases to handle the phonetic variation of the 'ቂ' character family.

---

## Current Strategy & Observations
- **Baseline beats ML_NER overall:** Rule-Based baseline (77.3%) outperforms ML_NER (75.6%) and FULL (74.8%) on overall landmark accuracy. The ML model occasionally "over-extracts" subcity names as part of landmark spans (e.g. "ኪርቆስ ሂልተን ሆቴል" treated as one entity), which corrupts the landmark query.
- **FULL pipeline leads on English:** The semantic search layer adds value for English-only addresses (83.9% vs 80.6% baseline) but hurts Amharic (55.0% vs 70.0%) due to poor multilingual embedding quality for Ethiopic script.
- **Cross-subcity landmark references:** The soft penalty approach correctly handles addresses like "Mexico area Yeka" (Mexico is in Kirkos) and "Merkato Lideta" (Merkato is in Addis Ketema) — common patterns in real Ethiopian logistics data where people use well-known landmarks as reference points regardless of subcity boundaries.
- **Remaining gap vs. April 2026:** The English score (80.6%) is below the April 2026 measurement (90.3%), but those numbers used the old smaller `addis_landmarks.json` database and a different test distribution — not a true regression in parser logic.
