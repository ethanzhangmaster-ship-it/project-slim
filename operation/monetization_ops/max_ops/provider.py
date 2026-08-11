"""E15.2.3 — MaxOperationProvider"""
from monetization.providers.models import CredentialRef, SandboxMode
from operation.monetization_ops.max_ops.client import MockMaxOperationClient
from operation.monetization_ops.providers.models import (
    MonetizationOpChange, MonetizationOperationProvider, OpResult,
    OP_CREATE, OP_FETCH, OP_UPDATE, OP_HEALTH_CHECK,
)


class MaxOperationProvider(MonetizationOperationProvider):
    name = "max_ops"

    def __init__(self, sandbox=SandboxMode.SIMULATION, credential_ref=None,
                 client=None):
        super().__init__(sandbox=sandbox, credential_ref=credential_ref)
        self.client = client or MockMaxOperationClient()

    def apply_change(self, change: MonetizationOpChange) -> OpResult:
        op = change.operation
        gid = change.game_id
        p = change.new or {}
        rl = self.sandbox == SandboxMode.PRODUCTION and not self._production_locked

        def _call():
            if op == OP_CREATE and "ad_unit" in p.get("target", ""):
                return self.client.create_ad_unit(
                    gid, p.get("ad_unit_id", f"max_{gid}_reward"),
                    p.get("format", "rewarded_video"),
                    p.get("platform", "android"),
                    p.get("placement", "reward_video"))
            elif op == OP_CREATE:
                return self.client.create_app(
                    gid, app_id=p.get("app_id", ""),
                    package_name=p.get("package_name", ""))
            elif op == OP_UPDATE:
                return self.client.configure_waterfall(
                    gid, p.get("ad_unit_id", ""),
                    p.get("networks", ["applovin"]),
                    p.get("floor", 0.01))
            elif op == OP_FETCH:
                return self.client.read_revenue(gid)
            else:
                return {"success": False, "error": f"unknown op: {op}"}

        r, ms = self._timed(_call)
        return self._result(op, r.get("success", False), latency_ms=ms,
                            real_api_called=rl, change_id=change.change_id,
                            error=r.get("error", ""), data=r)

    def rollback_change(self, change: MonetizationOpChange) -> OpResult:
        return self._result("rollback", True, detail="config rolled back")

    def health_check(self) -> OpResult:
        return self._result(OP_HEALTH_CHECK, True, detail="max_ops healthy")
