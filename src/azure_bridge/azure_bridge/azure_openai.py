"""Azure OpenAI client for the bridge function."""

from __future__ import annotations

from typing import Any

import httpx

from azure_bridge.config import AzureOpenAIConfig
from azure_bridge.normalizer import AzureRagResponseNormalizer


class AzureOpenAIRagClient:
    """Calls Azure OpenAI Chat Completions with an Azure AI Search data source."""

    def __init__(
        self,
        config: AzureOpenAIConfig,
        normalizer: AzureRagResponseNormalizer | None = None,
    ) -> None:
        self.config = config
        self.normalizer = normalizer or AzureRagResponseNormalizer()

    def query(
        self,
        query: str,
        top_k: int | None = None,
        include_image_evidence: bool | None = None,
    ) -> dict[str, Any]:
        clean_query = query.strip()
        if not clean_query:
            return self.normalizer.empty_response()
        payload = self.request_payload(clean_query, top_k, include_image_evidence)
        response = httpx.post(
            self.chat_completions_url(),
            params={"api-version": self.config.api_version},
            headers={"Content-Type": "application/json", "api-key": self.config.api_key},
            json=payload,
            timeout=self.config.timeout_seconds,
        )
        response.raise_for_status()
        return self.normalizer.normalize(clean_query, response.json())

    def chat_completions_url(self) -> str:
        endpoint = self.config.normalized_endpoint()
        deployment = self.config.chat_deployment
        return f"{endpoint}/openai/deployments/{deployment}/chat/completions"

    def request_payload(
        self,
        query: str,
        top_k: int | None,
        include_image_evidence: bool | None,
    ) -> dict[str, Any]:
        search_parameters = self.search_parameters(top_k, include_image_evidence)
        return {
            "messages": [{"role": "user", "content": query}],
            "temperature": 0,
            "data_sources": [{"type": "azure_search", "parameters": search_parameters}],
        }

    def search_parameters(
        self,
        top_k: int | None,
        include_image_evidence: bool | None,
    ) -> dict[str, Any]:
        parameters: dict[str, Any] = {
            "endpoint": self.config.normalized_search_endpoint(),
            "index_name": self.config.search_index,
            "authentication": {"type": "api_key", "key": self.config.search_key},
            "top_n_documents": top_k or self.config.top_k,
            "strictness": self.config.strictness,
            "query_type": self.config.query_type,
            "in_scope": True,
            "role_information": self.config.role_information,
        }
        if self.config.embedding_deployment:
            parameters["embedding_dependency"] = {
                "type": "deployment_name",
                "deployment_name": self.config.embedding_deployment,
            }
        if self.config.semantic_configuration:
            parameters["semantic_configuration"] = self.config.semantic_configuration
        search_filter = self.search_filter(include_image_evidence)
        if search_filter:
            parameters["filter"] = search_filter
        return parameters

    def search_filter(self, include_image_evidence: bool | None) -> str | None:
        if include_image_evidence:
            return self.config.search_filter
        return self.config.search_filter
