"""Retrieval intent and reranking classes for WARNY-BI RAG."""

from __future__ import annotations

from dataclasses import dataclass, replace
import re

from rag_service.documents import SearchResult


@dataclass(frozen=True)
class QueryContext:
    """Free-text query plus optional structured fields from API clients."""

    query: str
    make: str | None = None
    model: str | None = None
    model_year: int | None = None
    warning_light: str | None = None
    include_image_evidence: bool = False

    def search_text(self) -> str:
        parts = [
            self.query,
            self.make or "",
            self.model or "",
            str(self.model_year) if self.model_year is not None else "",
            self.warning_light or "",
        ]
        return " ".join(part for part in parts if part).strip()


@dataclass(frozen=True)
class QueryIntent:
    """Terms extracted from a query for deterministic evidence reranking."""

    terms: frozenset[str]
    vehicle_terms: frozenset[str]
    warning_terms: frozenset[str]
    warning_categories: frozenset[str]
    years: frozenset[int]
    asks_for_recall: bool
    asks_for_image: bool


class QueryTermExtractor:
    """Extracts deterministic vehicle, warning-light, recall, and image terms."""

    def __init__(self) -> None:
        self.stop_words = frozenset(
            {
                "a",
                "an",
                "and",
                "car",
                "dashboard",
                "for",
                "in",
                "is",
                "light",
                "my",
                "of",
                "on",
                "the",
                "to",
                "vehicle",
                "warning",
                "with",
                "yellow",
                "amber",
                "red",
                "blue",
                "green",
            }
        )
        self.warning_keyword_groups = {
            "engine_emissions": frozenset({"check engine", "engine", "emission", "emissions", "malfunction", "mil"}),
            "tires_wheels": frozenset({"tire", "tires", "tyre", "tyres", "tpms", "pressure", "wheel", "wheels"}),
            "brake_abs": frozenset({"brake", "brakes", "abs", "parking brake"}),
            "airbag_srs": frozenset({"airbag", "srs", "restraint"}),
            "transmission_powertrain": frozenset({"transmission", "gearbox", "powertrain", "shift", "shifting"}),
            "suspension": frozenset({"suspension", "damper", "dampers", "control arm"}),
            "fuel": frozenset({"fuel", "gas", "range"}),
            "oil": frozenset({"oil", "lubrication"}),
            "battery_charging": frozenset({"battery", "charging", "alternator"}),
            "cooling": frozenset({"coolant", "temperature", "overheat", "overheating"}),
        }
        self.recall_terms = frozenset({"recall", "recalls", "campaign", "nhtsa"})
        self.image_terms = frozenset({"image", "images", "icon", "icons", "picture", "photo", "symbol", "uploaded", "screenshot"})

    def extract(self, context: QueryContext) -> QueryIntent:
        text = context.search_text()
        normalized = self.normalize(text)
        terms = frozenset(self.tokenize(normalized))
        years = set(self.extract_years(normalized))
        if context.model_year is not None:
            years.add(context.model_year)
        warning_categories = set(self.extract_warning_categories(normalized, terms))
        warning_terms = set(self.warning_terms_for_categories(warning_categories))
        excluded_terms = warning_terms.union(self.recall_terms).union(self.stop_words)
        vehicle_terms = frozenset(term for term in terms if term not in excluded_terms and not term.isdigit())
        return QueryIntent(
            terms=terms,
            vehicle_terms=vehicle_terms,
            warning_terms=frozenset(warning_terms),
            warning_categories=frozenset(warning_categories),
            years=frozenset(years),
            asks_for_recall=bool(terms.intersection(self.recall_terms)),
            asks_for_image=bool(terms.intersection(self.image_terms)),
        )

    def extract_warning_categories(self, normalized: str, terms: frozenset[str]) -> tuple[str, ...]:
        warning_categories: set[str] = set()
        for category, keywords in self.warning_keyword_groups.items():
            if any(self.keyword_matches(keyword, normalized, terms) for keyword in keywords):
                warning_categories.add(category)
        return tuple(warning_categories)

    def warning_terms_for_categories(self, warning_categories: set[str]) -> tuple[str, ...]:
        warning_terms: set[str] = set(warning_categories)
        for category in warning_categories:
            for keyword in self.warning_keyword_groups.get(category, ()):
                if " " not in keyword:
                    warning_terms.update(self.tokenize(keyword))
        return tuple(warning_terms)

    def keyword_matches(self, keyword: str, normalized: str, terms: frozenset[str]) -> bool:
        if " " in keyword:
            return keyword in normalized
        return keyword in terms

    def extract_years(self, normalized: str) -> tuple[int, ...]:
        years = []
        for match in re.findall(r"\b(19[8-9][0-9]|20[0-3][0-9])\b", normalized):
            years.append(int(match))
        return tuple(years)

    def normalize(self, value: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()

    def tokenize(self, value: str) -> tuple[str, ...]:
        return tuple(token for token in self.normalize(value).split() if len(token) > 1)


class SearchResultReranker:
    """Reranks vector hits using parsed context and deterministic query terms."""

    def __init__(self, term_extractor: QueryTermExtractor) -> None:
        self.term_extractor = term_extractor

    def rerank(self, context: QueryContext, results: tuple[SearchResult, ...], limit: int) -> tuple[SearchResult, ...]:
        intent = self.term_extractor.extract(context)
        ranked = tuple(self.score_result(context, intent, result) for result in results)
        sorted_results = tuple(
            sorted(
                ranked,
                key=self.sort_key,
                reverse=True,
            )
        )
        preferred_results = self.preferred_results(context, intent, sorted_results)
        return preferred_results[:limit]

    def sort_key(self, result: SearchResult) -> tuple[float, float]:
        return (
            result.rank_score if result.rank_score is not None else 0.0,
            result.score if result.score is not None else 0.0,
        )

    def preferred_results(
        self,
        context: QueryContext,
        intent: QueryIntent,
        sorted_results: tuple[SearchResult, ...],
    ) -> tuple[SearchResult, ...]:
        preferred = sorted_results
        if intent.warning_categories:
            warning_matches = tuple(
                result for result in preferred if "warning_light_mismatch" not in result.match_reasons
            )
            if warning_matches:
                preferred = warning_matches

        if self.has_structured_vehicle(context):
            vehicle_matches = tuple(
                result
                for result in preferred
                if not any(reason in result.match_reasons for reason in ("make_mismatch", "model_mismatch", "model_year_mismatch"))
            )
            if vehicle_matches:
                preferred = vehicle_matches
        if not context.include_image_evidence and not intent.asks_for_image:
            non_image_matches = tuple(result for result in preferred if not self.is_image_document(result))
            if non_image_matches:
                preferred = non_image_matches
        return preferred

    def score_result(self, context: QueryContext, intent: QueryIntent, result: SearchResult) -> SearchResult:
        score = float(result.score or 0.0)
        reasons: list[str] = []
        score = self.apply_vehicle_score(score, reasons, context, intent, result)
        score = self.apply_warning_score(score, reasons, intent, result)
        score = self.apply_recall_score(score, reasons, intent, result)
        score = self.apply_source_score(score, reasons, context, intent, result)
        return replace(result, rank_score=round(score, 6), match_reasons=tuple(reasons))

    def apply_vehicle_score(
        self,
        score: float,
        reasons: list[str],
        context: QueryContext,
        intent: QueryIntent,
        result: SearchResult,
    ) -> float:
        structured_score = self.structured_vehicle_score(context, result, reasons)
        if structured_score is not None:
            return score + structured_score

        result_vehicle_terms = frozenset(self.term_extractor.tokenize(result.vehicle_text()))
        matched_vehicle_terms = intent.vehicle_terms.intersection(result_vehicle_terms)
        if matched_vehicle_terms:
            score += min(0.18, 0.06 * len(matched_vehicle_terms))
            reasons.append(f"vehicle_terms={','.join(sorted(matched_vehicle_terms))}")
        if intent.years and result.model_year in intent.years:
            score += 0.12
            reasons.append(f"model_year={result.model_year}")
        elif intent.years and result.model_year is not None:
            score -= 0.18
            reasons.append("model_year_mismatch")
        return score

    def structured_vehicle_score(
        self,
        context: QueryContext,
        result: SearchResult,
        reasons: list[str],
    ) -> float | None:
        score = 0.0
        if not self.has_structured_vehicle(context):
            return None

        compared = False
        if context.make and result.make:
            compared = True
            if self.same_text(context.make, result.make):
                score += 0.25
                reasons.append(f"make={result.make}")
            else:
                score -= 0.55
                reasons.append("make_mismatch")
        if context.model and result.model:
            compared = True
            if self.same_text(context.model, result.model):
                score += 0.30
                reasons.append(f"model={result.model}")
            else:
                score -= 0.65
                reasons.append("model_mismatch")
        if context.model_year is not None and result.model_year is not None:
            compared = True
            if context.model_year == result.model_year:
                score += 0.20
                reasons.append(f"model_year={result.model_year}")
            else:
                score -= 0.35
                reasons.append("model_year_mismatch")

        if not compared:
            score += 0.02
            reasons.append("generic_vehicle_context")
        return score

    def has_structured_vehicle(self, context: QueryContext) -> bool:
        return any((context.make, context.model, context.model_year is not None))

    def apply_warning_score(
        self,
        score: float,
        reasons: list[str],
        intent: QueryIntent,
        result: SearchResult,
    ) -> float:
        if not intent.warning_terms:
            return score

        result_categories = self.warning_categories_for_result(result)
        matched_categories = intent.warning_categories.intersection(result_categories)
        if matched_categories:
            score += 0.45
            reasons.append(f"warning_category={','.join(sorted(matched_categories))}")
            return score

        result_warning_tokens = frozenset(
            self.term_extractor.tokenize(
                " ".join(
                    str(value)
                    for value in (result.warning_light_name, result.component_category)
                    if value is not None
                )
            )
        )
        matched_warning_terms = intent.warning_terms.intersection(result_warning_tokens)
        if matched_warning_terms:
            score += min(0.22, 0.08 * len(matched_warning_terms))
            reasons.append(f"warning_terms={','.join(sorted(matched_warning_terms))}")
        elif result.warning_light_name or result.component_category or result.recommended_service_type:
            score -= 0.90
            reasons.append("warning_light_mismatch")
        return score

    def apply_recall_score(
        self,
        score: float,
        reasons: list[str],
        intent: QueryIntent,
        result: SearchResult,
    ) -> float:
        if intent.asks_for_recall and self.is_primary_recall_document(result):
            score += 0.10
            reasons.append("recall_source")
        elif intent.asks_for_recall and self.mentions_recall(result):
            score += 0.02
            reasons.append("recall_context")
        return score

    def apply_source_score(
        self,
        score: float,
        reasons: list[str],
        context: QueryContext,
        intent: QueryIntent,
        result: SearchResult,
    ) -> float:
        if self.is_primary_recall_document(result):
            score += 0.12
            reasons.append("source_weight=recall")
        elif self.is_image_document(result):
            if context.include_image_evidence or intent.asks_for_image:
                score += 0.06
                reasons.append("source_weight=image")
            else:
                score -= 0.35
                reasons.append("image_evidence_excluded_by_default")
        elif self.is_warning_guide_document(result):
            score += 0.08
            reasons.append("source_weight=warning_guide")
        return score

    def warning_categories_for_result(self, result: SearchResult) -> frozenset[str]:
        categories = set()

        structured_text = self.term_extractor.normalize(
            " ".join(
                str(value)
                for value in (result.component_category, result.recommended_service_type)
                if value is not None
            )
        )
        structured_tokens = frozenset(self.term_extractor.tokenize(structured_text))
        for category, keywords in self.term_extractor.warning_keyword_groups.items():
            category_tokens = frozenset(self.term_extractor.tokenize(category))
            if category_tokens and category_tokens.issubset(structured_tokens):
                categories.add(category)
        if categories:
            return frozenset(categories)

        warning_name_text = self.term_extractor.normalize(result.warning_light_name or "")
        warning_name_tokens = frozenset(self.term_extractor.tokenize(warning_name_text))
        for category, keywords in self.term_extractor.warning_keyword_groups.items():
            if any(
                self.term_extractor.keyword_matches(keyword, warning_name_text, warning_name_tokens)
                for keyword in keywords
            ):
                categories.add(category)
        return frozenset(categories)

    def is_primary_recall_document(self, result: SearchResult) -> bool:
        document_id = self.term_extractor.normalize(result.document_id or "")
        source_type = self.term_extractor.normalize(result.source_type or "")
        return document_id.startswith("recall") or source_type == "nhtsa recalls api"

    def is_image_document(self, result: SearchResult) -> bool:
        document_id = self.term_extractor.normalize(result.document_id or "")
        source_type = self.term_extractor.normalize(result.source_type or "")
        return (
            document_id.startswith("image")
            or "image" in source_type.split()
            or "icon" in source_type.split()
            or bool(result.image_path)
        )

    def is_warning_guide_document(self, result: SearchResult) -> bool:
        document_id = self.term_extractor.normalize(result.document_id or "")
        source_type = self.term_extractor.normalize(result.source_type or "")
        return document_id.startswith("warning light") or "warning light guide" in source_type

    def mentions_recall(self, result: SearchResult) -> bool:
        source_text = self.term_extractor.normalize(result.source_text())
        return "recall" in source_text.split() or "nhtsa" in source_text.split()

    def same_text(self, left: str, right: str) -> bool:
        return self.term_extractor.normalize(left) == self.term_extractor.normalize(right)
