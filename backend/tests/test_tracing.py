import time

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app import tracing
from app.config import settings
from app.database import SessionLocal
from app.models.audit_log import AuditLog
from app.models.execution import Execution
from app.models.script import Script
from app.services.audit_service import create_log


def _use_in_memory_tracer(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing, "_tracer", provider.get_tracer("test"))
    return exporter


def test_current_trace_id_without_span():
    assert tracing.current_trace_id() == ""


def test_job_span_records_trace_id_and_attributes(monkeypatch):
    exporter = _use_in_memory_tracer(monkeypatch)

    with tracing.job_span("script.execute", {"script.id": 1}) as span:
        span.set_attribute("execution.status", "failed")
        trace_id = tracing.current_trace_id()

    assert len(trace_id) == 32
    spans = exporter.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "script.execute"
    assert spans[0].attributes["script.id"] == 1
    assert spans[0].attributes["execution.status"] == "failed"
    assert format(spans[0].get_span_context().trace_id, "032x") == trace_id


def test_execute_script_stores_trace_id(client, auth_headers, db_session, monkeypatch):
    monkeypatch.setattr(settings, "sandbox_enabled", False)
    monkeypatch.setattr(tracing, "current_trace_id", lambda: "a" * 32)

    script = Script(name="trace-test", type="shell", content="echo hi", timeout=5, env_vars={})
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    resp = client.post(
        f"/api/v1/scripts/{script.id}/execute",
        json={"credential_ids": []},
        headers=auth_headers,
    )
    assert resp.status_code == 200

    db_session.expire_all()
    execution = db_session.query(Execution).order_by(Execution.id.desc()).first()
    assert execution is not None
    assert execution.trace_id == "a" * 32


def test_create_log_persists_trace_id(db_session):
    entry = create_log(db_session, user_id=1, username="tester", action="POST", trace_id="b" * 32)
    assert entry.trace_id == "b" * 32
    assert db_session.query(AuditLog).filter(AuditLog.id == entry.id).first().trace_id == "b" * 32


def test_audit_middleware_persists_trace_id(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "audit_enabled", True)
    monkeypatch.setattr(tracing, "current_trace_id", lambda: "c" * 32)

    resp = client.post(
        "/api/v1/notepads",
        json={"title": "trace-test", "content": "x"},
        headers=auth_headers,
    )
    assert resp.status_code in (200, 201)

    db = SessionLocal()
    try:
        entry = None
        for _ in range(30):
            entry = (
                db.query(AuditLog)
                .filter(AuditLog.action == "POST")
                .order_by(AuditLog.id.desc())
                .first()
            )
            if entry:
                break
            db.expire_all()
            time.sleep(0.1)
        assert entry is not None
        assert entry.trace_id == "c" * 32
    finally:
        db.close()


def test_system_tracing_endpoint(client, auth_headers, monkeypatch):
    resp = client.get("/api/v1/system/tracing", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"enabled": False, "ui_url": ""}

    monkeypatch.setattr(settings, "tracing_enabled", True)
    monkeypatch.setattr(settings, "tracing_ui_url", "https://jaeger.example.com")
    resp = client.get("/api/v1/system/tracing", headers=auth_headers)
    assert resp.json() == {"enabled": True, "ui_url": "https://jaeger.example.com"}

    resp = client.get("/api/v1/system/tracing")
    assert resp.status_code in (401, 403)


class _FakeSpan:
    def __init__(self):
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class _FakeRequest:
    url = "https://example.com/path?token=secret"


def test_redact_httpx_query():
    span = _FakeSpan()
    tracing._redact_httpx_query(span, _FakeRequest())

    assert span.attributes["url.full"] == "https://example.com/path"
    assert span.attributes["http.url"] == "https://example.com/path"
    assert span.attributes["url.query"] == ""
    assert "secret" not in str(span.attributes)


def test_execution_trace_id_defaults_to_empty(db_session):
    script = Script(name="trace-default", type="shell", content="echo", env_vars={})
    db_session.add(script)
    db_session.commit()
    db_session.refresh(script)

    execution = Execution(script_id=script.id)
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)

    assert execution.trace_id == ""
