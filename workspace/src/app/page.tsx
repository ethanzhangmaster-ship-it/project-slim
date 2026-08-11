"use client";

import { useEffect, useState } from "react";
import { api, type Dashboard, type LoopTriggerResponse, type LoopCycleSummary, type CEODailyRunResponse, type ChurnAnalysis, type WinbackCampaign, type CampaignExecutionResult, type LiveOpsOverview, type CrossAgentOverview, type ChurnResponse, type ChurnResponseStats, type MonitorOverview } from "@/lib/api";
import LiveEventStream from "@/components/live-event-stream";
import AgentTopology from "@/components/agent-topology";
import {
  Users,
  DollarSign,
  TrendingUp,
  Bot,
  Zap,
  Gamepad2,
  Activity as ActivityIcon,
  Target,
  Play,
  Loader2,
  RotateCw,
  ShieldCheck,
  Stethoscope,
  Wand2,
  Briefcase,
  CheckCircle2,
  SkipForward,
  XCircle,
  HeartPulse,
  Gift,
  Send,
  Check,
  Ban,
  BarChart3,
  Trophy,
  Bell,
  Network,
  ArrowRight,
  Radio,
  AlertTriangle,
  TrendingDown,
  PieChart,
  Pause,
  Database,
  Undo2,
  CheckCircle,
  Activity,
  AlertCircle,
  HardDrive,
  Clock,
  ShieldAlert,
} from "lucide-react";

const statusColors: Record<string, string> = {
  success: "text-green-600 bg-green-50",
  warning: "text-yellow-600 bg-yellow-50",
  info: "text-blue-600 bg-blue-50",
  error: "text-red-600 bg-red-50",
  decision: "text-purple-600 bg-purple-50",
};

const gameStatusColors: Record<string, string> = {
  growing: "text-green-600 bg-green-50",
  stable: "text-blue-600 bg-blue-50",
  declining: "text-red-600 bg-red-50",
  launching: "text-purple-600 bg-purple-50",
};

const riskColors: Record<string, string> = {
  low: "text-green-600 bg-green-50",
  medium: "text-yellow-600 bg-yellow-50",
  high: "text-red-600 bg-red-50",
};

const actionTypeColors: Record<string, string> = {
  update_budget: "text-blue-600 bg-blue-50",
  pause_campaign: "text-orange-600 bg-orange-50",
  resume_campaign: "text-green-600 bg-green-50",
  replace_creative: "text-purple-600 bg-purple-50",
};

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + "M";
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return n.toString();
}

function formatCurrency(n: number): string {
  if (n >= 1000) return "$" + (n / 1000).toFixed(1) + "K";
  return "$" + n.toFixed(0);
}

function formatTime(iso: string): string {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [loopLoading, setLoopLoading] = useState(false);
  const [loopResult, setLoopResult] = useState<LoopTriggerResponse | null>(null);
  const [loopError, setLoopError] = useState<string | null>(null);
  const [fetchMetaAds, setFetchMetaAds] = useState(false);
  const [loopHistory, setLoopHistory] = useState<LoopCycleSummary[]>([]);
  const [ceoLoading, setCeoLoading] = useState(false);
  const [ceoResult, setCeoResult] = useState<CEODailyRunResponse | null>(null);
  const [ceoError, setCeoError] = useState<string | null>(null);
  const [liveopsGameId, setLiveopsGameId] = useState("");
  const [churnAnalysis, setChurnAnalysis] = useState<ChurnAnalysis | null>(null);
  const [winbackCampaign, setWinbackCampaign] = useState<WinbackCampaign | null>(null);
  const [liveopsLoading, setLiveopsLoading] = useState(false);
  const [liveopsError, setLiveopsError] = useState<string | null>(null);
  const [executionResult, setExecutionResult] = useState<CampaignExecutionResult | null>(null);
  const [executeDryRun, setExecuteDryRun] = useState(true);
  const [pendingApprovals, setPendingApprovals] = useState<CampaignExecutionResult[]>([]);
  const [liveopsStats, setLiveopsStats] = useState<LiveOpsOverview | null>(null);
  const [crossAgent, setCrossAgent] = useState<CrossAgentOverview | null>(null);
  const [churnResponses, setChurnResponses] = useState<ChurnResponse[]>([]);
  const [churnResponseStats, setChurnResponseStats] = useState<ChurnResponseStats | null>(null);
  const [monitor, setMonitor] = useState<MonitorOverview | null>(null);

  const refreshPendingApprovals = () => {
    api.listLiveopsPendingApprovals().then(setPendingApprovals).catch(() => {});
  };
  const refreshLiveopsStats = () => {
    api.getLiveopsStats(5).then(setLiveopsStats).catch(() => {});
  };
  const refreshCrossAgent = () => {
    api.getCrossAgentOverview().then(setCrossAgent).catch(() => {});
  };
  const refreshChurnResponses = () => {
    api.listChurnResponses(undefined, 10).then(setChurnResponses).catch(() => {});
    api.getChurnResponseStats().then(setChurnResponseStats).catch(() => {});
  };
  const refreshMonitor = () => {
    api.getMonitorOverview().then(setMonitor).catch(() => {});
  };

  const handleRollbackResponse = async (responseId: string) => {
    setLiveopsLoading(true);
    setLiveopsError(null);
    try {
      await api.rollbackChurnResponse(responseId);
      refreshChurnResponses();
      refreshCrossAgent();
    } catch (err) {
      setLiveopsError(err instanceof Error ? err.message : "回滚失败");
    } finally {
      setLiveopsLoading(false);
    }
  };

  useEffect(() => {
    Promise.all([
      api.getDashboard(),
      api.getLoopHistory(5),
    ]).then(([d, h]) => {
      setData(d);
      setLoopHistory(h);
    }).finally(() => setLoading(false));
    refreshPendingApprovals();
    refreshLiveopsStats();
    refreshCrossAgent();
    refreshChurnResponses();
    refreshMonitor();
  }, []);

  const refreshLoopHistory = () => {
    api.getLoopHistory(5).then(setLoopHistory).catch(() => {});
  };

  const handleTriggerLoop = async () => {
    setLoopLoading(true);
    setLoopError(null);
    setLoopResult(null);
    try {
      const res = await api.triggerLoop(true, fetchMetaAds);
      setLoopResult(res);
      // 刷新 Dashboard 数据和历史
      api.getDashboard().then(setData);
      refreshLoopHistory();
    } catch (err) {
      setLoopError(err instanceof Error ? err.message : "触发失败");
    } finally {
      setLoopLoading(false);
    }
  };

  const handleTriggerCEODaily = async () => {
    setCeoLoading(true);
    setCeoError(null);
    setCeoResult(null);
    try {
      const res = await api.triggerCEODailyRun("", false, false);
      setCeoResult(res);
      // 刷新 Dashboard 数据
      api.getDashboard().then(setData);
    } catch (err) {
      setCeoError(err instanceof Error ? err.message : "CEO 例会触发失败");
    } finally {
      setCeoLoading(false);
    }
  };

  const handleAnalyzeChurn = async () => {
    const gameId = liveopsGameId || data?.games?.[0]?.id || "demo_game";
    setLiveopsLoading(true);
    setLiveopsError(null);
    setChurnAnalysis(null);
    setWinbackCampaign(null);
    try {
      const res = await api.getChurnAnalysis(gameId);
      setChurnAnalysis(res);
    } catch (err) {
      setLiveopsError(err instanceof Error ? err.message : "流失分析失败");
    } finally {
      setLiveopsLoading(false);
    }
  };

  const handleDesignWinback = async () => {
    const gameId = liveopsGameId || data?.games?.[0]?.id || "demo_game";
    setLiveopsLoading(true);
    setLiveopsError(null);
    setWinbackCampaign(null);
    setExecutionResult(null);
    try {
      const res = await api.designWinbackCampaign(gameId, churnAnalysis || undefined);
      setWinbackCampaign(res);
      // design 会触发 churn_alert 广播 → 刷新 Growth 响应
      refreshChurnResponses();
      refreshCrossAgent();
    } catch (err) {
      setLiveopsError(err instanceof Error ? err.message : "回流活动设计失败");
    } finally {
      setLiveopsLoading(false);
    }
  };

  const handleExecuteCampaign = async () => {
    if (!winbackCampaign) return;
    setLiveopsLoading(true);
    setLiveopsError(null);
    setExecutionResult(null);
    try {
      const res = await api.executeLiveopsCampaign(winbackCampaign.campaign_id, executeDryRun);
      setExecutionResult(res);
      refreshPendingApprovals();
      refreshLiveopsStats();
      refreshCrossAgent();
    } catch (err) {
      setLiveopsError(err instanceof Error ? err.message : "活动执行失败");
    } finally {
      setLiveopsLoading(false);
    }
  };

  const handleApproveExecution = async (executionId: string) => {
    setLiveopsLoading(true);
    setLiveopsError(null);
    try {
      const res = await api.approveLiveopsExecution(executionId);
      setExecutionResult(res);
      refreshPendingApprovals();
      refreshLiveopsStats();
      refreshCrossAgent();
    } catch (err) {
      setLiveopsError(err instanceof Error ? err.message : "审批通过失败");
    } finally {
      setLiveopsLoading(false);
    }
  };

  const handleRejectExecution = async (executionId: string) => {
    setLiveopsLoading(true);
    setLiveopsError(null);
    try {
      const res = await api.rejectLiveopsExecution(executionId);
      setExecutionResult(res);
      refreshPendingApprovals();
      refreshLiveopsStats();
      refreshCrossAgent();
    } catch (err) {
      setLiveopsError(err instanceof Error ? err.message : "审批拒绝失败");
    } finally {
      setLiveopsLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-gray-500">Loading dashboard...</div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-red-500">Failed to load dashboard data</div>
      </div>
    );
  }

  const { kpi, briefing, games, active_tasks } = data;

  return (
    <div className="p-8 space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">{briefing.greeting}, 这里是今天的经营概览</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Meta Ads 数据开关 */}
          <label className="flex items-center gap-2 text-xs text-gray-500 cursor-pointer">
            <input
              type="checkbox"
              checked={fetchMetaAds}
              onChange={(e) => setFetchMetaAds(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-gray-300 text-indigo-500 focus:ring-indigo-500"
            />
            拉取 Meta Ads
          </label>
          <button
            onClick={handleTriggerLoop}
            disabled={loopLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-indigo-500 text-white hover:bg-indigo-600 transition-colors disabled:opacity-50"
          >
            {loopLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            触发 GrowthLoop
          </button>
          {/* CEO 每日例会按钮 */}
          <button
            onClick={handleTriggerCEODaily}
            disabled={ceoLoading}
            className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-purple-500 text-white hover:bg-purple-600 transition-colors disabled:opacity-50"
          >
            {ceoLoading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Briefcase className="w-4 h-4" />
            )}
            CEO 每日例会
          </button>
        </div>
      </div>

      {/* CEO 每日例会结果 */}
      {ceoResult && (
        <div className="bg-purple-50 border border-purple-200 rounded-xl p-5 space-y-4">
          <div className="flex items-start gap-3">
            <Briefcase className="w-5 h-5 text-purple-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <p className="text-sm font-medium text-purple-700">
                  CEO 例会 #{ceoResult.run_id.slice(-8)} · {ceoResult.date}
                </p>
                <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                  ceoResult.status === "completed" ? "text-green-600 bg-green-100" :
                  ceoResult.status === "skipped" ? "text-yellow-600 bg-yellow-100" :
                  ceoResult.status === "partial" ? "text-orange-600 bg-orange-100" :
                  "text-red-600 bg-red-100"
                }`}>
                  {ceoResult.status.toUpperCase()}
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-3 mt-1 text-xs text-gray-500">
                <span>耗时 {ceoResult.duration_seconds}s</span>
                <span>·</span>
                <span>{ceoResult.stages.length} 阶段</span>
                {ceoResult.report_id && (
                  <>
                    <span>·</span>
                    <span className="text-purple-600">报告: {ceoResult.report_id.slice(0, 20)}</span>
                  </>
                )}
                {ceoResult.real_api_called && (
                  <span className="text-red-500 font-medium">⚠ 真实 API 被调用</span>
                )}
              </div>
            </div>
          </div>

          {/* 13 阶段进度 */}
          <div className="bg-white/60 rounded-lg p-3 border border-gray-200">
            <div className="text-xs font-medium text-gray-700 mb-2">执行阶段</div>
            <div className="grid grid-cols-2 gap-1.5">
              {ceoResult.stages.map((s, i) => (
                <div key={i} className="flex items-center gap-2 text-xs bg-white rounded px-2 py-1 border border-gray-100">
                  {s.status === "ok" ? (
                    <CheckCircle2 className="w-3 h-3 text-green-500 flex-shrink-0" />
                  ) : s.status === "skipped" ? (
                    <SkipForward className="w-3 h-3 text-yellow-500 flex-shrink-0" />
                  ) : (
                    <XCircle className="w-3 h-3 text-red-500 flex-shrink-0" />
                  )}
                  <span className="text-gray-600 font-mono text-[11px]">{s.stage}</span>
                  {s.detail && (
                    <span className="text-gray-400 text-[10px] ml-auto truncate max-w-[120px]">{s.detail}</span>
                  )}
                </div>
              ))}
            </div>
          </div>

          {/* 决策 + 执行统计 */}
          <div className="grid grid-cols-2 gap-3">
            {Object.keys(ceoResult.decisions).length > 0 && (
              <div className="bg-white/60 rounded-lg p-3 border border-gray-200">
                <div className="text-xs font-medium text-gray-700 mb-2">决策统计</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(ceoResult.decisions).map(([type, count]) => (
                    <span key={type} className={`px-2 py-1 rounded text-xs font-medium ${
                      type === "EXECUTE" ? "text-green-600 bg-green-50" :
                      type === "APPROVE" ? "text-yellow-600 bg-yellow-50" :
                      type === "BLOCK" ? "text-red-600 bg-red-50" :
                      "text-gray-600 bg-gray-50"
                    }`}>
                      {type}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}
            {Object.keys(ceoResult.executions).length > 0 && (
              <div className="bg-white/60 rounded-lg p-3 border border-gray-200">
                <div className="text-xs font-medium text-gray-700 mb-2">执行统计</div>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(ceoResult.executions).map(([type, count]) => (
                    <span key={type} className="px-2 py-1 rounded text-xs font-medium text-gray-600 bg-gray-50">
                      {type}: {count}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 错误列表 */}
          {ceoResult.errors.length > 0 && (
            <div className="bg-red-50 rounded-lg p-3 border border-red-200">
              <div className="text-xs font-medium text-red-700 mb-1">错误 ({ceoResult.errors.length})</div>
              <div className="space-y-1">
                {ceoResult.errors.slice(0, 5).map((e, i) => (
                  <div key={i} className="text-xs text-red-600">• {e}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      {ceoError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3">
          <span className="text-red-600 text-sm">{ceoError}</span>
        </div>
      )}

      {/* Loop Trigger Result — 增强展示 */}
      {loopResult && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-5 space-y-4">
          <div className="flex items-start gap-3">
            <Zap className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
            <div className="flex-1">
              <p className="text-sm font-medium text-green-700">{loopResult.message}</p>
              <div className="flex flex-wrap items-center gap-3 mt-1 text-xs text-gray-500">
                <span>耗时 {loopResult.duration_seconds}s</span>
                <span>·</span>
                <span className={loopResult.dry_run ? "text-yellow-600" : "text-green-600"}>
                  {loopResult.dry_run ? "Dry-run" : "Live"}
                </span>
                <span>·</span>
                <span>动作 {loopResult.actions_planned}</span>
                <span>·</span>
                <span>执行 {loopResult.actions_executed}</span>
                {loopResult.success_rate !== undefined && (
                  <>
                    <span>·</span>
                    <span className="text-green-600">成功率 {(loopResult.success_rate * 100).toFixed(0)}%</span>
                  </>
                )}
              </div>
            </div>
          </div>

          {/* Meta Ads 数据 + RealityScore 横向展示 */}
          <div className="grid grid-cols-2 gap-3">
            {/* Meta Ads 数据 */}
            {loopResult.meta_ads_data && (
              <div className="bg-white/60 rounded-lg p-3 border border-gray-200">
                <div className="flex items-center gap-2 mb-2">
                  <ActivityIcon className="w-3.5 h-3.5 text-indigo-500" />
                  <span className="text-xs font-medium text-gray-700">Meta Ads 数据</span>
                </div>
                <div className="text-xs text-gray-600 space-y-0.5">
                  <div>创意: {loopResult.meta_ads_data.creatives_fetched} · 信号: {loopResult.meta_ads_data.signals_generated}</div>
                  {loopResult.meta_ads_data.predictions_generated !== undefined && (
                    <div>预测: {loopResult.meta_ads_data.predictions_generated}</div>
                  )}
                  {loopResult.meta_ads_data.fetch_error && (
                    <div className="text-red-500">错误: {loopResult.meta_ads_data.fetch_error}</div>
                  )}
                </div>
              </div>
            )}

            {/* RealityScore */}
            {loopResult.reality_scores && loopResult.reality_scores.length > 0 && (
              <div className="bg-white/60 rounded-lg p-3 border border-gray-200">
                <div className="flex items-center gap-2 mb-2">
                  <ShieldCheck className="w-3.5 h-3.5 text-green-500" />
                  <span className="text-xs font-medium text-gray-700">RealityGate</span>
                </div>
                <div className="space-y-1">
                  {loopResult.reality_scores.map((rs, i) => (
                    <div key={i} className="text-xs">
                      <div className="flex items-center justify-between">
                        <span className="text-gray-600">{rs.game_id}</span>
                        <span className="font-mono font-medium text-green-600">{rs.composite.toFixed(2)}</span>
                      </div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="px-1.5 py-0.5 rounded bg-green-100 text-green-700 text-[10px] font-medium">
                          {rs.decision_level}
                        </span>
                        <span className="text-[10px] text-gray-400">
                          C{rs.coverage.toFixed(1)} F{rs.freshness.toFixed(1)} K{rs.consistency.toFixed(1)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* 诊断 + 策略 摘要 */}
          {(loopResult.diagnosis_summary || loopResult.strategy_summary) && (
            <div className="grid grid-cols-2 gap-3">
              {loopResult.diagnosis_summary && (
                <div className="bg-white/60 rounded-lg p-3 border border-gray-200">
                  <div className="flex items-center gap-2 mb-1.5">
                    <Stethoscope className="w-3.5 h-3.5 text-purple-500" />
                    <span className="text-xs font-medium text-gray-700">诊断摘要</span>
                    <span className="ml-auto text-xs text-gray-400">置信度 {(loopResult.diagnosis_summary.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="text-xs text-gray-600">
                    <div className="font-medium text-purple-600">{loopResult.diagnosis_summary.root_cause}</div>
                    {loopResult.diagnosis_summary.evidence.slice(0, 2).map((e, i) => (
                      <div key={i} className="text-[11px] text-gray-500 mt-0.5">• {e}</div>
                    ))}
                  </div>
                </div>
              )}
              {loopResult.strategy_summary && (
                <div className="bg-white/60 rounded-lg p-3 border border-gray-200">
                  <div className="flex items-center gap-2 mb-1.5">
                    <Wand2 className="w-3.5 h-3.5 text-indigo-500" />
                    <span className="text-xs font-medium text-gray-700">策略摘要</span>
                    <span className="ml-auto text-xs text-gray-400">{loopResult.strategy_summary.time_horizon_days}d</span>
                  </div>
                  <div className="text-xs text-gray-600">
                    <div className="font-medium text-indigo-600">
                      {loopResult.strategy_summary.strategy_type} · 强度 {(loopResult.strategy_summary.intensity * 100).toFixed(0)}%
                    </div>
                    <div className="text-[11px] text-gray-500 mt-0.5">
                      目标: {loopResult.strategy_summary.target_creative_id.slice(0, 16)}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 动作详情列表 */}
          {loopResult.action_details && loopResult.action_details.length > 0 && (
            <div className="bg-white/60 rounded-lg p-3 border border-gray-200">
              <div className="text-xs font-medium text-gray-700 mb-2">
                动作链路 ({loopResult.action_details.length} 个)
              </div>
              <div className="space-y-1.5 max-h-48 overflow-y-auto">
                {loopResult.action_details.map((a, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs bg-white rounded px-2 py-1.5 border border-gray-100">
                    <span className={`px-1.5 py-0.5 rounded font-medium ${actionTypeColors[a.action_type] || "text-gray-600 bg-gray-50"}`}>
                      {a.action_type}
                    </span>
                    <span className="text-gray-500 font-mono text-[11px]">{a.creative_id.slice(0, 14)}</span>
                    <span className="text-gray-400">·</span>
                    <span className={`px-1 py-0.5 rounded text-[10px] ${riskColors[a.risk_level] || "text-gray-500"}`}>
                      {a.risk_level}
                    </span>
                    <span className={`px-1 py-0.5 rounded text-[10px] ${a.approval_level === 0 ? "text-green-600 bg-green-50" : "text-yellow-600 bg-yellow-50"}`}>
                      L{a.approval_level}
                    </span>
                    {a.budget_impact > 0 && (
                      <span className="text-orange-500 text-[11px]">${a.budget_impact.toFixed(0)}</span>
                    )}
                    <span className="text-gray-400 ml-auto text-[10px]">{a.status}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
      {loopError && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-center gap-3">
          <span className="text-red-600 text-sm">{loopError}</span>
        </div>
      )}

      {/* LiveOps Agent — 流失分析 + 回流活动 */}
      <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <HeartPulse className="w-4 h-4 text-fuchsia-500" />
            <h2 className="text-sm font-semibold text-gray-900">LiveOps Agent</h2>
            <span className="text-xs text-gray-400">流失分析 · 回流活动设计</span>
          </div>
          <div className="flex items-center gap-2">
            <select
              value={liveopsGameId}
              onChange={(e) => setLiveopsGameId(e.target.value)}
              className="text-xs border border-gray-300 rounded-lg px-2 py-1.5 text-gray-700 focus:ring-fuchsia-500 focus:border-fuchsia-500"
            >
              <option value="">选择游戏</option>
              {data?.games?.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
              <option value="demo_game">demo_game</option>
            </select>
            <button
              onClick={handleAnalyzeChurn}
              disabled={liveopsLoading}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-fuchsia-500 text-white hover:bg-fuchsia-600 transition-colors disabled:opacity-50"
            >
              {liveopsLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <HeartPulse className="w-3.5 h-3.5" />}
              分析流失
            </button>
            <button
              onClick={handleDesignWinback}
              disabled={liveopsLoading || !churnAnalysis}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-pink-500 text-white hover:bg-pink-600 transition-colors disabled:opacity-50"
            >
              {liveopsLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Gift className="w-3.5 h-3.5" />}
              设计回流活动
            </button>
          </div>
        </div>

        {liveopsError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-xs text-red-600">
            {liveopsError}
          </div>
        )}

        {churnAnalysis && (
          <div className="bg-fuchsia-50 border border-fuchsia-200 rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-2">
              <HeartPulse className="w-4 h-4 text-fuchsia-600" />
              <span className="text-sm font-medium text-fuchsia-700">
                流失分析 · {churnAnalysis.game_id} · {churnAnalysis.analysis_date}
              </span>
            </div>
            <div className="grid grid-cols-4 gap-3">
              <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                <div className="text-[10px] text-gray-500">总玩家</div>
                <div className="text-base font-semibold text-gray-900">{churnAnalysis.total_players}</div>
              </div>
              <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                <div className="text-[10px] text-gray-500">流失风险</div>
                <div className="text-base font-semibold text-red-600">{churnAnalysis.at_risk_count}</div>
              </div>
              <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                <div className="text-[10px] text-gray-500">高价值风险</div>
                <div className="text-base font-semibold text-orange-600">{churnAnalysis.high_value_at_risk}</div>
              </div>
              <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                <div className="text-[10px] text-gray-500">平均风险分</div>
                <div className="text-base font-semibold text-fuchsia-600">{(churnAnalysis.avg_churn_risk * 100).toFixed(0)}%</div>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-white/60 rounded-lg p-3 border border-gray-200">
                <div className="text-xs font-medium text-gray-700 mb-1.5">生命周期阶段</div>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(churnAnalysis.lifecycle_stages).map(([stage, count]) => (
                    <span key={stage} className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                      stage === "LAPSED" ? "text-red-600 bg-red-50" :
                      stage === "CHURNING" ? "text-orange-600 bg-orange-50" :
                      stage === "ENGAGED" ? "text-green-600 bg-green-50" :
                      "text-blue-600 bg-blue-50"
                    }`}>
                      {stage}: {count}
                    </span>
                  ))}
                </div>
              </div>
              <div className="bg-white/60 rounded-lg p-3 border border-gray-200">
                <div className="text-xs font-medium text-gray-700 mb-1.5">玩家分群</div>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(churnAnalysis.segments).map(([seg, count]) => (
                    <span key={seg} className={`px-2 py-0.5 rounded text-[11px] font-medium ${
                      seg === "at_risk_churn" ? "text-red-600 bg-red-50" :
                      seg === "power_user" ? "text-green-600 bg-green-50" :
                      "text-gray-600 bg-gray-50"
                    }`}>
                      {seg}: {count}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {winbackCampaign && (
          <div className="bg-pink-50 border border-pink-200 rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-2">
              <Gift className="w-4 h-4 text-pink-600" />
              <span className="text-sm font-medium text-pink-700">
                回流活动方案 · {winbackCampaign.campaign_type}
              </span>
              <span className="px-2 py-0.5 rounded text-[10px] font-medium text-pink-600 bg-pink-100">
                {winbackCampaign.target_segment}
              </span>
              <span className="text-[10px] text-gray-400 ml-auto">
                {winbackCampaign.campaign_id.slice(0, 20)}
              </span>
            </div>
            <div className="grid grid-cols-4 gap-3">
              <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                <div className="text-[10px] text-gray-500">目标用户</div>
                <div className="text-sm font-semibold text-gray-900">{winbackCampaign.target_count}</div>
              </div>
              <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                <div className="text-[10px] text-gray-500">奖励池</div>
                <div className="text-sm font-semibold text-green-600">${winbackCampaign.rewards_pool.toFixed(0)}</div>
              </div>
              <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                <div className="text-[10px] text-gray-500">持续天数</div>
                <div className="text-sm font-semibold text-gray-900">{winbackCampaign.duration_days}d</div>
              </div>
              <div className="bg-white rounded-lg p-2.5 border border-gray-100">
                <div className="text-[10px] text-gray-500">预期留存提升</div>
                <div className="text-sm font-semibold text-fuchsia-600">+{(winbackCampaign.expected_retention_uplift * 100).toFixed(1)}%</div>
              </div>
            </div>
            <div className="bg-white/60 rounded-lg p-3 border border-gray-200">
              <div className="text-xs font-medium text-gray-700 mb-2">活动动作 ({winbackCampaign.actions.length})</div>
              <div className="space-y-1.5">
                {winbackCampaign.actions.map((a, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs bg-white rounded px-2 py-1.5 border border-gray-100">
                    <span className={`px-1.5 py-0.5 rounded font-medium text-[10px] ${
                      a.action_type === "push_notification" ? "text-blue-600 bg-blue-50" :
                      a.action_type === "in_app_message" ? "text-purple-600 bg-purple-50" :
                      a.action_type === "reward_grant" ? "text-green-600 bg-green-50" :
                      a.action_type === "email" ? "text-orange-600 bg-orange-50" :
                      "text-gray-600 bg-gray-50"
                    }`}>
                      {a.action_type}
                    </span>
                    <span className="text-gray-600 flex-1">{a.content}</span>
                    {a.trigger_delay_hours > 0 && (
                      <span className="text-[10px] text-gray-400">+{a.trigger_delay_hours}h</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
            {/* 执行按钮 */}
            <div className="flex items-center gap-2 pt-2 border-t border-pink-200">
              <label className="flex items-center gap-1.5 text-xs text-gray-600 cursor-pointer">
                <input
                  type="checkbox"
                  checked={executeDryRun}
                  onChange={(e) => setExecuteDryRun(e.target.checked)}
                  className="w-3 h-3 rounded border-gray-300 text-pink-500 focus:ring-pink-500"
                />
                Dry-run 模式
              </label>
              <button
                onClick={handleExecuteCampaign}
                disabled={liveopsLoading}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-rose-500 text-white hover:bg-rose-600 transition-colors disabled:opacity-50 ml-auto"
              >
                {liveopsLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
                执行活动
              </button>
            </div>
          </div>
        )}

        {/* 执行结果展示 */}
        {executionResult && (
          <div className={`border rounded-lg p-4 space-y-3 ${
            executionResult.status === "completed" ? "bg-green-50 border-green-200" :
            executionResult.status === "blocked" ? "bg-orange-50 border-orange-200" :
            executionResult.status === "dry_run" ? "bg-blue-50 border-blue-200" :
            executionResult.status === "failed" ? "bg-red-50 border-red-200" :
            executionResult.status === "rejected" ? "bg-gray-50 border-gray-200" :
            "bg-gray-50 border-gray-200"
          }`}>
            <div className="flex items-center gap-2">
              {executionResult.status === "completed" && <CheckCircle2 className="w-4 h-4 text-green-600" />}
              {executionResult.status === "blocked" && <ShieldCheck className="w-4 h-4 text-orange-600" />}
              {executionResult.status === "dry_run" && <SkipForward className="w-4 h-4 text-blue-600" />}
              {executionResult.status === "failed" && <XCircle className="w-4 h-4 text-red-600" />}
              {executionResult.status === "rejected" && <Ban className="w-4 h-4 text-gray-600" />}
              <span className="text-sm font-medium">
                执行结果 · <span className="font-mono">{executionResult.execution_id.slice(0, 16)}</span>
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                executionResult.status === "completed" ? "text-green-600 bg-green-100" :
                executionResult.status === "blocked" ? "text-orange-600 bg-orange-100" :
                executionResult.status === "dry_run" ? "text-blue-600 bg-blue-100" :
                executionResult.status === "failed" ? "text-red-600 bg-red-100" :
                "text-gray-600 bg-gray-100"
              }`}>
                {executionResult.status.toUpperCase()}
              </span>
              <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                executionResult.approval_level === 0 ? "text-green-600 bg-green-50" :
                executionResult.approval_level === 1 ? "text-yellow-600 bg-yellow-50" :
                "text-red-600 bg-red-50"
              }`}>
                Level {executionResult.approval_level}
              </span>
              {executionResult.dry_run && (
                <span className="px-2 py-0.5 rounded text-[10px] font-medium text-blue-600 bg-blue-50">
                  DRY-RUN
                </span>
              )}
              {/* 审批按钮 (仅 blocked/dry_run 状态显示) */}
              {(executionResult.status === "blocked" || executionResult.status === "dry_run") && (
                <div className="flex items-center gap-1.5 ml-auto">
                  <button
                    onClick={() => handleApproveExecution(executionResult.execution_id)}
                    disabled={liveopsLoading}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-green-500 text-white hover:bg-green-600 transition-colors disabled:opacity-50"
                  >
                    {liveopsLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Check className="w-3 h-3" />}
                    审批通过
                  </button>
                  <button
                    onClick={() => handleRejectExecution(executionResult.execution_id)}
                    disabled={liveopsLoading}
                    className="flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-red-500 text-white hover:bg-red-600 transition-colors disabled:opacity-50"
                  >
                    {liveopsLoading ? <Loader2 className="w-3 h-3 animate-spin" /> : <Ban className="w-3 h-3" />}
                    拒绝
                  </button>
                </div>
              )}
            </div>
            {executionResult.blocked_reason && (
              <div className="text-xs text-gray-600 bg-white/60 rounded px-2 py-1.5 border border-gray-200">
                {executionResult.blocked_reason}
              </div>
            )}
            <div className="grid grid-cols-4 gap-2">
              <div className="bg-white rounded p-2 border border-gray-100">
                <div className="text-[10px] text-gray-500">动作数</div>
                <div className="text-sm font-semibold text-gray-900">{executionResult.actions.length}</div>
              </div>
              <div className="bg-white rounded p-2 border border-gray-100">
                <div className="text-[10px] text-gray-500">已完成</div>
                <div className="text-sm font-semibold text-green-600">
                  {executionResult.actions.filter(a => a.status === "completed").length}
                </div>
              </div>
              <div className="bg-white rounded p-2 border border-gray-100">
                <div className="text-[10px] text-gray-500">已阻塞</div>
                <div className="text-sm font-semibold text-orange-600">
                  {executionResult.actions.filter(a => a.status === "blocked").length}
                </div>
              </div>
              <div className="bg-white rounded p-2 border border-gray-100">
                <div className="text-[10px] text-gray-500">已失败</div>
                <div className="text-sm font-semibold text-red-600">
                  {executionResult.actions.filter(a => a.status === "failed").length}
                </div>
              </div>
            </div>
            {/* 动作执行详情 */}
            <div className="bg-white/60 rounded-lg p-3 border border-gray-200">
              <div className="text-xs font-medium text-gray-700 mb-2">动作执行详情</div>
              <div className="space-y-1.5 max-h-40 overflow-y-auto">
                {executionResult.actions.map((a, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs bg-white rounded px-2 py-1.5 border border-gray-100">
                    <span className={`px-1.5 py-0.5 rounded font-medium text-[10px] ${
                      a.action_type === "push_notification" ? "text-blue-600 bg-blue-50" :
                      a.action_type === "in_app_message" ? "text-purple-600 bg-purple-50" :
                      a.action_type === "reward_grant" ? "text-green-600 bg-green-50" :
                      a.action_type === "email" ? "text-orange-600 bg-orange-50" :
                      "text-gray-600 bg-gray-50"
                    }`}>
                      {a.action_type}
                    </span>
                    {a.rewards_amount > 0 && (
                      <span className="text-[10px] text-green-600 font-medium">${a.rewards_amount.toFixed(2)}</span>
                    )}
                    <span className={`px-1 py-0.5 rounded text-[10px] ${
                      a.approval_level === 0 ? "text-green-600 bg-green-50" :
                      a.approval_level === 1 ? "text-yellow-600 bg-yellow-50" :
                      "text-red-600 bg-red-50"
                    }`}>
                      L{a.approval_level}
                    </span>
                    <span className={`px-1 py-0.5 rounded text-[10px] font-medium ${
                      a.status === "completed" ? "text-green-600 bg-green-50" :
                      a.status === "blocked" ? "text-orange-600 bg-orange-50" :
                      a.status === "failed" ? "text-red-600 bg-red-50" :
                      a.status === "dry_run" ? "text-blue-600 bg-blue-50" :
                      "text-gray-600 bg-gray-50"
                    }`}>
                      {a.status}
                    </span>
                    {a.error_message && (
                      <span className="text-[10px] text-red-500 truncate max-w-[150px]">{a.error_message}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* 待审批列表 */}
        {pendingApprovals.length > 0 && (
          <div className="bg-orange-50 border border-orange-200 rounded-lg p-4 space-y-2">
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-orange-600" />
              <span className="text-sm font-medium text-orange-700">
                待审批活动 ({pendingApprovals.length})
              </span>
              <button
                onClick={refreshPendingApprovals}
                className="text-xs text-orange-500 hover:text-orange-700 ml-auto"
              >
                刷新
              </button>
            </div>
            <div className="space-y-1.5">
              {pendingApprovals.map((p) => (
                <div key={p.execution_id} className="flex items-center gap-2 text-xs bg-white rounded px-2 py-1.5 border border-orange-100">
                  <span className="font-mono text-gray-600">{p.execution_id.slice(0, 16)}</span>
                  <span className="text-gray-500">·</span>
                  <span className="text-gray-700">{p.campaign_type}</span>
                  <span className="text-gray-500">·</span>
                  <span className="text-green-600 font-medium">${p.rewards_pool.toFixed(0)}</span>
                  <span className="text-gray-500">·</span>
                  <span className="text-orange-600">Level {p.approval_level}</span>
                  {p.blocked_reason && (
                    <span className="text-[10px] text-gray-500 truncate max-w-[200px]">{p.blocked_reason}</span>
                  )}
                  <div className="flex items-center gap-1 ml-auto">
                    <button
                      onClick={() => handleApproveExecution(p.execution_id)}
                      disabled={liveopsLoading}
                      className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-green-500 text-white hover:bg-green-600 transition-colors disabled:opacity-50"
                    >
                      <Check className="w-3 h-3" />
                      通过
                    </button>
                    <button
                      onClick={() => handleRejectExecution(p.execution_id)}
                      disabled={liveopsLoading}
                      className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-medium bg-red-500 text-white hover:bg-red-600 transition-colors disabled:opacity-50"
                    >
                      <Ban className="w-3 h-3" />
                      拒绝
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* LiveOps 执行概览统计 */}
        {liveopsStats && liveopsStats.total_executions > 0 && (
          <div className="bg-white border border-[#e5e5e5] rounded-lg p-4 space-y-3">
            <div className="flex items-center gap-2">
              <BarChart3 className="w-4 h-4 text-rose-500" />
              <span className="text-sm font-semibold text-gray-900">LiveOps 执行概览</span>
              <span className="text-xs text-gray-500 ml-1">
                共 {liveopsStats.total_executions} 次执行 · 成功率 {(liveopsStats.success_rate * 100).toFixed(0)}%
              </span>
              <button
                onClick={refreshLiveopsStats}
                className="text-xs text-gray-400 hover:text-gray-600 ml-auto"
              >
                刷新
              </button>
            </div>

            {/* 统计指标卡片 */}
            <div className="grid grid-cols-4 gap-2">
              <div className="bg-green-50 border border-green-100 rounded-lg p-2.5">
                <div className="flex items-center gap-1.5">
                  <CheckCircle2 className="w-3.5 h-3.5 text-green-600" />
                  <span className="text-[10px] font-medium text-green-700">已完成</span>
                </div>
                <div className="text-lg font-bold text-green-700 mt-0.5">{liveopsStats.completed}</div>
              </div>
              <div className="bg-orange-50 border border-orange-100 rounded-lg p-2.5">
                <div className="flex items-center gap-1.5">
                  <ShieldCheck className="w-3.5 h-3.5 text-orange-600" />
                  <span className="text-[10px] font-medium text-orange-700">阻塞中</span>
                </div>
                <div className="text-lg font-bold text-orange-700 mt-0.5">{liveopsStats.blocked}</div>
              </div>
              <div className="bg-blue-50 border border-blue-100 rounded-lg p-2.5">
                <div className="flex items-center gap-1.5">
                  <Trophy className="w-3.5 h-3.5 text-blue-600" />
                  <span className="text-[10px] font-medium text-blue-700">奖励下发</span>
                </div>
                <div className="text-lg font-bold text-blue-700 mt-0.5">${liveopsStats.total_rewards_distributed.toFixed(0)}</div>
              </div>
              <div className="bg-purple-50 border border-purple-100 rounded-lg p-2.5">
                <div className="flex items-center gap-1.5">
                  <Bell className="w-3.5 h-3.5 text-purple-600" />
                  <span className="text-[10px] font-medium text-purple-700">推送送达</span>
                </div>
                <div className="text-lg font-bold text-purple-700 mt-0.5">{liveopsStats.total_push_delivered}</div>
              </div>
            </div>

            {/* 详细下发统计 */}
            <div className="flex items-center gap-4 text-xs text-gray-600 pt-1 border-t border-gray-100">
              <span className="flex items-center gap-1">
                <Gift className="w-3 h-3 text-pink-500" />
                奖励发放: <span className="font-medium text-gray-900">{liveopsStats.total_reward_grant_delivered}</span>
              </span>
              <span className="flex items-center gap-1">
                <Send className="w-3 h-3 text-cyan-500" />
                邮件: <span className="font-medium text-gray-900">{liveopsStats.total_email_delivered}</span>
              </span>
              <span className="flex items-center gap-1">
                <SkipForward className="w-3 h-3 text-gray-400" />
                Dry-run: <span className="font-medium text-gray-900">{liveopsStats.dry_run}</span>
              </span>
              {liveopsStats.failed > 0 && (
                <span className="flex items-center gap-1">
                  <XCircle className="w-3 h-3 text-red-500" />
                  失败: <span className="font-medium text-red-600">{liveopsStats.failed}</span>
                </span>
              )}
            </div>

            {/* 按游戏分组 */}
            {Object.keys(liveopsStats.by_game).length > 0 && (
              <div className="space-y-1.5 pt-1 border-t border-gray-100">
                <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">按游戏分组</div>
                {Object.entries(liveopsStats.by_game).map(([gameId, stat]) => (
                  <div key={gameId} className="flex items-center gap-2 text-xs bg-gray-50 rounded px-2 py-1.5">
                    <span className="font-mono text-gray-700">{gameId}</span>
                    <span className="text-gray-400">·</span>
                    <span className="text-gray-600">执行 {stat.executions} 次</span>
                    <span className="text-gray-400">·</span>
                    <span className="text-green-600">完成 {stat.completed}</span>
                    {stat.blocked > 0 && (
                      <>
                        <span className="text-gray-400">·</span>
                        <span className="text-orange-600">阻塞 {stat.blocked}</span>
                      </>
                    )}
                    <span className="text-gray-400">·</span>
                    <span className="text-blue-600 font-medium">${stat.rewards_distributed.toFixed(0)}</span>
                    <span className="text-gray-400 ml-auto">目标 {stat.target_count} 人</span>
                  </div>
                ))}
              </div>
            )}

            {/* 最近执行记录 */}
            {liveopsStats.recent_executions.length > 0 && (
              <div className="space-y-1.5 pt-1 border-t border-gray-100">
                <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">最近执行</div>
                {liveopsStats.recent_executions.map((exec) => (
                  <div key={exec.execution_id} className="flex items-center gap-2 text-xs bg-white rounded px-2 py-1.5 border border-gray-100">
                    <span className="font-mono text-gray-500 text-[10px]">{exec.execution_id.slice(0, 12)}</span>
                    <span className="text-gray-400">·</span>
                    <span className="text-gray-700">{exec.campaign_type}</span>
                    <span className="text-gray-400">·</span>
                    <span className="text-gray-600">{exec.game_id}</span>
                    <span className="text-gray-400">·</span>
                    <span className="text-green-600 font-medium">${exec.rewards_pool.toFixed(0)}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                      exec.status === "completed" ? "text-green-600 bg-green-50" :
                      exec.status === "blocked" ? "text-orange-600 bg-orange-50" :
                      exec.status === "dry_run" ? "text-blue-600 bg-blue-50" :
                      exec.status === "rejected" ? "text-gray-600 bg-gray-50" :
                      "text-red-600 bg-red-50"
                    }`}>
                      {exec.status}
                    </span>
                    {exec.dry_run && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium text-blue-600 bg-blue-50">DRY</span>
                    )}
                    <span className="text-gray-400 ml-auto text-[10px]">
                      {exec.completed_at ? new Date(exec.completed_at).toLocaleString("zh-CN", { hour: "2-digit", minute: "2-digit", month: "2-digit", day: "2-digit" }) : "-"}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* 跨 Agent 协同可视化 */}
      {crossAgent && (
        <div className="bg-white border border-[#e5e5e5] rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2">
            <Network className="w-5 h-5 text-indigo-500" />
            <h2 className="text-lg font-bold text-gray-900">跨 Agent 协同拓扑</h2>
            <span className="text-xs text-gray-500">
              {crossAgent.collaboration_stats.topology_summary?.total_agents || crossAgent.topology.nodes.length} 个 Agent · {" "}
              {crossAgent.collaboration_stats.topology_summary?.total_edges || crossAgent.topology.edges.length} 条链路 · {" "}
              {crossAgent.collaboration_stats.topology_summary?.total_departments || crossAgent.topology.departments.length} 个部门
            </span>
            <button
              onClick={refreshCrossAgent}
              className="text-xs text-gray-400 hover:text-gray-600 ml-auto"
            >
              刷新
            </button>
          </div>

          {/* 交互式拓扑图 */}
          <div className="bg-gray-50 border border-gray-100 rounded-lg p-4">
            <AgentTopology
              nodes={crossAgent.topology.nodes}
              edges={crossAgent.topology.edges}
              departments={crossAgent.topology.departments}
            />
          </div>

          {/* 协同链路快捷入口 */}
          {crossAgent.collaboration_stats.collaboration_links && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">协同链路:</span>
              {crossAgent.collaboration_stats.collaboration_links.map((link, idx) => (
                <span
                  key={idx}
                  className={`px-2 py-1 rounded text-[10px] font-medium border ${
                    link.active
                      ? "text-indigo-600 bg-indigo-50 border-indigo-100"
                      : "text-gray-400 bg-gray-50 border-gray-100"
                  }`}
                >
                  {link.name}
                </span>
              ))}
            </div>
          )}

          {/* CEO Daily Run STAGE_LIVEOPS 结果 */}
          {crossAgent.ceo_liveops_stage && (
            <div className="bg-purple-50 border border-purple-200 rounded-lg p-4 space-y-2">
              <div className="flex items-center gap-2">
                <Briefcase className="w-4 h-4 text-purple-600" />
                <span className="text-sm font-medium text-purple-900">
                  CEO Daily Run · STAGE_LIVEOPS
                </span>
                <span className={`px-2 py-0.5 rounded text-[10px] font-medium ${
                  crossAgent.ceo_liveops_stage.status === "ok" ? "text-green-600 bg-green-100" :
                  crossAgent.ceo_liveops_stage.status === "skipped" ? "text-yellow-600 bg-yellow-100" :
                  "text-red-600 bg-red-100"
                }`}>
                  {crossAgent.ceo_liveops_stage.status.toUpperCase()}
                </span>
                <span className="text-[10px] text-purple-500 ml-auto font-mono">
                  {crossAgent.ceo_liveops_stage.business_date} · {crossAgent.ceo_liveops_stage.run_id.slice(0, 12)}
                </span>
              </div>
              <div className="text-xs text-purple-700">{crossAgent.ceo_liveops_stage.detail}</div>
              {crossAgent.ceo_liveops_stage.payload && (
                <div className="grid grid-cols-3 gap-2 pt-1">
                  <div className="bg-white rounded px-2 py-1.5 border border-purple-100">
                    <div className="text-[10px] text-gray-500">分析游戏数</div>
                    <div className="text-sm font-bold text-purple-700">
                      {String((crossAgent.ceo_liveops_stage.payload as Record<string, unknown>).analyses_count ?? "-")}
                    </div>
                  </div>
                  <div className="bg-white rounded px-2 py-1.5 border border-purple-100">
                    <div className="text-[10px] text-gray-500">设计活动数</div>
                    <div className="text-sm font-bold text-purple-700">
                      {String((crossAgent.ceo_liveops_stage.payload as Record<string, unknown>).campaigns_count ?? "-")}
                    </div>
                  </div>
                  <div className="bg-white rounded px-2 py-1.5 border border-purple-100">
                    <div className="text-[10px] text-gray-500">高价值流失</div>
                    <div className="text-sm font-bold text-orange-600">
                      {String((crossAgent.ceo_liveops_stage.payload as Record<string, unknown>).high_value_at_risk_total ?? "-")} 人
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* 协同统计 */}
          <div className="grid grid-cols-4 gap-2">
            <div className="bg-indigo-50 border border-indigo-100 rounded-lg p-2.5">
              <div className="flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 text-indigo-600" />
                <span className="text-[10px] font-medium text-indigo-700">LiveOps 事件</span>
              </div>
              <div className="text-lg font-bold text-indigo-700 mt-0.5">
                {crossAgent.collaboration_stats.total_liveops_events}
              </div>
            </div>
            <div className="bg-purple-50 border border-purple-100 rounded-lg p-2.5">
              <div className="flex items-center gap-1.5">
                <Briefcase className="w-3.5 h-3.5 text-purple-600" />
                <span className="text-[10px] font-medium text-purple-700">CEO 触发</span>
              </div>
              <div className="text-lg font-bold text-purple-700 mt-0.5">
                {crossAgent.collaboration_stats.ceo_liveops_triggered ? "已触发" : "未触发"}
              </div>
            </div>
            <div className="bg-blue-50 border border-blue-100 rounded-lg p-2.5">
              <div className="flex items-center gap-1.5">
                <Bell className="w-3.5 h-3.5 text-blue-600" />
                <span className="text-[10px] font-medium text-blue-700">广播类型</span>
              </div>
              <div className="text-lg font-bold text-blue-700 mt-0.5">
                {crossAgent.collaboration_stats.broadcast_types.length}
              </div>
            </div>
            <div className="bg-green-50 border border-green-100 rounded-lg p-2.5">
              <div className="flex items-center gap-1.5">
                <Database className="w-3.5 h-3.5 text-green-600" />
                <span className="text-[10px] font-medium text-green-700">回流通道</span>
              </div>
              <div className="text-lg font-bold text-green-700 mt-0.5">
                {crossAgent.collaboration_stats.feedback_channels.length}
              </div>
            </div>
          </div>

          {/* 最近 LiveOps 事件流 */}
          {crossAgent.recent_events.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
                最近 LiveOps 事件流 (CEO Memory)
              </div>
              {crossAgent.recent_events.slice(-8).reverse().map((evt, idx) => {
                const actionColors: Record<string, string> = {
                  push_notification: "text-blue-600 bg-blue-50",
                  reward_grant: "text-green-600 bg-green-50",
                  email: "text-orange-600 bg-orange-50",
                  in_app_message: "text-purple-600 bg-purple-50",
                };
                return (
                  <div key={idx} className="flex items-center gap-2 text-xs bg-white rounded px-2 py-1.5 border border-gray-100">
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${actionColors[evt.action_type] || "text-gray-600 bg-gray-50"}`}>
                      {evt.action_type}
                    </span>
                    <span className="text-gray-500">·</span>
                    <span className="font-mono text-gray-600 text-[10px]">{evt.game_id}</span>
                    <span className="text-gray-500">·</span>
                    <span className="text-gray-700 truncate max-w-[300px]">{evt.detail}</span>
                    <span className={`ml-auto px-1.5 py-0.5 rounded text-[10px] font-medium ${
                      evt.success ? "text-green-600 bg-green-50" : "text-red-600 bg-red-50"
                    }`}>
                      {evt.status}
                    </span>
                    <span className="text-[10px] text-gray-400">
                      {new Date(evt.created_at).toLocaleString("zh-CN", { hour: "2-digit", minute: "2-digit", month: "2-digit", day: "2-digit" })}
                    </span>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Growth 响应 LiveOps — 双向协同 */}
      {churnResponseStats && (
        <div className="bg-white border border-[#e5e5e5] rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-orange-500" />
            <h2 className="text-lg font-bold text-gray-900">Growth 响应 LiveOps</h2>
            <span className="text-xs text-gray-500">churn_alert → UA 动作建议</span>
            <button
              onClick={refreshChurnResponses}
              className="text-xs text-gray-400 hover:text-gray-600 ml-auto"
            >
              刷新
            </button>
          </div>

          {/* 响应统计卡片 */}
          <div className="grid grid-cols-4 gap-2">
            <div className="bg-orange-50 border border-orange-100 rounded-lg p-2.5">
              <div className="flex items-center gap-1.5">
                <AlertTriangle className="w-3.5 h-3.5 text-orange-600" />
                <span className="text-[10px] font-medium text-orange-700">响应总数</span>
              </div>
              <div className="text-lg font-bold text-orange-700 mt-0.5">
                {churnResponseStats.total_responses}
              </div>
            </div>
            <div className="bg-red-50 border border-red-100 rounded-lg p-2.5">
              <div className="flex items-center gap-1.5">
                <Pause className="w-3.5 h-3.5 text-red-600" />
                <span className="text-[10px] font-medium text-red-700">高严重度</span>
              </div>
              <div className="text-lg font-bold text-red-700 mt-0.5">
                {churnResponseStats.severity_distribution.high}
              </div>
            </div>
            <div className="bg-yellow-50 border border-yellow-100 rounded-lg p-2.5">
              <div className="flex items-center gap-1.5">
                <TrendingDown className="w-3.5 h-3.5 text-yellow-600" />
                <span className="text-[10px] font-medium text-yellow-700">中严重度</span>
              </div>
              <div className="text-lg font-bold text-yellow-700 mt-0.5">
                {churnResponseStats.severity_distribution.medium}
              </div>
            </div>
            <div className="bg-blue-50 border border-blue-100 rounded-lg p-2.5">
              <div className="flex items-center gap-1.5">
                <PieChart className="w-3.5 h-3.5 text-blue-600" />
                <span className="text-[10px] font-medium text-blue-700">动作类型</span>
              </div>
              <div className="text-lg font-bold text-blue-700 mt-0.5">
                {Object.keys(churnResponseStats.action_type_distribution).length}
              </div>
            </div>
          </div>

          {/* 动作类型分布 */}
          {Object.keys(churnResponseStats.action_type_distribution).length > 0 && (
            <div className="bg-gray-50 border border-gray-100 rounded-lg p-3">
              <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-2">动作类型分布</div>
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(churnResponseStats.action_type_distribution).map(([type, count]) => {
                  const typeColors: Record<string, string> = {
                    pause_campaign: "text-red-600 bg-red-50",
                    reallocate_budget: "text-blue-600 bg-blue-50",
                    reduce_budget: "text-yellow-600 bg-yellow-50",
                    monitor: "text-gray-600 bg-gray-50",
                  };
                  const typeIcons: Record<string, typeof Pause> = {
                    pause_campaign: Pause,
                    reallocate_budget: PieChart,
                    reduce_budget: TrendingDown,
                    monitor: BarChart3,
                  };
                  const Icon = typeIcons[type] || BarChart3;
                  return (
                    <span key={type} className={`px-2 py-1 rounded text-[10px] font-medium flex items-center gap-1 ${typeColors[type] || "text-gray-600 bg-gray-50"}`}>
                      <Icon className="w-3 h-3" />
                      {type} × {count}
                    </span>
                  );
                })}
              </div>
            </div>
          )}

          {/* 最近响应记录 */}
          {churnResponses.length > 0 && (
            <div className="space-y-2">
              <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">
                最近响应记录
              </div>
              {churnResponses.slice(0, 8).map((resp, idx) => {
                const sevColors: Record<string, string> = {
                  high: "border-red-200 bg-red-50",
                  medium: "border-yellow-200 bg-yellow-50",
                  low: "border-gray-200 bg-gray-50",
                };
                const sevBadge: Record<string, string> = {
                  high: "text-red-600 bg-red-100",
                  medium: "text-yellow-600 bg-yellow-100",
                  low: "text-gray-600 bg-gray-100",
                };
                return (
                  <div key={idx} className={`border rounded-lg p-3 space-y-2 ${sevColors[resp.severity] || sevColors.low}`}>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${sevBadge[resp.severity] || sevBadge.low}`}>
                        {resp.severity.toUpperCase()}
                      </span>
                      <span className="font-mono text-xs text-gray-700">{resp.game_id}</span>
                      <span className="text-gray-400">·</span>
                      <span className="text-xs text-gray-600">高价值流失 {resp.high_value_at_risk} 人</span>
                      <span className="text-gray-400">·</span>
                      <span className="text-xs text-gray-600">{resp.action_count} 个动作</span>
                      {/* 执行状态徽章 */}
                      {resp.status === "executed" && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium text-green-600 bg-green-100 flex items-center gap-1">
                          <CheckCircle className="w-3 h-3" />
                          已执行{resp.dry_run ? " (模拟)" : ""}
                        </span>
                      )}
                      {resp.status === "partial_executed" && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium text-orange-600 bg-orange-100">
                          部分执行
                        </span>
                      )}
                      {resp.status === "rolled_back" && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium text-gray-600 bg-gray-200 flex items-center gap-1">
                          <Undo2 className="w-3 h-3" />
                          已回滚
                        </span>
                      )}
                      {resp.status === "suggested" && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-medium text-blue-600 bg-blue-100">
                          待执行
                        </span>
                      )}
                      {/* 回滚按钮 — 仅 executed/partial_executed 可回滚 */}
                      {(resp.status === "executed" || resp.status === "partial_executed") && (
                        <button
                          onClick={() => handleRollbackResponse(resp.response_id)}
                          disabled={liveopsLoading}
                          className="ml-auto flex items-center gap-1 px-2 py-1 rounded text-[10px] font-medium text-gray-600 bg-white border border-gray-200 hover:bg-gray-50 disabled:opacity-50"
                        >
                          <Undo2 className="w-3 h-3" />
                          回滚
                        </button>
                      )}
                      {resp.status !== "executed" && resp.status !== "partial_executed" && (
                        <span className="text-[10px] text-gray-400 ml-auto">
                          {new Date(resp.created_at).toLocaleString("zh-CN", { hour: "2-digit", minute: "2-digit", month: "2-digit", day: "2-digit" })}
                        </span>
                      )}
                    </div>
                    {/* 动作列表 */}
                    <div className="space-y-1">
                      {resp.actions.map((action, aidx) => {
                        const actionColors: Record<string, string> = {
                          pause_campaign: "text-red-600 bg-red-50",
                          reallocate_budget: "text-blue-600 bg-blue-50",
                          reduce_budget: "text-yellow-600 bg-yellow-50",
                          monitor: "text-gray-600 bg-gray-50",
                        };
                        return (
                          <div key={aidx} className="flex items-start gap-2 text-xs bg-white rounded px-2 py-1.5 border border-gray-100">
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${actionColors[action.action_type] || "text-gray-600 bg-gray-50"}`}>
                              {action.action_type}
                            </span>
                            <span className="text-gray-700 flex-1">{action.reason}</span>
                            {action.ratio && (
                              <span className="text-[10px] text-gray-500 font-mono">
                                {Math.round(action.ratio * 100)}%
                              </span>
                            )}
                            {/* 执行结果 */}
                            {action.execution_result && (
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                action.execution_result.success
                                  ? "text-green-600 bg-green-50"
                                  : "text-red-600 bg-red-50"
                              }`}>
                                {action.execution_result.status === "simulated" ? "模拟" : "已执行"}
                              </span>
                            )}
                            {/* 回滚结果 */}
                            {action.rollback_result && (
                              <span className="px-1.5 py-0.5 rounded text-[10px] font-medium text-gray-600 bg-gray-100">
                                已回滚
                              </span>
                            )}
                            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                              action.priority === "high" ? "text-red-600 bg-red-50" :
                              action.priority === "medium" ? "text-yellow-600 bg-yellow-50" :
                              "text-gray-500 bg-gray-50"
                            }`}>
                              {action.priority}
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {churnResponses.length === 0 && (
            <div className="text-center text-xs text-gray-400 py-4">
              暂无 Growth 响应记录 — LiveOps 设计回流活动时将自动触发
            </div>
          )}
        </div>
      )}

      {/* 系统监控仪表盘 */}
      {monitor && (
        <div className="bg-white border border-[#e5e5e5] rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-indigo-500" />
            <h2 className="text-lg font-bold text-gray-900">系统监控</h2>
            <span className="text-xs text-gray-500">健康状态 · 告警 · 数据文件</span>
            <button
              onClick={refreshMonitor}
              className="text-xs text-gray-400 hover:text-gray-600 ml-auto"
            >
              刷新
            </button>
          </div>

          {/* 健康状态总览 */}
          <div className="grid grid-cols-4 gap-2">
            <div className={`border rounded-lg p-3 ${
              monitor.health.status === "healthy" ? "bg-green-50 border-green-200" :
              monitor.health.status === "degraded" ? "bg-yellow-50 border-yellow-200" :
              "bg-red-50 border-red-200"
            }`}>
              <div className="flex items-center gap-1.5">
                <ShieldAlert className={`w-4 h-4 ${
                  monitor.health.status === "healthy" ? "text-green-600" :
                  monitor.health.status === "degraded" ? "text-yellow-600" :
                  "text-red-600"
                }`} />
                <span className="text-xs font-medium text-gray-700">系统状态</span>
              </div>
              <div className={`text-lg font-bold mt-1 ${
                monitor.health.status === "healthy" ? "text-green-700" :
                monitor.health.status === "degraded" ? "text-yellow-700" :
                "text-red-700"
              }`}>
                {monitor.health.status === "healthy" ? "健康" :
                 monitor.health.status === "degraded" ? "降级" : "严重"}
              </div>
            </div>
            <div className="bg-red-50 border border-red-100 rounded-lg p-3">
              <div className="flex items-center gap-1.5">
                <AlertCircle className="w-4 h-4 text-red-600" />
                <span className="text-xs font-medium text-red-700">Critical 告警</span>
              </div>
              <div className="text-lg font-bold text-red-700 mt-1">
                {monitor.health.critical_alerts}
              </div>
            </div>
            <div className="bg-yellow-50 border border-yellow-100 rounded-lg p-3">
              <div className="flex items-center gap-1.5">
                <AlertCircle className="w-4 h-4 text-yellow-600" />
                <span className="text-xs font-medium text-yellow-700">Warning 告警</span>
              </div>
              <div className="text-lg font-bold text-yellow-700 mt-1">
                {monitor.health.warning_alerts}
              </div>
            </div>
            <div className="bg-blue-50 border border-blue-100 rounded-lg p-3">
              <div className="flex items-center gap-1.5">
                <Clock className="w-4 h-4 text-blue-600" />
                <span className="text-xs font-medium text-blue-700">总告警数</span>
              </div>
              <div className="text-lg font-bold text-blue-700 mt-1">
                {monitor.health.alerts_count}
              </div>
            </div>
          </div>

          {/* 子系统统计 */}
          <div className="grid grid-cols-4 gap-2">
            <div className="bg-gray-50 border border-gray-100 rounded-lg p-3">
              <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1">GrowthLoop</div>
              <div className="text-sm font-bold text-gray-900">{monitor.growth_loop.total_cycles} cycles</div>
              <div className="text-[10px] text-gray-500 mt-0.5">
                成功率 {(monitor.growth_loop.success_rate * 100).toFixed(0)}%
              </div>
            </div>
            <div className="bg-gray-50 border border-gray-100 rounded-lg p-3">
              <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1">LiveOps</div>
              <div className="text-sm font-bold text-gray-900">{monitor.liveops.total_executions} execs</div>
              <div className="text-[10px] text-gray-500 mt-0.5">
                成功率 {(monitor.liveops.success_rate * 100).toFixed(0)}%
              </div>
            </div>
            <div className="bg-gray-50 border border-gray-100 rounded-lg p-3">
              <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1">ChurnAlert</div>
              <div className="text-sm font-bold text-gray-900">{monitor.churn_alert.total_responses} responses</div>
              <div className="text-[10px] text-gray-500 mt-0.5">
                已执行 {monitor.churn_alert.executed} · 已回滚 {monitor.churn_alert.rolled_back}
              </div>
            </div>
            <div className="bg-gray-50 border border-gray-100 rounded-lg p-3">
              <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide mb-1">审批队列</div>
              <div className="text-sm font-bold text-gray-900">{monitor.approval_queue.total_pending} pending</div>
              <div className="text-[10px] text-gray-500 mt-0.5">
                CEO {monitor.approval_queue.ceo_pending} · LiveOps {monitor.approval_queue.liveops_pending}
              </div>
            </div>
          </div>

          {/* 告警列表 */}
          {monitor.alerts.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide">告警详情</div>
              {monitor.alerts.slice(0, 8).map((alert, idx) => {
                const sevColors: Record<string, string> = {
                  critical: "border-red-200 bg-red-50",
                  warning: "border-yellow-200 bg-yellow-50",
                  info: "border-blue-200 bg-blue-50",
                };
                const sevBadge: Record<string, string> = {
                  critical: "text-red-600 bg-red-100",
                  warning: "text-yellow-600 bg-yellow-100",
                  info: "text-blue-600 bg-blue-100",
                };
                return (
                  <div key={idx} className={`border rounded-lg p-2.5 ${sevColors[alert.severity] || sevColors.info}`}>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${sevBadge[alert.severity] || sevBadge.info}`}>
                        {alert.severity.toUpperCase()}
                      </span>
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium text-gray-600 bg-gray-100">
                        {alert.category}
                      </span>
                      <span className="text-xs text-gray-700 flex-1">{alert.message}</span>
                    </div>
                    {alert.suggestion && (
                      <div className="text-[10px] text-gray-500 mt-1 ml-1">
                        建议: {alert.suggestion}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}

          {/* JSONL 数据文件监控 */}
          <div className="space-y-1.5">
            <div className="text-[10px] font-medium text-gray-500 uppercase tracking-wide flex items-center gap-1">
              <HardDrive className="w-3 h-3" />
              JSONL 数据文件
            </div>
            <div className="grid grid-cols-2 gap-1.5">
              {Object.entries(monitor.data_files).map(([name, stats]) => (
                <div key={name} className={`border rounded p-2 text-xs ${
                  stats.exists ? "bg-white border-gray-200" : "bg-gray-50 border-gray-200 border-dashed"
                }`}>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] text-gray-700 truncate">{name}</span>
                    {stats.exists ? (
                      <span className="text-[10px] text-gray-400">
                        {stats.size_mb}MB · {stats.record_count} 行
                      </span>
                    ) : (
                      <span className="text-[10px] text-gray-400">不存在</span>
                    )}
                  </div>
                  {stats.exists && (
                    <div className="text-[10px] text-gray-400 mt-0.5">
                      {stats.hours_since_update < 1 ? "刚刚" :
                       stats.hours_since_update < 24 ? `${stats.hours_since_update.toFixed(0)} 小时前` :
                       `${(stats.hours_since_update / 24).toFixed(1)} 天前`}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-4 gap-4">
        <KPICard icon={Gamepad2} label="Games" value={kpi.games.toString()} color="text-purple-500" />
        <KPICard icon={Users} label="Total DAU" value={formatNumber(kpi.total_dau)} color="text-blue-500" />
        <KPICard icon={DollarSign} label="Revenue / day" value={formatCurrency(kpi.total_revenue)} color="text-green-500" />
        <KPICard icon={TrendingUp} label="Avg ROAS" value={kpi.avg_roas.toFixed(2)} color="text-indigo-500" />
        <KPICard icon={DollarSign} label="Spend / day" value={formatCurrency(kpi.total_spend)} color="text-orange-500" />
        <KPICard icon={Target} label="Avg LTV" value={"$" + kpi.avg_ltv.toFixed(2)} color="text-cyan-500" />
        <KPICard icon={Bot} label="AI Tasks" value={kpi.ai_tasks.toString()} color="text-pink-500" />
        <KPICard icon={Zap} label="Automation" value={(kpi.automation_rate * 100).toFixed(0) + "%"} color="text-yellow-500" />
      </div>

      {/* GrowthLoop 执行历史 */}
      {loopHistory.length > 0 && (
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <RotateCw className="w-4 h-4 text-indigo-500" />
              <h2 className="text-sm font-semibold text-gray-900">GrowthLoop 执行历史</h2>
            </div>
            <button
              onClick={refreshLoopHistory}
              className="text-xs text-gray-500 hover:text-indigo-500 flex items-center gap-1"
            >
              <RotateCw className="w-3 h-3" />
              刷新
            </button>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-gray-500 border-b border-gray-200">
                  <th className="text-left py-2 px-2 font-medium">Cycle</th>
                  <th className="text-left py-2 px-2 font-medium">完成时间</th>
                  <th className="text-center py-2 px-2 font-medium">信号</th>
                  <th className="text-center py-2 px-2 font-medium">动作</th>
                  <th className="text-center py-2 px-2 font-medium">执行</th>
                  <th className="text-center py-2 px-2 font-medium">成功率</th>
                  <th className="text-left py-2 px-2 font-medium">动作类型</th>
                  <th className="text-center py-2 px-2 font-medium">模式</th>
                </tr>
              </thead>
              <tbody>
                {loopHistory.map((c) => (
                  <tr key={c.cycle_number} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-2 font-mono font-medium text-gray-900">#{c.cycle_number}</td>
                    <td className="py-2 px-2 text-gray-500">{formatTime(c.completed_at)}</td>
                    <td className="py-2 px-2 text-center text-gray-600">{c.signal_count}</td>
                    <td className="py-2 px-2 text-center text-gray-600">{c.actions_planned}</td>
                    <td className="py-2 px-2 text-center text-gray-600">{c.actions_executed}</td>
                    <td className="py-2 px-2 text-center">
                      <span className={`font-medium ${c.success_rate >= 0.8 ? "text-green-600" : c.success_rate >= 0.5 ? "text-yellow-600" : "text-red-600"}`}>
                        {(c.success_rate * 100).toFixed(0)}%
                      </span>
                    </td>
                    <td className="py-2 px-2">
                      <div className="flex flex-wrap gap-1">
                        {Object.entries(c.action_types).map(([type, count]) => (
                          <span key={type} className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${actionTypeColors[type] || "text-gray-600 bg-gray-50"}`}>
                            {type} ×{count}
                          </span>
                        ))}
                        {Object.keys(c.action_types).length === 0 && (
                          <span className="text-gray-400 text-[11px]">-</span>
                        )}
                      </div>
                    </td>
                    <td className="py-2 px-2 text-center">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${c.dry_run ? "text-yellow-600 bg-yellow-50" : "text-green-600 bg-green-50"}`}>
                        {c.dry_run ? "Dry" : "Live"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Two Column: Briefing + Active Tasks */}
      <div className="grid grid-cols-2 gap-6">
        {/* Daily Briefing */}
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <ActivityIcon className="w-4 h-4 text-indigo-500" />
            <h2 className="text-sm font-semibold text-gray-900">今日 AI 简报</h2>
          </div>
          <div className="space-y-3">
            {briefing.highlights.map((h, i) => (
              <div key={i} className={`p-3 rounded-lg ${statusColors[h.type] || statusColors.info}`}>
                <div className="font-medium text-sm">{h.title}</div>
                <div className="text-xs opacity-70 mt-1">{h.detail}</div>
                <div className="text-xs mt-1 font-medium">{h.suggestion}</div>
              </div>
            ))}
          </div>
          {briefing.alerts.length > 0 && (
            <div className="mt-4 pt-4 border-t border-[#e5e5e5]">
              <div className="text-xs text-gray-500 mb-2">Alerts</div>
              <div className="space-y-2">
                {briefing.alerts.map((a, i) => (
                  <div key={i} className={`p-2 rounded text-xs ${statusColors[a.type] || statusColors.info}`}>
                    <span className="font-medium">{a.title}</span>
                    <span className="opacity-70 ml-2">{a.detail}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Active Tasks */}
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6">
          <div className="flex items-center gap-2 mb-4">
            <Bot className="w-4 h-4 text-indigo-500" />
            <h2 className="text-sm font-semibold text-gray-900">正在执行的任务</h2>
          </div>
          <div className="space-y-3">
            {active_tasks.map((task) => (
              <div key={task.id} className="p-3 rounded-lg bg-[#f5f5f5]">
                <div className="flex items-center justify-between mb-2">
                  <div className="text-sm font-medium text-gray-900">{task.title}</div>
                  <span className="text-xs text-gray-500">{task.progress}%</span>
                </div>
                <div className="w-full h-1.5 bg-[#e5e5e5] rounded-full overflow-hidden">
                  <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${task.progress}%` }} />
                </div>
                <div className="flex items-center gap-2 mt-2">
                  <span className="text-xs text-gray-500">{task.agent_name}</span>
                  <span className="text-xs text-gray-400">·</span>
                  <span className="text-xs text-gray-500">{task.game_name}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Games + Recent Events */}
      <div className="grid grid-cols-2 gap-6">
        {/* Games */}
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6">
          <h2 className="text-sm font-semibold text-gray-900 mb-4">游戏组合</h2>
          <div className="space-y-2">
            {games.map((game) => (
              <div key={game.id} className="flex items-center justify-between p-3 rounded-lg bg-[#f5f5f5] hover:bg-[#eee] transition-colors">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500/20 to-purple-500/20 flex items-center justify-center">
                    <Gamepad2 className="w-5 h-5 text-indigo-500" />
                  </div>
                  <div>
                    <div className="text-sm font-medium text-gray-900">{game.name}</div>
                    <div className="text-xs text-gray-500">{game.genre} · {game.market}</div>
                  </div>
                </div>
                <div className="flex items-center gap-4">
                  <div className="text-right">
                    <div className="text-sm text-gray-900">{formatCurrency(game.revenue)}/d</div>
                    <div className="text-xs text-gray-500">{formatNumber(game.dau)} DAU</div>
                  </div>
                  <span className={`px-2 py-1 rounded text-xs font-medium ${gameStatusColors[game.status] || gameStatusColors.stable}`}>
                    {game.status}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Live Event Stream (SSE) */}
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6">
          <LiveEventStream maxItems={8} />
        </div>
      </div>
    </div>
  );
}

function KPICard({
  icon: Icon,
  label,
  value,
  color,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  color: string;
}) {
  return (
    <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-gray-500">{label}</span>
        <Icon className={`w-4 h-4 ${color}`} />
      </div>
      <div className="text-xl font-bold text-gray-900">{value}</div>
    </div>
  );
}
