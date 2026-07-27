"""Validate the observability stack config (Grafana + Loki/Promtail/Prometheus).

These files are never imported, so a typo or a renamed metric goes unnoticed
until a container fails to start — or worse, silently scrapes/plots nothing — on
the server. This parses every file and cross-checks the wiring end to end:

  - every YAML / the dashboard JSON parses
  - promtail ships logs to the port Loki actually listens on
  - prometheus scrapes the backend metrics port
  - grafana datasources expose the uids the alerts reference
  - every voya_* metric used in dashboards/alerts is really exported by
    app/metrics.py (catches renamed / typo'd metrics)
  - docker-compose still mounts the provisioning files

Pure file/parse checks — no DB or running stack needed.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
LOGGING = REPO / "logging"
METRICS_PY = Path(__file__).resolve().parents[1] / "app" / "metrics.py"


def _yaml(rel: str):
    p = LOGGING / rel
    assert p.exists(), f"missing observability config: {p}"
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


# --- everything parses -------------------------------------------------------

@pytest.mark.parametrize("rel", [
    "loki-config.yaml",
    "promtail-config.yaml",
    "prometheus.yml",
    "grafana/datasources.yml",
    "grafana/dashboards/dashboards.yml",
    "grafana/alerting/hardware-alerts.yml",
    "grafana/alerting/contact-points.yml",
    "grafana/alerting/policies.yml",
])
def test_yaml_parses(rel):
    assert _yaml(rel) is not None, f"{rel} parsed to empty"


def test_dashboard_json_valid_and_has_panels():
    p = LOGGING / "grafana/dashboards/voya_system_dashboard.json"
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data.get("panels"), "dashboard JSON has no panels"


# --- wiring cross-checks -----------------------------------------------------

def test_promtail_ships_to_the_port_loki_listens_on():
    port = _yaml("loki-config.yaml")["server"]["http_listen_port"]
    urls = [c["url"] for c in _yaml("promtail-config.yaml")["clients"]]
    assert any(f":{port}/loki/api/v1/push" in u for u in urls), \
        f"promtail must push to Loki on :{port}; got {urls}"


def test_prometheus_scrapes_backend_metrics_port():
    prom = _yaml("prometheus.yml")
    targets = [
        t for job in prom["scrape_configs"]
        for sc in job.get("static_configs", []) for t in sc.get("targets", [])
    ]
    assert any(t.endswith(":8000") for t in targets), \
        f"prometheus should scrape backend:8000; got {targets}"


def test_grafana_datasources_expose_loki_and_prometheus_uids():
    uids = {d["uid"] for d in _yaml("grafana/datasources.yml")["datasources"]}
    assert {"loki", "prometheus"} <= uids, f"datasources missing uids: {uids}"


def test_alert_rules_reference_only_known_datasources():
    valid = {d["uid"] for d in _yaml("grafana/datasources.yml")["datasources"]} | {"__expr__"}
    used = set()
    for grp in _yaml("grafana/alerting/hardware-alerts.yml").get("groups", []):
        for rule in grp.get("rules", []):
            for d in rule.get("data", []):
                if d.get("datasourceUid"):
                    used.add(d["datasourceUid"])
    assert used, "no datasourceUid found in any alert rule"
    assert used <= valid, f"alerts reference unknown datasource uid(s): {sorted(used - valid)}"


# --- metric-name consistency (the highest-value check) -----------------------

def _exported_metrics() -> set[str]:
    src = METRICS_PY.read_text(encoding="utf-8")
    return set(re.findall(r"(?:Gauge|Counter|Histogram)\(\s*'(voya_[a-z_]+)'", src))


def _prometheus_job_names() -> set[str]:
    # e.g. `up{job="voya_backend"}` — a job LABEL value, not a metric name.
    return {job["job_name"] for job in _yaml("prometheus.yml")["scrape_configs"]}


def _referenced_metrics() -> set[str]:
    names: set[str] = set()
    for p in (LOGGING / "grafana").rglob("*"):
        if p.suffix in {".json", ".yml", ".yaml"}:
            names |= set(re.findall(r"\bvoya_[a-z_]+\b", p.read_text(encoding="utf-8")))
    return names - _prometheus_job_names()  # drop job labels; keep only metric names


def test_dashboards_and_alerts_only_use_exported_metrics():
    exported = _exported_metrics()
    referenced = _referenced_metrics()
    assert exported, "parsed no voya_* metrics from app/metrics.py"
    assert referenced, "parsed no voya_* metric references from grafana configs"
    missing = referenced - exported
    assert not missing, (
        f"Grafana references metrics the backend does NOT export: {sorted(missing)}. "
        f"Exported: {sorted(exported)}"
    )


# --- compose still wires the provisioning files ------------------------------

def test_compose_mounts_observability_provisioning():
    compose = yaml.safe_load((REPO / "docker-compose.yml").read_text(encoding="utf-8"))
    services = compose["services"]
    for svc in ("loki", "promtail", "prometheus", "grafana"):
        assert svc in services, f"docker-compose missing observability service: {svc}"
    grafana_vols = " ".join(services["grafana"].get("volumes", []))
    for needle in ("datasources.yml", "alerting", "dashboards"):
        assert needle in grafana_vols, f"grafana does not mount {needle}"
