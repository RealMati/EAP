# EAP Accuracy Status and Improvements

This document tracks the accuracy improvements and technical changes made to the Ethiopian Address Parser (EAP) to handle real-world addresses.

## Latest Accuracy Results (April 2026)

The following results were achieved by running the baseline (rule-based) parser against the standard test suite after resolving subcity-landmark alias conflicts and phonetic ambiguities.

| Category | Subcity Accuracy | Landmark Accuracy | Avg Confidence |
| :--- | :--- | :--- | :--- |
| **English Only** | 93.5% | 90.3% | 81.8% |
| **Mixed (Amharic + English)** | 82.8% | 69.0% | 82.3% |
| **Pure Amharic** | 60.0% | 65.0% | 67.9% |
| **Transliterated** | 84.6% | 82.1% | 79.9% |
| **OVERALL** | **82.4%** | **78.2%** | **79.0%** |

### Comparison to Previous Milestone
*   **Overall Landmark Accuracy:** 70.6% → **78.2%** (+7.6% improvement)
*   **English Landmark Accuracy:** 77.4% → **90.3%** (+12.9% improvement)
*   **Transliterated Accuracy:** 71.8% → **82.1%** (+10.3% improvement)
*   **Starting Point (Initial Baseline):** 57.1% (Total improvement: **+21.1%**)

## Technical Improvements & Commits

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
- **Baseline vs. ML:** The improved Rule-Based baseline is currently outperforming the Full ML Pipeline in certain cases (70.6% vs 66.4%). This is because the ML model occasionally "over-extracts" area names as landmarks, whereas the rule-based logic now proactively filters them.
- **Real-World Robustness:** The system is now significantly more stable for noisy logistics data where addresses often contain multiple descriptors, building names, and floor numbers.
