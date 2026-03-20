"""Named Entity Recognition for Ethiopian addresses.

Supports two modes:
1. Rule-based: regex + dictionary lookup (fast, no deps)
2. ML-based: XLM-RoBERTa fine-tuned on Amharic NER (accurate, needs torch)
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .normalizer import (
    AMHARIC_KEYWORDS,
    detect_script,
    normalize_amharic,
    normalize_text,
    transliterate_to_latin,
)


@dataclass
class Entity:
    text: str
    label: str  # LANDMARK, SUBCITY, WOREDA, DIRECTION, DISTANCE
    start: int
    end: int
    confidence: float = 1.0


@dataclass
class NERResult:
    entities: list[Entity] = field(default_factory=list)
    landmarks: list[str] = field(default_factory=list)
    subcities: list[str] = field(default_factory=list)
    directions: list[str] = field(default_factory=list)
    woredas: list[str] = field(default_factory=list)
    raw_text: str = ""
    normalized_text: str = ""
    script: str = ""


class RuleBasedNER:
    """Extract entities using dictionaries and regex patterns."""

    def __init__(self, data_dir: str = "."):
        self.data_dir = Path(data_dir)
        self.subcity_lookup: dict[str, str] = {}
        self.direction_lookup: dict[str, str] = {}

    def load(self):
        """Load reference data."""
        # Subcities
        sc_path = self.data_dir / "data" / "subcities.json"
        if sc_path.exists():
            with open(sc_path) as f:
                data = json.load(f)
            for sc in data.get("subcities", []):
                canonical = sc["name"]
                self.subcity_lookup[canonical.lower()] = canonical
                for alias in sc.get("aliases", []):
                    self.subcity_lookup[alias.lower()] = canonical
                amharic = sc.get("amharic", "")
                if amharic:
                    self.subcity_lookup[amharic] = canonical
                    self.subcity_lookup[normalize_amharic(amharic)] = canonical

        # Directions
        dir_path = self.data_dir / "data" / "directions.json"
        if dir_path.exists():
            with open(dir_path) as f:
                data = json.load(f)
            for d in data.get("directions", []):
                canonical = d["canonical"]
                for word in d.get("english", []):
                    self.direction_lookup[word.lower()] = canonical
                for word in d.get("amharic", []):
                    self.direction_lookup[word] = canonical
                    self.direction_lookup[normalize_amharic(word)] = canonical
                for word in d.get("transliterated", []):
                    self.direction_lookup[word.lower()] = canonical

        # Add built-in Amharic keywords
        for am, en in AMHARIC_KEYWORDS.items():
            if en in ("behind", "front", "near", "opposite", "area", "inside"):
                self.direction_lookup[am] = en
                self.direction_lookup[normalize_amharic(am)] = en

    def extract(self, text: str) -> NERResult:
        """Extract entities from address text."""
        result = NERResult(raw_text=text, script=detect_script(text))
        result.normalized_text = normalize_text(text)

        # Work with both original and normalized forms
        text_lower = text.lower()
        text_normalized = result.normalized_text

        # Extract subcities
        for key, canonical in self.subcity_lookup.items():
            if key in text_lower or key in text or key in text_normalized:
                if canonical not in result.subcities:
                    result.subcities.append(canonical)
                    pos = max(text_lower.find(key), text.find(key), text_normalized.find(key))
                    result.entities.append(Entity(
                        text=key, label="SUBCITY",
                        start=pos, end=pos + len(key),
                    ))

        # Extract directions
        for key, canonical in self.direction_lookup.items():
            if key in text_lower or key in text or key in text_normalized:
                if canonical not in result.directions:
                    result.directions.append(canonical)
                    pos = max(text_lower.find(key), text.find(key), text_normalized.find(key))
                    result.entities.append(Entity(
                        text=key, label="DIRECTION",
                        start=pos, end=pos + len(key),
                    ))

        # Extract woreda patterns
        woreda_patterns = [
            r"(?:woreda|wereda|ወሬዳ|ወረዳ)\s*(\d{1,2})",
            r"w(?:oreda|ereda)?\s*(\d{1,2})",
        ]
        for pattern in woreda_patterns:
            for m in re.finditer(pattern, text_lower):
                woreda = m.group(1)
                if woreda not in result.woredas:
                    result.woredas.append(woreda)
                    result.entities.append(Entity(
                        text=m.group(0), label="WOREDA",
                        start=m.start(), end=m.end(),
                    ))

        return result


class TransformerNER:
    """Extract entities using a fine-tuned XLM-RoBERTa model.

    Uses `mbeukman/xlm-roberta-base-finetuned-ner-amharic` by default.
    Falls back to rule-based if model can't be loaded.
    """

    def __init__(self, model_name: str = "mbeukman/xlm-roberta-base-finetuned-ner-amharic"):
        self.model_name = model_name
        self.pipeline = None
        self._loaded = False

    def load(self):
        """Load the transformer NER pipeline."""
        try:
            from transformers import pipeline
            self.pipeline = pipeline(
                "ner",
                model=self.model_name,
                aggregation_strategy="simple",
            )
            self._loaded = True
            print(f"Loaded NER model: {self.model_name}")
        except Exception as e:
            print(f"Could not load NER model ({e}). Transformer NER unavailable.")
            self._loaded = False

    @property
    def is_available(self) -> bool:
        return self._loaded and self.pipeline is not None

    def extract(self, text: str) -> list[Entity]:
        """Run transformer NER on text. Returns location entities."""
        if not self.is_available:
            return []

        results = self.pipeline(text)
        entities = []
        for r in results:
            # MasakhaNER labels: B-LOC, I-LOC, B-PER, etc.
            label = r.get("entity_group", "")
            if "LOC" in label:
                entities.append(Entity(
                    text=r["word"].strip(),
                    label="LANDMARK",
                    start=r["start"],
                    end=r["end"],
                    confidence=r["score"],
                ))
        return entities


class CombinedNER:
    """Combines rule-based and transformer NER for best results.

    Rule-based handles: subcities, directions, woredas (structured patterns)
    Transformer handles: landmark names (unstructured entities)
    """

    def __init__(self, data_dir: str = ".", use_transformer: bool = True,
                 transformer_model: str = "mbeukman/xlm-roberta-base-finetuned-ner-amharic"):
        self.rule_ner = RuleBasedNER(data_dir)
        self.transformer_ner = TransformerNER(transformer_model) if use_transformer else None

    def load(self):
        self.rule_ner.load()
        if self.transformer_ner:
            self.transformer_ner.load()

    def extract(self, text: str) -> NERResult:
        """Extract all entities from address text."""
        # Rule-based gets subcities, directions, woredas
        result = self.rule_ner.extract(text)

        # Transformer gets landmark names
        if self.transformer_ner and self.transformer_ner.is_available:
            ml_entities = self.transformer_ner.extract(text)
            for ent in ml_entities:
                # Avoid duplicating entities that rule-based already found
                overlap = False
                for existing in result.entities:
                    if (ent.start < existing.end and ent.end > existing.start):
                        overlap = True
                        break
                if not overlap:
                    result.entities.append(ent)
                    result.landmarks.append(ent.text)

        return result
