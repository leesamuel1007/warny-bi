"""Azure Functions entrypoint for the WARNY-BI Azure bridge."""

from __future__ import annotations

import json
import logging
from typing import Any

import azure.functions as func
import httpx

from azure_bridge.azure_openai import AzureOpenAIRagClient
from azure_bridge.config import AzureBridgeConfig
from azure_bridge.normalizer import AzureRagResponseNormalizer
from azure_bridge.query_log import QueryLogRowBuilder


app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


class AzureBridgeService:
    """Coordinates Azure RAG query execution and SQL logging."""

    def __init__(self, config: AzureBridgeConfig) -> None:
        self.config = config
        self.rag_client = AzureOpenAIRagClient(
            config=config.azure_openai,
            normalizer=AzureRagResponseNormalizer(),
        )
        self.log_row_builder = QueryLogRowBuilder(config.sql_log.pipeline)

    def query(self, request_payload: dict[str, Any]) -> tuple[dict[str, Any], func.SqlRow | None, func.SqlRowList | None]:
        query = str(request_payload.get("query") or "").strip()
        if not query:
            raise ValueError("query must not be blank")
        top_k = self.optional_int(request_payload.get("top_k"))
        include_image_evidence = self.optional_bool(request_payload.get("include_image_evidence"))
        response = self.rag_client.query(
            query=query,
            top_k=top_k,
            include_image_evidence=include_image_evidence,
        )
        if not self.config.sql_log.enabled:
            response["logging_status"] = "disabled"
            response["query_id"] = None
            return response, None, None
        rows = self.log_row_builder.build(response)
        response["logging_status"] = "logged"
        response["query_id"] = rows.query_row["query_id"]
        return (
            response,
            func.SqlRow.from_dict(rows.query_row),
            func.SqlRowList([func.SqlRow.from_dict(row) for row in rows.evidence_rows]),
        )

    def optional_int(self, value: Any) -> int | None:
        if value is None:
            return None
        return int(float(str(value).strip()))

    def optional_bool(self, value: Any) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None:
            return None
        text = str(value).strip().lower()
        if text in {"true", "yes", "1"}:
            return True
        if text in {"false", "no", "0"}:
            return False
        return None


class AzureBridgeServiceFactory:
    """Builds and caches the bridge service per function worker."""

    def __init__(self) -> None:
        self.service: AzureBridgeService | None = None

    def get(self) -> AzureBridgeService:
        if self.service is None:
            self.service = AzureBridgeService(AzureBridgeConfig.from_env())
        return self.service


service_factory = AzureBridgeServiceFactory()


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    return json_response({"status": "ok", "service": "warny-bi-azure-bridge"})


@app.route(route="query", methods=["POST"])
@app.sql_output(
    arg_name="queryLog",
    command_text="[dbo].[query_log]",
    connection_string_setting="SqlConnectionString",
)
@app.sql_output(
    arg_name="queryLogEvidence",
    command_text="[dbo].[query_log_evidence]",
    connection_string_setting="SqlConnectionString",
)
def query(
    req: func.HttpRequest,
    queryLog: func.Out[func.SqlRow],
    queryLogEvidence: func.Out[func.SqlRowList],
) -> func.HttpResponse:
    try:
        payload = req.get_json()
        if not isinstance(payload, dict):
            return json_response({"error": "JSON request body must be an object"}, status_code=400)
        result, query_log_row, evidence_rows = service_factory.get().query(payload)
        if query_log_row is not None:
            queryLog.set(query_log_row)
        if evidence_rows is not None:
            queryLogEvidence.set(evidence_rows)
        return json_response(result)
    except ValueError as error:
        return json_response({"error": str(error)}, status_code=400)
    except httpx.HTTPStatusError as error:
        detail = error.response.text[:1000]
        return json_response({"error": "Azure OpenAI request failed", "detail": detail}, status_code=502)
    except Exception as error:
        logging.exception("WARNY-BI Azure bridge query failed")
        return json_response({"error": "WARNY-BI Azure bridge query failed", "detail": str(error)}, status_code=500)


def json_response(payload: dict[str, Any], status_code: int = 200) -> func.HttpResponse:
    return func.HttpResponse(
        body=json.dumps(payload, ensure_ascii=False),
        status_code=status_code,
        mimetype="application/json",
    )
