"""E13.5 — Listing Experiment Agent tests (real client + connector gate +
agent logic). True ASO via ``edits.experiments`` (a real, writable
androidpublisher v3 endpoint).

Covers:
  * real_client.create_listing_experiment / list_experiments / get_experiment
    / delete_experiment (with _api_override seam) + local caps
  * connector.read_experiments (READ radius) / create_experiment (METADATA,
    three-tier gate + ownership)
  * ListingExperimentAgent build_proposal / propose / propose_title_test /
    evaluate (winner pick) / run_daily
  * experiment_audit persistence + summary_by_package + active_experiments
  * daily_briefing._run_experiment section rendering

Lean: all tests are offline (override seam / fake client), no network.
"""
from __future__ import annotations

import os

from monetization.providers.models import SandboxMode

from operation.publishing_factory.play_runtime.connector import PlayConnector
from operation.publishing_factory.play_runtime.models import GateStage
from operation.publishing_factory.play_runtime.experiment_agent import (
    ListingExperimentAgent, ExperimentPolicy, ListingExperimentProposal,
)
from operation.publishing.providers.google_play.real_client import (
    GooglePlayRealClient,
)


# --------------------------------------------------------------------- #
# fake client for the connector / agent
class FakeExperimentClient:
    def __init__(self, owned: bool = True, experiments=None,
                 create_fail=False, list_fail=False):
        self.owned = owned
        self.experiments = experiments or []
        self.create_fail = create_fail
        self.list_fail = list_fail
        self.calls: list = []

    def check_status(self, package_name):
        self.calls.append(("check_status", package_name))
        if self.owned:
            return {"success": True, "status": "published",
                    "play_status": "completed"}
        return {"success": False, "status_code": 404,
                "error": "package not found in account"}

    def list_experiments(self, package_name):
        self.calls.append(("list_experiments", package_name))
        if self.list_fail:
            return {"success": False, "status_code": 500,
                    "error": "boom", "experiments": []}
        return {"success": True, "package_name": package_name,
                "experiments": self.experiments,
                "count": len(self.experiments),
                "source": "androidpublisher.edits.experiments"}

    def create_listing_experiment(self, package_name, **kwargs):
        self.calls.append(("create", package_name, kwargs))
        if self.create_fail:
            return {"success": False, "status_code": 500, "error": "boom"}
        return {"success": True, "experiment_id": "EXP1", "edit_id": "EDIT1",
                "name": kwargs.get("name"), "locale": kwargs.get("locale"),
                "detail": "listing experiment created"}

    def get_experiment(self, package_name, experiment_id):
        self.calls.append(("get", package_name, experiment_id))
        return {"success": True, "package_name": package_name,
                "experiment_id": experiment_id, "experiment": {}}

    def delete_experiment(self, package_name, experiment_id):
        self.calls.append(("delete", package_name, experiment_id))
        return {"success": True, "experiment_id": experiment_id,
                "detail": "experiment deleted"}


PKG = "com.ofwsalary.ofwcalculator"


def _connector(sandbox, auto_pilot=False, client=None, audit_file=None,
               experiment_file=None):
    if audit_file is not None:
        os.environ["LAUNCHFORGE_PLAY_AUDIT"] = str(audit_file)
    if experiment_file is not None:
        os.environ["LAUNCHFORGE_PLAY_EXPERIMENTS"] = str(experiment_file)
    return PlayConnector(client=client or FakeExperimentClient(),
                         sandbox=sandbox, auto_pilot=auto_pilot)


def _agent(client, sandbox=SandboxMode.PRODUCTION, auto_pilot=True,
           audit_file=None, experiment_file=None):
    conn = _connector(sandbox, auto_pilot=auto_pilot, client=client,
                      audit_file=audit_file, experiment_file=experiment_file)
    return ListingExperimentAgent(conn, policy=ExperimentPolicy()), conn


# ===================================================================== #
# 1) real_client.create_listing_experiment
def test_real_client_create_experiment_override():
    c = GooglePlayRealClient(credential={"package_name": PKG})
    cap = {}

    def ov(method, path, body):
        cap.setdefault("calls", []).append((method, path))
        if method == "POST" and path.endswith("/edits"):
            return {"success": True, "status_code": 200,
                    "data": {"id": "EDIT1"}}
        if method == "POST" and "/experiments" in path:
            return {"success": True, "status_code": 200,
                    "data": {"experimentId": "EXP1"}}
        if path.endswith(":commit"):
            return {"success": True, "status_code": 200, "data": {}}
        return {"success": False, "status_code": 404, "error": "unexpected"}

    c.arm_real_client(ov)
    r = c.create_listing_experiment(
        PKG, name="ASO title test", locale="fil",
        variant_title="Ly Standard")
    assert r["success"] is True
    assert r["experiment_id"] == "EXP1"
    # open edit -> POST experiment -> commit (3 writes)
    assert cap["calls"][0][1].endswith("/edits")
    assert "/experiments" in cap["calls"][1][1]
    assert cap["calls"][2][1].endswith(":commit")


def test_real_client_create_rejects_long_name():
    c = GooglePlayRealClient(credential={"package_name": PKG})
    r = c.create_listing_experiment(PKG, name="x" * 81, locale="en-US",
                                    variant_title="Y")
    assert r["success"] is False
    assert "too long" in r["error"]


def test_real_client_create_rejects_empty_variant_title():
    c = GooglePlayRealClient(credential={"package_name": PKG})
    r = c.create_listing_experiment(PKG, name="n", locale="en-US",
                                    variant_title="   ")
    assert r["success"] is False


# ===================================================================== #
# 2) real_client.list_experiments / get_experiment / delete_experiment
def test_real_client_list_experiments_readonly():
    c = GooglePlayRealClient(credential={"package_name": PKG})
    cap = {}

    def ov(method, path, body):
        cap.setdefault("calls", []).append((method, path))
        if method == "POST" and path.endswith("/edits"):
            return {"success": True, "status_code": 200,
                    "data": {"id": "EDIT1"}}
        if method == "GET" and "/experiments" in path:
            return {"success": True, "status_code": 200,
                    "data": {"experiments": [{"experimentId": "EXP1"}]}}
        if method == "DELETE" and "/edits/" in path:
            return {"success": True, "status_code": 200, "data": {}}
        return {"success": False, "status_code": 404, "error": "unexpected"}

    c.arm_real_client(ov)
    r = c.list_experiments(PKG)
    assert r["success"] is True
    assert r["count"] == 1
    # open edit -> GET experiments -> discard edit (DELETE), no commit
    assert cap["calls"][-1][0] == "DELETE"
    assert all(not p.endswith(":commit") for _, p in cap["calls"])


def test_real_client_get_experiment():
    c = GooglePlayRealClient(credential={"package_name": PKG})

    def ov(method, path, body):
        if method == "POST" and path.endswith("/edits"):
            return {"success": True, "data": {"id": "EDIT1"}}
        if method == "GET" and "/experiments/EXP1" in path:
            return {"success": True, "data": {"experimentId": "EXP1",
                                              "name": "t"}}
        if method == "DELETE" and "/edits/" in path:
            return {"success": True, "data": {}}
        return {"success": False, "status_code": 404}

    c.arm_real_client(ov)
    r = c.get_experiment(PKG, "EXP1")
    assert r["success"] is True
    assert r["experiment"]["experimentId"] == "EXP1"


def test_real_client_delete_experiment():
    c = GooglePlayRealClient(credential={"package_name": PKG})

    def ov(method, path, body):
        if method == "POST" and path.endswith("/edits"):
            return {"success": True, "data": {"id": "EDIT1"}}
        if method == "DELETE" and "/experiments/EXP1" in path:
            return {"success": True, "status_code": 200}
        if path.endswith(":commit"):
            return {"success": True, "status_code": 200}
        return {"success": False, "status_code": 404}

    c.arm_real_client(ov)
    r = c.delete_experiment(PKG, "EXP1")
    assert r["success"] is True


# ===================================================================== #
# 3) connector.read_experiments (READ radius)
def test_connector_read_experiments_simulation(tmp_path):
    c = _connector(SandboxMode.SIMULATION, client=FakeExperimentClient(),
                   audit_file=tmp_path / "a.jsonl")
    r = c.read_experiments(PKG)
    assert r.stage == GateStage.RECOMMEND
    assert r.real_api_called is False


def test_connector_read_experiments_production(tmp_path):
    fc = FakeExperimentClient(experiments=[{"experimentId": "EXP1"}])
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.read_experiments(PKG)
    assert r.stage == GateStage.EXECUTE
    assert r.real_api_called is True
    assert r.data["count"] == 1


# ===================================================================== #
# 4) connector.create_experiment (METADATA radius, gated write)
def test_connector_create_blocked_without_autopilot(tmp_path):
    fc = FakeExperimentClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=False, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.create_experiment(PKG, name="n", locale="en-US",
                            variant_title="T", apply=True)
    assert r.stage == GateStage.BLOCKED
    assert r.real_api_called is False
    assert fc.calls == []


def test_connector_create_dry_preview(tmp_path):
    fc = FakeExperimentClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.create_experiment(PKG, name="n", locale="en-US",
                            variant_title="T", apply=False)
    assert r.stage == GateStage.SIMULATE
    assert r.real_api_called is True   # ownership verify read
    assert ("check_status", PKG) in fc.calls
    assert all(call[0] != "create" for call in fc.calls)


def test_connector_create_execute(tmp_path):
    fc = FakeExperimentClient(owned=True)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.create_experiment(PKG, name="n", locale="en-US",
                            variant_title="T", apply=True)
    assert r.stage == GateStage.EXECUTE
    assert r.ok is True
    assert ("create", PKG, {}) in [(c[0], c[1], {}) for c in fc.calls
                                   if c[0] == "create"]


def test_connector_create_non_owned_refused(tmp_path):
    fc = FakeExperimentClient(owned=False)
    c = _connector(SandboxMode.PRODUCTION, auto_pilot=True, client=fc,
                   audit_file=tmp_path / "a.jsonl")
    r = c.create_experiment(PKG, name="n", locale="en-US",
                            variant_title="T", apply=True)
    assert r.stage == GateStage.EXECUTE
    assert r.ok is False
    assert all(call[0] != "create" for call in fc.calls)


# ===================================================================== #
# 5) ListingExperimentAgent build_proposal + propose
def test_build_proposal_validates():
    a, _ = _agent(FakeExperimentClient())
    p = a.build_proposal(PKG, name="ASO fil", locale="fil",
                         variant_title="Ly Std")
    assert p.status == "proposed"
    assert p.variant_title == "Ly Std"
    # bad title length
    try:
        a.build_proposal(PKG, name="n", locale="en-US",
                         variant_title="x" * 51)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_propose_title_test_routes_to_connector(tmp_path):
    fc = FakeExperimentClient(owned=True)
    a, _ = _agent(fc, sandbox=SandboxMode.PRODUCTION, auto_pilot=True,
                  audit_file=tmp_path / "a.jsonl",
                  experiment_file=tmp_path / "exp.jsonl")
    res = a.propose_title_test(PKG, "fil", "Ly Standard", apply=True)
    assert res.stage == GateStage.EXECUTE
    assert res.ok is True
    # connector forwarded the variant title to the real client
    create_call = next(c for c in fc.calls if c[0] == "create")
    assert create_call[2]["variant_title"] == "Ly Standard"
    assert create_call[2]["locale"] == "fil"


def test_propose_preview_no_write(tmp_path):
    fc = FakeExperimentClient(owned=True)
    a, _ = _agent(fc, sandbox=SandboxMode.PRODUCTION, auto_pilot=True,
                  audit_file=tmp_path / "a.jsonl",
                  experiment_file=tmp_path / "exp.jsonl")
    res = a.propose(PKG, name="n", locale="en-US", variant_title="T",
                    apply=False)
    assert res.stage == GateStage.SIMULATE
    assert all(call[0] != "create" for call in fc.calls)


# ===================================================================== #
# 6) evaluate winner pick + run_daily
_ENDED_WIN = {
    "experimentId": "EXP1", "name": "title test", "status": "ENDED",
    "userFraction": 0.1,
    "variants": [
        {"id": "default",
         "storeListing": {"languageCode": "en-US", "title": "A"},
         "results": {"conversionRate": 0.10}},
        {"id": "variant",
         "storeListing": {"languageCode": "en-US", "title": "B"},
         "results": {"conversionRate": 0.20}},   # +100% lift -> promote
    ],
}


def test_evaluate_picks_winner(tmp_path):
    fc = FakeExperimentClient(owned=True, experiments=[_ENDED_WIN])
    a, _ = _agent(fc, sandbox=SandboxMode.PRODUCTION, auto_pilot=True,
                  audit_file=tmp_path / "a.jsonl",
                  experiment_file=tmp_path / "exp.jsonl")
    out = a.evaluate(PKG)
    assert out["count"] == 1
    assert out["ended"] == 1
    assert out["recommendations"][0]["recommendation"] == "promote_variant"


def test_evaluate_running_no_recommendation(tmp_path):
    fc = FakeExperimentClient(owned=True, experiments=[
        {"experimentId": "EXP2", "name": "r", "status": "RUNNING",
         "variants": [{"id": "variant",
                       "storeListing": {"languageCode": "en-US"}}]}])
    a, _ = _agent(fc, sandbox=SandboxMode.PRODUCTION, auto_pilot=True,
                  audit_file=tmp_path / "a.jsonl",
                  experiment_file=tmp_path / "exp.jsonl")
    out = a.evaluate(PKG)
    assert out["running"] == 1
    assert out["recommendations"] == []


def test_run_daily_persists_and_recommends(tmp_path):
    fc = FakeExperimentClient(owned=True, experiments=[_ENDED_WIN])
    a, _ = _agent(fc, sandbox=SandboxMode.PRODUCTION, auto_pilot=True,
                  audit_file=tmp_path / "a.jsonl",
                  experiment_file=tmp_path / "exp.jsonl")
    out = a.run_daily([PKG])
    assert out["per_package"][PKG]["ended"] == 1
    assert len(out["recommendations"]) == 1
    # audit file should contain the ended + winner record
    from operation.publishing_factory.play_runtime.experiment_audit import (
        read_all, active_experiments)
    recs = read_all()
    assert any(r["status"] == "ended" for r in recs)
    # ended experiments are NOT in the "active" set
    assert active_experiments() == []


# ===================================================================== #
# 7) experiment_audit summary + active
def test_experiment_audit_summary_and_active(tmp_path):
    os.environ["LAUNCHFORGE_PLAY_EXPERIMENTS"] = str(tmp_path / "exp.jsonl")
    from operation.publishing_factory.play_runtime.experiment_audit import (
        append, summary_by_package, active_experiments)
    append(ListingExperimentProposal(PKG, "p1", status="running"))
    append(ListingExperimentProposal(PKG, "p2", status="ended",
                                     recommendation="promote_variant"))
    board = summary_by_package()
    assert board[PKG]["running"] == 1
    assert board[PKG]["ended"] == 1
    assert board[PKG]["winner"] == 1
    act = active_experiments()
    assert len(act) == 1
    assert act[0]["status"] == "running"


# ===================================================================== #
# 8) daily_briefing._run_experiment section
def test_run_experiment_section_renders(tmp_path):
    os.environ["LAUNCHFORGE_PLAY_EXPERIMENTS"] = str(tmp_path / "exp.jsonl")
    from operation.publishing_factory.play_runtime.experiment_audit import (
        append)
    append(ListingExperimentProposal(PKG, "p1", status="running"))
    append(ListingExperimentProposal(PKG, "p2", status="ended",
                                     recommendation="promote_variant"))
    from operation.optimizer.daily_briefing import _run_experiment
    out = _run_experiment(notify=False)
    assert out["status"] == "OK"
    assert PKG in out["markdown"]
    assert "进行中" in out["markdown"]
    assert "胜出建议" in out["markdown"]


def test_run_experiment_section_empty(tmp_path):
    os.environ["LAUNCHFORGE_PLAY_EXPERIMENTS"] = str(tmp_path / "empty.jsonl")
    from operation.optimizer.daily_briefing import _run_experiment
    out = _run_experiment(notify=False)
    assert out["status"] == "EMPTY"
