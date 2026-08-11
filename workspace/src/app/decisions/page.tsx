"use client";

import { useEffect, useState, useCallback } from "react";
import { api, type Decision } from "@/lib/api";
import { Lightbulb, CheckCircle2, XCircle, Loader2, Play, Pause } from "lucide-react";

const statusColors: Record<string, string> = {
  proposed: "text-blue-400 bg-blue-500/10",
  approved: "text-green-400 bg-green-500/10",
  executed: "text-green-400 bg-green-500/10",
  rejected: "text-red-400 bg-red-500/10",
  waiting_approval: "text-yellow-400 bg-yellow-500/10",
};

export default function DecisionsPage() {
  const [decisions, setDecisions] = useState<Decision[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState<string | null>(null);
  const [toast, setToast] = useState<{ type: "success" | "error"; msg: string } | null>(null);

  const loadDecisions = useCallback(() => {
    api.getDecisions().then(setDecisions).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    loadDecisions();
  }, [loadDecisions]);

  // Toast 自动消失
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const handleApprove = async (id: string) => {
    setActionLoading(`approve-${id}`);
    try {
      const res = await api.approveDecision(id);
      setToast({ type: "success", msg: res.message });
      loadDecisions(); // 刷新列表
    } catch (err) {
      setToast({ type: "error", msg: err instanceof Error ? err.message : "批准失败" });
    } finally {
      setActionLoading(null);
    }
  };

  const handleReject = async (id: string) => {
    setActionLoading(`reject-${id}`);
    try {
      const res = await api.rejectDecision(id);
      setToast({ type: "success", msg: res.message });
      loadDecisions();
    } catch (err) {
      setToast({ type: "error", msg: err instanceof Error ? err.message : "驳回失败" });
    } finally {
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-gray-500">Loading decisions...</div>
      </div>
    );
  }

  const pendingCount = decisions.filter((d) => d.status === "waiting_approval").length;

  return (
    <div className="p-8 max-w-4xl">
      {/* Header */}
      <div className="mb-8 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Lightbulb className="w-5 h-5 text-indigo-400" />
            <h1 className="text-2xl font-bold text-gray-900">Decision Center</h1>
          </div>
          <p className="text-sm text-gray-500">
            AI 决策记录
            {pendingCount > 0 && (
              <span className="ml-2 px-2 py-0.5 rounded text-xs bg-yellow-500/10 text-yellow-400">
                {pendingCount} 待审批
              </span>
            )}
          </p>
        </div>
      </div>

      {/* Toast */}
      {toast && (
        <div className={`fixed top-6 right-6 z-50 px-4 py-3 rounded-lg shadow-lg border ${
          toast.type === "success"
            ? "bg-green-500/10 border-green-500/20 text-green-400"
            : "bg-red-500/10 border-red-500/20 text-red-400"
        }`}>
          {toast.msg}
        </div>
      )}

      {/* Decisions List */}
      <div className="space-y-4">
        {decisions.map((d) => {
          const isPending = d.status === "waiting_approval";
          const isLoading = actionLoading === `approve-${d.id}` || actionLoading === `reject-${d.id}`;

          return (
            <div
              key={d.id}
              className={`bg-[#ffffff] border rounded-xl p-5 transition-shadow ${
                isPending ? "border-yellow-500/30 shadow-md" : "border-[#e5e5e5]"
              }`}
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <h3 className="text-sm font-semibold text-gray-900 mb-1">{d.action}</h3>
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <span>{d.agent_name}</span>
                    <span>·</span>
                    <span>{d.game_name}</span>
                  </div>
                </div>
                <span className={`px-2 py-1 rounded text-xs ${statusColors[d.status] || statusColors.proposed}`}>
                  {d.status.replace("_", " ")}
                </span>
              </div>

              <p className="text-sm text-gray-400 mb-3">{d.reason}</p>

              <div className="flex items-center gap-4 pt-3 border-t border-[#e5e5e5]">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">Confidence</span>
                  <div className="w-20 h-1.5 bg-[#e5e5e5] rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${d.confidence * 100}%` }} />
                  </div>
                  <span className="text-xs text-indigo-400">{(d.confidence * 100).toFixed(0)}%</span>
                </div>
                <div className="text-xs">
                  <span className="text-gray-500">Impact: </span>
                  <span className="text-green-400">{d.impact}</span>
                </div>

                {/* 执行层: 审批按钮 */}
                {isPending && (
                  <div className="flex items-center gap-2 ml-auto">
                    <button
                      onClick={() => handleApprove(d.id)}
                      disabled={isLoading}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-green-500/10 text-green-400 hover:bg-green-500/20 transition-colors disabled:opacity-50"
                    >
                      {actionLoading === `approve-${d.id}` ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <CheckCircle2 className="w-3 h-3" />
                      )}
                      批准
                    </button>
                    <button
                      onClick={() => handleReject(d.id)}
                      disabled={isLoading}
                      className="flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium bg-red-500/10 text-red-400 hover:bg-red-500/20 transition-colors disabled:opacity-50"
                    >
                      {actionLoading === `reject-${d.id}` ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <XCircle className="w-3 h-3" />
                      )}
                      驳回
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {decisions.length === 0 && (
        <div className="text-center text-gray-500 py-12">
          暂无决策
        </div>
      )}
    </div>
  );
}
