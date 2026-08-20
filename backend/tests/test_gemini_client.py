"""The model list in models.json is a fallback chain, not a one-entry default.

An overloaded or quota-exhausted model must hand the request to the next model
rather than failing the pipeline step.
"""

import json

import pytest
from google.genai.errors import ClientError, ServerError

from backend.src.infrastructure import gemini_client as module
from backend.src.infrastructure.gemini_client import GeminiClient, suggested_delay


def api_error(cls, code, message="boom", details=None):
    payload = {"error": {"code": code, "message": message, "status": "UNAVAILABLE"}}
    if details:
        payload["error"]["details"] = details
    return cls(code, payload)


def overloaded():
    return api_error(ServerError, 503, "This model is currently experiencing high demand.")


def quota_exceeded(retry_delay=None):
    details = [{"@type": "type.googleapis.com/google.rpc.RetryInfo", "retryDelay": retry_delay}] if retry_delay else None
    return api_error(ClientError, 429, "You exceeded your current quota.", details)


@pytest.fixture(autouse=True)
def no_waiting(monkeypatch):
    """Keeps the retry policy intact but removes the sleeps from the test run."""
    monkeypatch.setattr(module, "RETRY_INITIAL_SECONDS", 0.0)
    monkeypatch.setattr(module, "MAX_BACKOFF_SECONDS", 0.0)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(GeminiClient, "_initialize_client", lambda self: object())
    monkeypatch.setattr(GeminiClient, "_load_models", lambda self: ["model-a", "model-b", "model-c"])
    return GeminiClient(api_key="test-key")


def record_calls(client, monkeypatch, behaviour):
    """Replaces the single API call with a scripted per-model behaviour."""
    calls = []

    def fake_generate_once(model, prompt, is_json):
        calls.append(model)
        outcome = behaviour(model)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(client, "_generate_once", fake_generate_once)
    return calls


def test_overloaded_model_hands_over_to_the_next_one(client, monkeypatch):
    calls = record_calls(client, monkeypatch, lambda model: overloaded() if model == "model-a" else "ok")

    assert client.generate_content("prompt") == "ok"
    assert calls[-1] == "model-b"
    # It exhausted its retries on the first model before switching.
    assert calls.count("model-a") == module.MAX_ATTEMPTS_PER_MODEL


def test_quota_exhaustion_hands_over_to_the_next_one(client, monkeypatch):
    calls = record_calls(client, monkeypatch, lambda model: quota_exceeded("2.0s") if model == "model-a" else "ok")

    assert client.generate_content("prompt") == "ok"
    assert "model-b" in calls


def test_every_model_failing_raises_the_last_error(client, monkeypatch):
    record_calls(client, monkeypatch, lambda model: overloaded())

    with pytest.raises(ServerError):
        client.generate_content("prompt")


def test_bad_request_is_not_retried_on_other_models(client, monkeypatch):
    # A malformed prompt fails identically everywhere, so re-sending it is waste.
    calls = record_calls(client, monkeypatch, lambda model: api_error(ClientError, 400, "invalid argument"))

    with pytest.raises(ClientError):
        client.generate_content("prompt")

    assert calls == ["model-a"]


def test_missing_model_falls_through_immediately(client, monkeypatch):
    calls = record_calls(
        client, monkeypatch, lambda model: api_error(ClientError, 404, "model not found") if model == "model-a" else "ok"
    )

    assert client.generate_content("prompt") == "ok"
    # 404 is not retryable, so the first model is tried exactly once.
    assert calls == ["model-a", "model-b"]


def test_explicit_model_name_disables_the_chain(monkeypatch):
    monkeypatch.setattr(GeminiClient, "_initialize_client", lambda self: object())
    client = GeminiClient(api_key="test-key", model_name="model-x")
    calls = record_calls(client, monkeypatch, lambda model: overloaded())

    with pytest.raises(ServerError):
        client.generate_content("prompt")

    assert set(calls) == {"model-x"}


def test_models_are_used_in_configured_order(tmp_path, monkeypatch):
    config = tmp_path / "models.json"
    config.write_text(json.dumps({"models": ["first", "second"]}))
    monkeypatch.setattr(GeminiClient, "_models_path", staticmethod(lambda: str(config)))
    monkeypatch.setattr(GeminiClient, "_initialize_client", lambda self: object())

    assert GeminiClient(api_key="test-key").models == ["first", "second"]


def test_unreadable_model_config_still_yields_a_model(tmp_path, monkeypatch):
    monkeypatch.setattr(GeminiClient, "_models_path", staticmethod(lambda: str(tmp_path / "missing.json")))
    monkeypatch.setattr(GeminiClient, "_initialize_client", lambda self: object())

    assert GeminiClient(api_key="test-key").models == [module.DEFAULT_MODEL]


# --- server retry hints ----------------------------------------------------

def test_suggested_delay_reads_the_servers_retry_info():
    assert suggested_delay(quota_exceeded("2.013344487s")) == pytest.approx(2.013344487)


def test_suggested_delay_falls_back_to_the_prose_hint():
    assert suggested_delay(api_error(ClientError, 429, "Please retry in 7.5s")) == pytest.approx(7.5)


def test_suggested_delay_is_absent_when_the_server_gives_no_hint():
    assert suggested_delay(overloaded()) is None
