# EAP Accuracy Status and Improvements

This document tracks the accuracy improvements and technical changes made to the Ethiopian Address Parser (EAP) to handle real-world addresses.

## Latest Accuracy Results (May 2026)

Results across all three pipeline modes after GPS coordinate corrections and subcity soft-penalty fix.

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

### Comparison to Previous Milestone (April 2026 Baseline)
*   **Overall Landmark Accuracy:** 73.9% → **77.3%** (+3.4% improvement)
*   **English Landmark Accuracy:** 74.2% → **80.6%** (+6.4% improvement)
*   **Amharic Landmark Accuracy:** 60.0% → **70.0%** (+10.0% improvement)
*   **Starting Point (Initial Baseline):** 57.1% (Total improvement: **+20.2%**)

## Technical Improvements & Commits

### Commit: `548d640`
**Title:** fix: replace hard subcity filter with 20-point penalty in landmark matching
- **Soft Subcity Penalty:** Replaced hard exclusion of cross-subcity landmarks with a −20 point score penalty. Same-subcity matches still win, but famous cross-subcity landmarks (e.g. "Mexico area Yeka", "Taitu Hotel" from Lideta) remain reachable as fallbacks.
- **Early-Exit Fix:** The exact-match early exit now only triggers when all results are full-score (≥100), preventing penalised exact matches from cutting off the fuzzy search prematurely.

### Commit: `2252477`
**Title:** fix: correct GPS coordinates for 34 landmarks using OSM Overpass data
- **Coordinate Corrections:** Updated GPS coordinates for 34 landmarks with >400m discrepancy vs OSM ground truth, including Edna Mall (2.7km off), CMC (5.3km), Sar Bet (4.1km), Gerji (2.3km), Piassa (603m), and Kazanchis (480m).
- **Merkato Subcity Fix:** Corrected Merkato subcity tag from `Kolfe Keranio` → `Addis Ketema`.
- **Root Cause:** Wrong coordinates were introduced when the landmark database was initially populated, causing incorrect subcity inference via point-in-polygon and wrong delivery GPS for couriers.

### Commit: `4efe942`
**Title:** feat: improve rule-based parsing accuracy for real-world addresses
- **Robust Chunking:** Implemented a fallback NER mechanism that splits noisy real-world addresses by delimiters (`/`, `,`, `\n`) to isolate potential landmark candidates.
- **Subcity-Constrained Matching:** Refactored `LandmarkIndex.match` to allow filtering by subcity. The parser now prioritizes landmarks within the detected subcity, preventing false positives from other areas.
- **Noise Filtering:** Added logic to remove known administrative terms and area names from landmark search queries.

### Commit: `4ffacfe`
**Title:** refactor: expand noise words to improve landmark matching precision
- **Expanded Noise List:** Added over 30 new noise words and regex patterns to filter out generic terms like "area", "building", "floor", "street", "road", and their Amharic equivalents (e.g., "አካባቢ", "ህንፃ").
- **Precision Fix:** Resolved specific false positives where "area" was incorrectly matched to "ARE Tewodros".

### Commit: `e22e63b`
**Title:** fix: resolve subcity-landmark alias conflict for major areas
- **Alias Decoupling:** Removed major landmarks (Meskel Square, Mexico, Piassa, Merkato) from subcity aliases in `subcities.json`. This prevents the parser from "stripping" these landmarks from the search text after identifying the subcity.
- **Smarter Query Building:** Refactored `_build_landmark_queries` to preserve original cleaned text even after noise removal, ensuring that high-value area names aren't lost during pre-processing.

### Commit: `15a7bf4`
**Title:** fix: handle K/Q phonetic ambiguity for Kirkos/Qirqos
- **Phonetic Normalization:** Added "Qirqos", "Qirkos", and "Kirqos" to spelling corrections and subcity aliases to handle the phonetic variation of the 'ቂ' character family.

## Current Strategy & Observations
- **Baseline vs. ML:** The Rule-Based baseline (77.3%) outperforms ML_NER (75.6%) and FULL (74.8%) on overall landmark accuracy. The ML model occasionally "over-extracts" subcity names as part of landmark spans (e.g. "ኪርቆስ ሂልተን ሆቴል" treated as one entity), which corrupts the landmark query.
- **FULL pipeline leads on English:** The semantic search layer adds value for English-only addresses (83.9% vs 80.6% baseline), but hurts Amharic (55.0% vs 70.0%) due to poor multilingual embedding quality for Ethiopic script.
- **Real-World Robustness:** The system handles cross-subcity landmark references common in real logistics data — addresses like "Mexico area Yeka" and "Merkato Lideta" now resolve correctly via soft penalty fallback.
