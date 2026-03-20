"""Main address parser — orchestrates NER, landmark matching, and geocoding."""

from dataclasses import dataclass, field
from typing import Optional

from .landmark_index import LandmarkIndex, MatchResult
from .ner import CombinedNER, NERResult
from .normalizer import detect_script, normalize_text, transliterate_to_latin


@dataclass
class ParsedAddress:
    """Result of parsing an Ethiopian address."""

    raw_input: str
    normalized_input: str
    script: str

    # Extracted components
    subcity: Optional[str] = None
    woreda: Optional[str] = None
    direction: Optional[str] = None

    # Resolved landmark
    landmark_name: Optional[str] = None
    landmark_amharic: Optional[str] = None
    landmark_category: Optional[str] = None
    landmark_match_score: float = 0.0
    landmark_match_method: str = ""

    # Coordinates
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Confidence
    confidence: float = 0.0
    confidence_breakdown: dict = field(default_factory=dict)

    # All landmark candidates
    candidates: list[MatchResult] = field(default_factory=list)

    # NER details
    ner_result: Optional[NERResult] = None


class EthiopianAddressParser:
    """Parse Ethiopian landmark-based addresses to structured data + GPS coordinates.

    Pipeline:
    1. Normalize input text
    2. NER: extract subcity, landmarks, directions, woreda
    3. Match extracted landmarks against the database
    4. Score confidence
    5. Return structured result with coordinates
    """

    def __init__(
        self,
        data_dir: str = ".",
        use_transformer_ner: bool = True,
        use_semantic_search: bool = False,
        transformer_model: str = "mbeukman/xlm-roberta-base-finetuned-ner-amharic",
        embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    ):
        self.data_dir = data_dir
        self.ner = CombinedNER(
            data_dir=data_dir,
            use_transformer=use_transformer_ner,
            transformer_model=transformer_model,
        )
        self.landmark_index = LandmarkIndex(data_dir=data_dir)
        self._use_semantic = use_semantic_search
        self._embedding_model = embedding_model
        self._initialized = False

    def load(self):
        """Load all data and models."""
        self.ner.load()
        self.landmark_index.load()
        if self._use_semantic:
            self.landmark_index.build_embedding_index(self._embedding_model)
        self._initialized = True

    def parse(self, address: str) -> ParsedAddress:
        """Parse an address string into structured components + coordinates."""
        if not self._initialized:
            self.load()

        normalized = normalize_text(address)
        script = detect_script(address)

        result = ParsedAddress(
            raw_input=address,
            normalized_input=normalized,
            script=script,
        )

        # Step 1: NER
        ner_result = self.ner.extract(address)
        result.ner_result = ner_result

        if ner_result.subcities:
            result.subcity = ner_result.subcities[0]
        if ner_result.woredas:
            result.woreda = ner_result.woredas[0]
        if ner_result.directions:
            result.direction = ner_result.directions[0]

        # Step 2: Build landmark queries
        # Use NER-extracted landmarks first, then fall back to full text minus known entities
        landmark_queries = self._build_landmark_queries(address, ner_result)

        # Step 3: Match against landmark database
        best_match = None
        all_candidates = []
        for query in landmark_queries:
            matches = self.landmark_index.match(query, top_k=5, threshold=50.0)
            all_candidates.extend(matches)
            if matches and (best_match is None or matches[0].score > best_match.score):
                best_match = matches[0]

        # If we have a subcity, boost matches in that subcity
        if result.subcity and all_candidates:
            for candidate in all_candidates:
                if candidate.landmark.subcity and \
                   candidate.landmark.subcity.lower() == result.subcity.lower():
                    candidate.score = min(100.0, candidate.score + 10.0)
            all_candidates.sort(key=lambda c: c.score, reverse=True)
            best_match = all_candidates[0]

        # Deduplicate candidates
        seen = set()
        unique_candidates = []
        for c in all_candidates:
            if c.landmark.name not in seen:
                seen.add(c.landmark.name)
                unique_candidates.append(c)
        result.candidates = unique_candidates[:5]

        # Step 4: Populate result
        if best_match and best_match.score >= 50.0:
            lm = best_match.landmark
            result.landmark_name = lm.name
            result.landmark_amharic = lm.amharic
            result.landmark_category = lm.category
            result.landmark_match_score = best_match.score
            result.landmark_match_method = best_match.method
            result.latitude = lm.lat
            result.longitude = lm.lng
            # If landmark has subcity info but NER didn't find one, use it
            if not result.subcity and lm.subcity:
                result.subcity = lm.subcity

        # Step 5: Confidence
        result.confidence, result.confidence_breakdown = self._calculate_confidence(result)

        return result

    def _build_landmark_queries(self, text: str, ner_result: NERResult) -> list[str]:
        """Build a list of strings to search the landmark database with."""
        queries = []

        # 1. NER-extracted landmarks (highest priority)
        for lm_text in ner_result.landmarks:
            queries.append(lm_text)

        # 2. Text with subcity/direction/woreda removed
        remaining = text
        # Remove known entity spans (sort by position descending to preserve indices)
        entity_spans = sorted(
            [(e.start, e.end) for e in ner_result.entities if e.label != "LANDMARK"],
            key=lambda x: x[0],
            reverse=True,
        )
        for start, end in entity_spans:
            if start >= 0 and end > start:
                remaining = remaining[:start] + " " + remaining[end:]
        remaining = " ".join(remaining.split()).strip()
        if remaining and remaining != text:
            queries.append(remaining)

        # 3. Full text (lowest priority)
        queries.append(text)

        # 4. Transliterated form if Ethiopic
        script = detect_script(text)
        if script in ("ETHIOPIC", "MIXED"):
            queries.append(transliterate_to_latin(text))

        return [q for q in queries if q.strip()]

    def _calculate_confidence(self, result: ParsedAddress) -> tuple[float, dict]:
        """Calculate overall confidence score (0-100)."""
        breakdown = {}
        total = 0.0

        # Subcity (25 points)
        if result.subcity:
            breakdown["subcity"] = 25.0
            total += 25.0

        # Woreda (10 points)
        if result.woreda:
            breakdown["woreda"] = 10.0
            total += 10.0

        # Landmark match (40 points, scaled by match score)
        if result.landmark_name:
            lm_score = result.landmark_match_score
            landmark_points = 40.0 * (lm_score / 100.0)
            breakdown["landmark"] = round(landmark_points, 1)
            total += landmark_points

        # Coordinates available (15 points)
        if result.latitude and result.longitude:
            breakdown["coordinates"] = 15.0
            total += 15.0

        # Direction info (5 points)
        if result.direction:
            breakdown["direction"] = 5.0
            total += 5.0

        # Consistency bonus: landmark subcity matches extracted subcity (5 points)
        if result.subcity and result.landmark_name:
            for c in result.candidates[:1]:
                if c.landmark.subcity and \
                   c.landmark.subcity.lower() == result.subcity.lower():
                    breakdown["consistency"] = 5.0
                    total += 5.0
                    break

        return round(min(100.0, total), 1), breakdown
