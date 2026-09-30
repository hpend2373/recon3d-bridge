"""TypeSafe Jev HTTP contract; also usable with compatible local Laya servers.

No chat-completions translation or automatic truncation is performed.
See https://docs.typesafe.ai/api (checked 2026-09-30).
"""

from __future__ import annotations

import ipaddress
import json
import math
import os
import time
from collections.abc import Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


class ContractError(ValueError):
    """The request or response does not satisfy the documented wire contract."""


class APIError(RuntimeError):
    """A sanitized transport error; request content and keys are not included."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _json_value(value, field: str, *, allow_null: bool = False):
    if not isinstance(value, (str, dict, list)) and not (allow_null and value is None):
        raise ContractError(f"{field} must be text, object, or array")
    try:
        json.dumps(value, allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ContractError(f"{field} must be finite JSON") from exc


def validate_request(payload: Mapping) -> None:
    if not isinstance(payload, Mapping) or set(payload) != {"model", "state", "questions"}:
        raise ContractError("request must contain exactly model, state, questions")
    if not isinstance(payload["model"], str) or not payload["model"].strip():
        raise ContractError("model must be nonempty text")
    _json_value(payload["state"], "state")
    questions = payload["questions"]
    if not isinstance(questions, dict) or not questions:
        raise ContractError("questions must be a nonempty map")
    for qid, question in questions.items():
        if not isinstance(qid, str) or not qid:
            raise ContractError("question IDs must be nonempty strings")
        if not isinstance(question, dict):
            raise ContractError("each question must be an object")
        if set(question) - {"type", "instructions", "criteria"}:
            raise ContractError("unknown question fields")
        _json_value(question.get("instructions"), "instructions")
        kind = question.get("type")
        criteria = question.get("criteria")
        if kind == "choice":
            if not isinstance(criteria, dict) or not 2 <= len(criteria) <= 255:
                raise ContractError("choice requires 2 to 255 criteria")
            for option, description in criteria.items():
                if not isinstance(option, str) or not option:
                    raise ContractError("choice option IDs must be nonempty strings")
                _json_value(description, "choice criteria", allow_null=True)
        elif kind == "score":
            if not isinstance(criteria, list) or not 2 <= len(criteria) <= 10:
                raise ContractError("score requires 2 to 10 ordered levels")
            for level in criteria:
                _json_value(level, "score criteria")
        elif kind == "noul":
            if "criteria" in question:
                if not isinstance(criteria, dict) or set(criteria) - {"true", "false"}:
                    raise ContractError("noul criteria may contain only true and false")
                for description in criteria.values():
                    _json_value(description, "noul criteria")
        else:
            raise ContractError("question type must be noul, choice, or score")


def _number(value, field: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{field} must be numeric")
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise ContractError(f"{field} is outside its finite range")
    return value


def validate_response(response, questions: dict) -> None:
    if not isinstance(response, dict) or not isinstance(response.get("model"), str) or not response["model"]:
        raise ContractError("response is missing a resolved model")
    answers = response.get("answers")
    if not isinstance(answers, dict) or set(answers) != set(questions):
        raise ContractError("response answer IDs must match every requested question")
    usage = response.get("usage")
    if not isinstance(usage, dict):
        raise ContractError("response is missing usage")
    for field in ("input_tokens", "output_tokens"):
        value = usage.get(field)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ContractError("token usage must contain nonnegative integers")
    for qid, question in questions.items():
        answer = answers[qid]
        kind = question["type"]
        if not isinstance(answer, dict) or answer.get("type") != kind:
            raise ContractError("answer type does not match its question")
        if kind == "noul":
            _number(answer.get("noul"), "noul", 0, 1)
            continue
        keys = set(question["criteria"]) if kind == "choice" else {str(i) for i in range(len(question["criteria"]))}
        probabilities = answer.get("probabilities")
        if not isinstance(probabilities, dict) or set(probabilities) != keys:
            raise ContractError("probabilities must cover exactly the requested options/levels")
        for value in probabilities.values():
            _number(value, "probability", 0, 1)
        if not math.isclose(sum(probabilities.values()), 1, abs_tol=0.005):
            raise ContractError("probabilities do not sum to one")
        _number(answer.get("confidence"), "confidence", 0, 1)
        if kind == "choice":
            choice = answer.get("choice")
            if not isinstance(choice, str) or choice not in keys:
                raise ContractError("choice is outside the requested options")
            if probabilities[choice] < max(probabilities.values()) - 0.005:
                raise ContractError("choice is not a highest-probability option")
        else:
            _number(answer.get("score"), "score", 0, len(keys) - 1)
            legend = answer.get("legend")
            if not isinstance(legend, dict) or set(legend) != keys or not all(isinstance(x, str) for x in legend.values()):
                raise ContractError("score legend must describe every level")
            expected = sum(int(key) * value for key, value in probabilities.items())
            if not math.isclose(answer["score"], expected, abs_tol=0.02):
                raise ContractError("score disagrees with the probability-weighted levels")


class JevClient:
    """Small synchronous client that has no external Python dependencies.

    base_url includes /v1. Use explicit api_key="" for an unauthenticated
    loopback Laya server. Hosted endpoints require an API key. Only 429/529
    responses are retried; unknown transport outcomes are not resubmitted.
    """

    def __init__(self, *, base_url: str = "https://api.typesafe.ai/v1",
                 api_key: str | None = None, model: str = "jev-latest",
                 timeout: float = 30, max_retries: int = 2,
                 max_retry_delay: float = 30):
        parsed = urlsplit(base_url)
        if not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ContractError("base_url must be an HTTP(S) origin plus API path")
        loopback = parsed.hostname == "localhost"
        try:
            loopback = loopback or ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            pass
        if parsed.scheme != "https" and not (parsed.scheme == "http" and loopback):
            raise ContractError("remote API endpoints require HTTPS; HTTP is allowed on loopback")
        if timeout <= 0 or not math.isfinite(timeout) or max_retries < 0 or max_retry_delay < 0 or not math.isfinite(max_retry_delay):
            raise ContractError("invalid timeout/retry settings")
        if api_key is None:
            api_key = os.environ.get("TYPESAFE_API_KEY") or os.environ.get("JEV_API_KEY") or ""
        if not isinstance(api_key, str) or "\r" in api_key or "\n" in api_key:
            raise ContractError("API key must be single-line text")
        if not api_key and not loopback:
            raise ContractError("set TYPESAFE_API_KEY (or JEV_API_KEY) for the hosted API")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.max_retry_delay = max_retry_delay
        self._opener = build_opener(_NoRedirect())

    def _request(self, path: str, payload=None):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        headers = {"Accept": "application/json", "User-Agent": "recon3d-cross-cell-deg/1.1.0"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        for attempt in range(self.max_retries + 1):
            req = Request(self.base_url + "/" + path, data=data, headers=headers)
            try:
                with self._opener.open(req, timeout=self.timeout) as handle:
                    raw = handle.read(2_000_001)
                if len(raw) > 2_000_000:
                    raise ContractError("API response exceeds 2 MB")
                try:
                    return json.loads(raw)
                except (ValueError, UnicodeError) as exc:
                    raise ContractError("API response is not JSON") from exc
            except HTTPError as exc:
                status = exc.code
                retry_after = exc.headers.get("Retry-After")
                exc.close()
                if status not in (429, 529) or attempt == self.max_retries:
                    raise APIError(f"System One API returned HTTP {status}", status) from None
                delay = 2 ** attempt
                if retry_after:
                    try:
                        delay = max(delay, float(retry_after))
                    except ValueError:
                        pass
                if not math.isfinite(delay) or delay > self.max_retry_delay:
                    raise APIError(f"HTTP {status}: Retry-After exceeds retry delay budget", status) from None
                time.sleep(delay)
            except (URLError, TimeoutError, OSError):
                raise APIError("System One transport failed; request was not automatically resubmitted") from None

    def evaluate(self, *, state, questions: dict, model: str | None = None) -> dict:
        payload = {"model": model or self.model, "state": state, "questions": questions}
        validate_request(payload)
        response = self._request("systemone", payload)
        validate_response(response, questions)
        return response

    def list_models(self) -> dict:
        response = self._request("models")
        if not isinstance(response, dict) or not isinstance(response.get("models"), list):
            raise ContractError("models response must contain a models list")
        if not all(isinstance(x, dict) and isinstance(x.get("name"), str) for x in response["models"]):
            raise ContractError("every model entry must have a name")
        return response
