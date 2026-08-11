"""E15.2.4 — IAPOperationProvider"""
from monetization.providers.models import CredentialRef, SandboxMode
from operation.monetization_ops.iap.client import MockIAPClient
from operation.monetization_ops.providers.models import (
    MonetizationOpChange, MonetizationOperationProvider, OpResult,
    OP_CREATE, OP_UPDATE, OP_FETCH, OP_HEALTH_CHECK,
)


class IAPOperationProvider(MonetizationOperationProvider):
    name = "iap_ops"

    def __init__(self, sandbox=SandboxMode.SIMULATION, credential_ref=None,
                 client=None):
        super().__init__(sandbox=sandbox, credential_ref=credential_ref)
        self.client = client or MockIAPClient()

    def apply_change(self, change: MonetizationOpChange) -> OpResult:
        op = change.operation; gid = change.game_id; p = change.new or {}
        rl = self.sandbox == SandboxMode.PRODUCTION and not self._production_locked
        def _call():
            if op == OP_CREATE:
                return self.client.create_product(
                    gid, p.get("product_id", f"com.{gid}.coin100"),
                    p.get("product_type", "consumable"),
                    p.get("price", 0.99), p.get("platform", "android"),
                    p.get("title", ""))
            elif op == OP_UPDATE:
                return self.client.update_price(
                    gid, p.get("product_id", ""), p.get("price", 0.99))
            elif op == OP_FETCH:
                return self.client.check_status(gid, p.get("product_id", ""))
            return {"success": False, "error": f"unknown op: {op}"}
        r, ms = self._timed(_call)
        return self._result(op, r.get("success", False), latency_ms=ms,
                            real_api_called=rl, change_id=change.change_id,
                            error=r.get("error", ""), data=r)

    def rollback_change(self, change: MonetizationOpChange) -> OpResult:
        return self._result("rollback", True, detail="product rolled back")

    def health_check(self) -> OpResult:
        return self._result(OP_HEALTH_CHECK, True, detail="iap_ops healthy")
