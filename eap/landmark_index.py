"""Landmark database with FAISS vector index for semantic matching."""

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np
from rapidfuzz import fuzz, process

from .normalizer import (
    detect_script,
    normalize_amharic,
    normalize_text,
    transliterate_to_latin,
)


@dataclass
class Landmark:
    name: str
    amharic: str
    aliases: list[str]
    category: str
    subcity: str
    lat: float
    lng: float
    # All searchable forms (populated at load time)
    search_forms: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    landmark: Landmark
    score: float
    matched_form: str
    method: str  # "exact", "fuzzy", "semantic"


class LandmarkIndex:
    """Manages landmark data and provides multiple matching strategies."""

    def __init__(self, data_dir: str = "."):
        self.data_dir = Path(data_dir)
        self.landmarks: list[Landmark] = []
        self._name_to_landmark: dict[str, Landmark] = {}
        self._all_search_forms: list[str] = []
        self._form_to_landmark: dict[str, Landmark] = {}
        # Embedding-based index (loaded lazily)
        self._embeddings: Optional[np.ndarray] = None
        self._embedding_model = None
        self._faiss_index = None

    def load(self):
        """Load landmarks from all JSON files."""
        landmark_files = [
            "addis_landmarks.json",
            "kilo_landmarks.json",
        ]
        seen_names = set()
        for fname in landmark_files:
            fpath = self.data_dir / fname
            if not fpath.exists():
                continue
            with open(fpath) as f:
                raw = json.load(f)
            for item in raw:
                name = item.get("name", "").strip()
                if not name or name.lower() in seen_names:
                    continue
                seen_names.add(name.lower())
                lm = Landmark(
                    name=name,
                    amharic=item.get("amharic", ""),
                    aliases=item.get("aliases", []),
                    category=item.get("category", ""),
                    subcity=item.get("subcity", ""),
                    lat=item.get("lat", 0.0),
                    lng=item.get("lng", 0.0),
                )
                self._build_search_forms(lm)
                self.landmarks.append(lm)
                for form in lm.search_forms:
                    self._form_to_landmark[form] = lm
                self._name_to_landmark[name.lower()] = lm

        # Also load from data/landmarks.json if it exists
        data_lm = self.data_dir / "data" / "landmarks.json"
        if data_lm.exists():
            with open(data_lm) as f:
                raw = json.load(f)
            for item in raw.get("landmarks", []):
                name = item.get("name", "").strip()
                if not name or name.lower() in seen_names:
                    continue
                seen_names.add(name.lower())
                lm = Landmark(
                    name=name,
                    amharic=item.get("amharic", ""),
                    aliases=item.get("aliases", []),
                    category=item.get("category", ""),
                    subcity=item.get("subcity", ""),
                    lat=item.get("lat", 0.0),
                    lng=item.get("lng", 0.0),
                )
                self._build_search_forms(lm)
                self.landmarks.append(lm)
                for form in lm.search_forms:
                    self._form_to_landmark[form] = lm
                self._name_to_landmark[name.lower()] = lm

        self._all_search_forms = list(self._form_to_landmark.keys())
        print(f"Loaded {len(self.landmarks)} landmarks, {len(self._all_search_forms)} search forms")

    def _build_search_forms(self, lm: Landmark):
        """Generate all searchable text forms for a landmark."""
        forms = set()
        # English name and lowercase
        forms.add(lm.name.lower())
        # Amharic name (both raw and normalized)
        if lm.amharic:
            forms.add(lm.amharic)
            forms.add(normalize_amharic(lm.amharic))
            # Transliterated form
            latin = transliterate_to_latin(lm.amharic).strip()
            if latin:
                forms.add(latin)
        # All aliases
        for alias in lm.aliases:
            forms.add(alias.lower().strip())
        # Short forms (first word if multi-word)
        words = lm.name.lower().split()
        if len(words) > 1:
            forms.add(words[0])
        lm.search_forms = [f for f in forms if f]

    def match(self, query: str, top_k: int = 5, threshold: float = 55.0) -> list[MatchResult]:
        """Match a query against the landmark database using multiple strategies.

        Strategy order:
        1. Exact match (score = 100)
        2. Fuzzy tri-gram match via rapidfuzz
        3. Semantic embedding match (if model loaded)
        """
        query = normalize_text(query).strip()
        if not query:
            return []

        results: list[MatchResult] = []
        seen_landmarks = set()

        # Prepare query forms based on script
        query_forms = [query.lower()]
        script = detect_script(query)
        if script == "ETHIOPIC":
            query_forms.append(normalize_amharic(query))
            latin = transliterate_to_latin(query).strip()
            if latin:
                query_forms.append(latin)
        elif script == "MIXED":
            query_forms.append(normalize_amharic(query))
            latin = transliterate_to_latin(query).strip()
            if latin:
                query_forms.append(latin)

        # 1. Exact match
        for qf in query_forms:
            if qf in self._form_to_landmark:
                lm = self._form_to_landmark[qf]
                if lm.name not in seen_landmarks:
                    seen_landmarks.add(lm.name)
                    results.append(MatchResult(
                        landmark=lm, score=100.0,
                        matched_form=qf, method="exact"
                    ))

        if len(results) >= top_k:
            return results[:top_k]

        # 2. Fuzzy match using rapidfuzz
        for qf in query_forms:
            matches = process.extract(
                qf,
                self._all_search_forms,
                scorer=fuzz.token_sort_ratio,
                limit=top_k * 2,
            )
            for match_str, score, _ in matches:
                if score < threshold:
                    continue
                lm = self._form_to_landmark[match_str]
                if lm.name not in seen_landmarks:
                    seen_landmarks.add(lm.name)
                    results.append(MatchResult(
                        landmark=lm, score=score,
                        matched_form=match_str, method="fuzzy"
                    ))

        # 3. Semantic match (if embeddings loaded)
        if self._faiss_index is not None:
            semantic_results = self._semantic_match(query_forms, top_k)
            for lm, score in semantic_results:
                if lm.name not in seen_landmarks:
                    seen_landmarks.add(lm.name)
                    results.append(MatchResult(
                        landmark=lm, score=score,
                        matched_form="[semantic]", method="semantic"
                    ))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:top_k]

    def build_embedding_index(self, model_name: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"):
        """Build FAISS index from landmark embeddings. Call once, reuse."""
        try:
            import faiss
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print("FAISS or sentence-transformers not installed. Skipping semantic index.")
            return

        print(f"Loading embedding model: {model_name}")
        self._embedding_model = SentenceTransformer(model_name)

        # Embed all search forms
        print(f"Encoding {len(self._all_search_forms)} search forms...")
        self._embeddings = self._embedding_model.encode(
            self._all_search_forms,
            show_progress_bar=True,
            normalize_embeddings=True,
        )

        # Build FAISS index
        dim = self._embeddings.shape[1]
        self._faiss_index = faiss.IndexFlatIP(dim)  # Inner product (cosine on normalized)
        self._faiss_index.add(self._embeddings.astype(np.float32))
        print(f"FAISS index built: {self._faiss_index.ntotal} vectors, dim={dim}")

    def _semantic_match(self, query_forms: list[str], top_k: int) -> list[tuple[Landmark, float]]:
        """Search FAISS index for semantically similar landmarks."""
        if self._embedding_model is None or self._faiss_index is None:
            return []

        query_emb = self._embedding_model.encode(
            query_forms, normalize_embeddings=True
        ).astype(np.float32)

        # Search
        scores, indices = self._faiss_index.search(query_emb, top_k)

        results = []
        seen = set()
        for i in range(len(query_forms)):
            for j in range(top_k):
                idx = indices[i][j]
                score = float(scores[i][j]) * 100  # Convert to 0-100 scale
                if idx < 0 or idx >= len(self._all_search_forms):
                    continue
                form = self._all_search_forms[idx]
                lm = self._form_to_landmark[form]
                if lm.name not in seen:
                    seen.add(lm.name)
                    results.append((lm, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
