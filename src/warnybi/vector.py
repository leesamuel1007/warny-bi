"""OpenSearch-backed RAG retrieval index operations for WARNY-BI."""

from __future__ import annotations

import json
from typing import Any

import httpx

from warnybi.config import OpenSearchSettings
from warnybi.models import QueryIntent, RagDocument, SearchHit


class OpenSearchIndex:
    """Stores and retrieves WARNY-BI documents in OpenSearch."""

    def __init__(self, settings: OpenSearchSettings) -> None:
        self.settings = settings
        self.base_url = settings.url.rstrip("/")
        self.index = settings.index
        self.client = httpx.Client(
            auth=(settings.username, settings.password) if settings.username or settings.password else None,
            timeout=30,
        )

    def ensure_index(self, vector_length: int) -> None:
        response = self.client.get(f"{self.base_url}/_cat/indices/{self.index}")
        if response.status_code == 200:
            return
        self.create_index(vector_length)

    def create_index(self, vector_length: int) -> None:
        payload = {
            "settings": {
                "index": {
                    "knn": True,
                }
            },
            "mappings": {
                "properties": {
                    "document_id": {"type": "keyword"},
                    "source_type": {"type": "keyword"},
                    "source_id": {"type": "keyword"},
                    "campaign_id": {"type": "keyword"},
                    "warning_light_id": {"type": "keyword"},
                    "warning_light_name": {"type": "text"},
                    "make": {"type": "keyword"},
                    "model": {"type": "keyword"},
                    "model_year": {"type": "integer"},
                    "component_category": {"type": "keyword"},
                    "severity": {"type": "keyword"},
                    "recommended_service_type": {"type": "keyword"},
                    "content": {"type": "text"},
                    "source_url": {"type": "keyword"},
                    "image_path": {"type": "keyword", "index": False},
                    "review_status": {"type": "keyword"},
                    "content_vector": {
                        "type": "knn_vector",
                        "dimension": vector_length,
                        "method": {
                            "name": "hnsw",
                            "space_type": "cosinesimil",
                            "engine": "lucene",
                            "parameters": {
                                "ef_construction": 128,
                                "m": 24,
                            },
                        },
                    },
                }
            }
        }
        response = self.client.put(f"{self.base_url}/{self.index}", json=payload)
        response.raise_for_status()

    def recreate_index(self, vector_length: int) -> None:
        delete = self.client.delete(f"{self.base_url}/{self.index}")
        if delete.status_code not in (200, 404):
            delete.raise_for_status()
        self.create_index(vector_length)

    def upsert_documents(self, documents: list[RagDocument], vectors: list[list[float]]) -> None:
        if not documents:
            return

        lines: list[str] = []
        for document, vector in zip(documents, vectors, strict=True):
            body = document.payload()
            body["content_vector"] = vector
            lines.append(self._jsonl_line({"index": {"_index": self.index, "_id": document.document_id}}))
            lines.append(self._jsonl_line(body))
        body_text = "\n".join(lines) + "\n"
        response = self.client.post(
            f"{self.base_url}/_bulk",
            content=body_text,
            headers={"Content-Type": "application/x-ndjson"},
        )
        response.raise_for_status()
        result = response.json()
        if result.get("errors"):
            raise RuntimeError(f"OpenSearch bulk indexing reported errors: {result}")

    def search(
        self,
        query_text: str,
        vector: list[float] | None,
        intent: QueryIntent,
        limit: int,
        include_images: bool,
    ) -> tuple[SearchHit, ...]:
        bm25_hits = self._bm25_search(query_text, intent, limit * 2, include_images)
        knn_hits = self._knn_search(vector, limit * 2, include_images) if vector else []

        merged: dict[str, dict[str, Any]] = {}
        for rank, hit in enumerate(bm25_hits, start=1):
            source = dict(hit.get("_source", {}))
            doc_id = source.get("document_id")
            if not doc_id or not self._eligible(source, intent):
                continue
            source["_bm25_rank"] = rank
            merged[doc_id] = source

        for rank, hit in enumerate(knn_hits, start=1):
            source = dict(hit.get("_source", {}))
            doc_id = source.get("document_id")
            if not doc_id or not self._eligible(source, intent):
                continue
            existing = merged.get(doc_id)
            if existing is None:
                source["_knn_rank"] = rank
                merged[doc_id] = source
            else:
                existing["_knn_rank"] = rank

        for source in merged.values():
            source["_score"] = self._rank_fusion_score(source, intent)
        ordered = sorted(merged.values(), key=lambda item: item.get("_score", 0.0), reverse=True)
        return tuple(SearchHit.from_record(item) for item in ordered[:limit])

    def _bm25_search(
        self,
        query_text: str,
        intent: QueryIntent,
        size: int,
        include_images: bool,
    ) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "_source": {"excludes": ["content_vector"]},
            "query": {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query_text,
                                "fields": [
                                    "content^4",
                                    "warning_light_name^2",
                                    "make",
                                    "model",
                                    "component_category",
                                    "source_type",
                                    "warning_light_id",
                                ],
                                "operator": "or",
                                "type": "best_fields",
                            }
                        }
                    ],
                    "should": self._intent_should_clauses(intent),
                }
            },
            "size": size,
        }
        if not include_images:
            query["post_filter"] = {"bool": {"must_not": {"exists": {"field": "image_path"}}}}
        response = self.client.post(f"{self.base_url}/{self.index}/_search", json=query)
        response.raise_for_status()
        return response.json().get("hits", {}).get("hits", [])

    def _knn_search(self, vector: list[float], size: int, include_images: bool) -> list[dict[str, Any]]:
        query: dict[str, Any] = {
            "_source": {"excludes": ["content_vector"]},
            "size": size,
            "query": {
                "knn": {
                    "content_vector": {
                        "vector": vector,
                        "k": size,
                    }
                }
            },
        }
        if not include_images:
            query["post_filter"] = {"bool": {"must_not": {"exists": {"field": "image_path"}}}}

        response = self.client.post(f"{self.base_url}/{self.index}/_search", json=query)
        response.raise_for_status()
        return response.json().get("hits", {}).get("hits", [])

    def _jsonl_line(self, value: Any) -> str:
        return json.dumps(value, ensure_ascii=False)

    def _intent_should_clauses(self, intent: QueryIntent) -> list[dict[str, Any]]:
        clauses: list[dict[str, Any]] = []
        self._add_term_boost(clauses, "warning_light_id", intent.warning_light_id, 80)
        self._add_term_boost(clauses, "component_category", intent.component_category, 35)
        return clauses

    def _add_term_boost(self, clauses: list[dict[str, Any]], field: str, value: Any, boost: int) -> None:
        if value is None or value == "":
            return
        clauses.append({"term": {field: {"value": value, "boost": boost}}})

    def _eligible(self, source: dict[str, Any], intent: QueryIntent) -> bool:
        if self._has_mismatched_value(source, "warning_light_id", intent.warning_light_id):
            return False
        if self._has_mismatched_value(source, "component_category", intent.component_category):
            return False
        if self._document_prefix(source) == "recall":
            if self._has_mismatched_value(source, "make", intent.make):
                return False
            if self._has_mismatched_value(source, "model", intent.model):
                return False
            if self._has_mismatched_value(source, "model_year", intent.model_year):
                return False
        return True

    def _rank_fusion_score(self, source: dict[str, Any], intent: QueryIntent) -> float:
        bm25_rank = self._integer(source.get("_bm25_rank"))
        knn_rank = self._integer(source.get("_knn_rank"))
        retrieval_score = self._rank_score(bm25_rank, 0.40) + self._rank_score(knn_rank, 0.25)
        metadata_score = self._metadata_score(source, intent)
        return min(max(retrieval_score + metadata_score, 0.0), 1.0)

    def _rank_score(self, rank: int | None, weight: float) -> float:
        if rank is None or rank < 1:
            return 0.0
        return weight / rank

    def _metadata_score(self, source: dict[str, Any], intent: QueryIntent) -> float:
        score = 0.0
        warning_aligned = False
        if self._field_matches(source, "warning_light_id", intent.warning_light_id):
            score += 0.20
            warning_aligned = True
        if self._field_matches(source, "warning_light_name", intent.warning_light):
            score += 0.10
            warning_aligned = True
        if self._field_matches(source, "component_category", intent.component_category):
            score += 0.15
            warning_aligned = True
        if warning_aligned:
            score += 0.04 if self._field_matches(source, "make", intent.make) else 0.0
            score += 0.04 if self._field_matches(source, "model", intent.model) else 0.0
            score += 0.02 if self._field_matches(source, "model_year", intent.model_year) else 0.0
        return score

    def _field_matches(self, source: dict[str, Any], field: str, expected: Any) -> bool:
        if expected is None or expected == "":
            return False
        actual = source.get(field)
        if actual is None or actual == "":
            return False
        return self._normalize(actual) == self._normalize(expected)

    def _has_mismatched_value(self, source: dict[str, Any], field: str, expected: Any) -> bool:
        if expected is None or expected == "":
            return False
        actual = source.get(field)
        if actual is None or actual == "":
            return False
        return self._normalize(actual) != self._normalize(expected)

    def _document_prefix(self, source: dict[str, Any]) -> str | None:
        document_id = source.get("document_id")
        if not document_id:
            return None
        text = str(document_id)
        if ":" in text:
            return text.split(":", 1)[0]
        if "-" in text:
            return text.split("-", 1)[0]
        return None

    def _integer(self, value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _normalize(self, value: Any) -> str:
        return str(value).strip().casefold()
