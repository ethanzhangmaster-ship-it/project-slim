"use client";

import { useEffect, useState } from "react";
import { api, type MemoryData } from "@/lib/api";
import { Brain, CheckCircle2, XCircle, TrendingUp, Activity, Database, Clock } from "lucide-react";

const verdictColors: Record<string, string> = {
  EXECUTED: "text-green-400 bg-green-500/10",
  SIMULATED: "text-blue-400 bg-blue-500/10",
  REJECTED: "text-red-400 bg-red-500/10",
  BLOCKED: "text-yellow-400 bg-yellow-500/10",
};

const domainColors: Record<string, string> = {
  creative: "text-purple-400 bg-purple-500/10",
  revenue: "text-yellow-400 bg-yellow-500/10",
  acquisition: "text-blue-400 bg-blue-500/10",
  product: "text-green-400 bg-green-500/10",
};

function formatTime(ts: string): string {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString("zh-CN", {
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

export default function MemoryPage() {
  const [data, setData] = useState<MemoryData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getMemory(50).then(setData).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-gray-500">Loading memory...</div>
      </div>
    );
  }

  if (!data) {
    return <div className="p-8 text-red-400">Failed to load memory data</div>;
  }

  return (
    <div className="p-8 max-w-6xl space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 mb-1">
          <Brain className="w-5 h-5 text-indigo-400" />
          <h1 className="text-2xl font-bold text-gray-900">Memory System</h1>
        </div>
        <p className="text-sm text-gray-500">执行记忆 · 经验学习 · 操作员日志</p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-gray-500">执行记忆</span>
          </div>
          <div className="text-2xl font-bold text-gray-900">{data.summary.total_executions}</div>
          <div className="text-xs text-gray-500 mt-1">
            成功率 {Math.round(data.summary.success_rate * 100)}%
          </div>
        </div>
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-green-400" />
            <span className="text-xs text-gray-500">经验学习</span>
          </div>
          <div className="text-2xl font-bold text-gray-900">{data.summary.total_experiences}</div>
          <div className="text-xs text-gray-500 mt-1">
            正向率 {Math.round(data.summary.positive_rate * 100)}%
          </div>
        </div>
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Database className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-gray-500">操作员日志</span>
          </div>
          <div className="text-2xl font-bold text-gray-900">{data.summary.operator_logs}</div>
          <div className="text-xs text-gray-500 mt-1">天数</div>
        </div>
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle2 className="w-4 h-4 text-green-400" />
            <span className="text-xs text-gray-500">成功执行</span>
          </div>
          <div className="text-2xl font-bold text-gray-900">{data.summary.successful_executions}</div>
          <div className="text-xs text-gray-500 mt-1">次</div>
        </div>
      </div>

      {/* Execution Memory */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-400" />
          执行记忆 (最近 {data.execution_memory.length} 条)
        </h2>
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#fafafa] border-b border-[#e5e5e5]">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">时间</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">游戏</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">领域</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">策略</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">状态</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">详情</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e5e5e5]">
              {data.execution_memory.slice(0, 15).map((m) => (
                <tr key={m.execution_id} className="hover:bg-[#fafafa]">
                  <td className="px-4 py-3 text-xs text-gray-500">{formatTime(m.created_at)}</td>
                  <td className="px-4 py-3 text-xs text-gray-900">{m.game_id}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${domainColors[m.domain] || domainColors.product}`}>
                      {m.domain}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-900">{m.strategy_type}</td>
                  <td className="px-4 py-3">
                    {m.success ? (
                      <CheckCircle2 className="w-4 h-4 text-green-400" />
                    ) : (
                      <XCircle className="w-4 h-4 text-red-400" />
                    )}
                  </td>
                  <td className="px-4 py-3 text-xs text-gray-500 max-w-xs truncate">{m.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Execution Experience */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <TrendingUp className="w-4 h-4 text-green-400" />
          经验学习 (闭环反馈, 最近 {data.execution_experience.length} 条)
        </h2>
        <div className="grid grid-cols-2 gap-4">
          {data.execution_experience.slice(0, 10).map((exp) => (
            <div key={exp.record_id} className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-4">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900">{exp.action}</span>
                  {exp.reward > 0 ? (
                    <span className="text-xs text-green-400">+{exp.reward.toFixed(2)}</span>
                  ) : (
                    <span className="text-xs text-red-400">{exp.reward.toFixed(2)}</span>
                  )}
                </div>
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${verdictColors[exp.verdict] || verdictColors.SIMULATED}`}>
                  {exp.verdict}
                </span>
              </div>
              <div className="text-xs text-gray-500 space-y-1">
                <div>上下文: {JSON.stringify(exp.context).slice(0, 80)}</div>
                <div>结果: {JSON.stringify(exp.result).slice(0, 80)}</div>
                <div className="flex items-center gap-1">
                  <Clock className="w-3 h-3" />
                  {formatTime(exp.timestamp)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Operator Memory */}
      <div>
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Database className="w-4 h-4 text-purple-400" />
          操作员日志 (最近 {data.operator_memory.length} 天)
        </h2>
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-[#fafafa] border-b border-[#e5e5e5]">
              <tr>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">日期</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">决策</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">已执行</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">已批准</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">已阻塞</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">收入影响</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500">状态</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#e5e5e5]">
              {data.operator_memory.slice(0, 14).map((log, i) => (
                <tr key={i} className="hover:bg-[#fafafa]">
                  <td className="px-4 py-3 text-xs text-gray-900">{log.date}</td>
                  <td className="px-4 py-3 text-xs text-gray-900">{log.decisions}</td>
                  <td className="px-4 py-3 text-xs text-green-400">{log.executed}</td>
                  <td className="px-4 py-3 text-xs text-blue-400">{log.approved}</td>
                  <td className="px-4 py-3 text-xs text-red-400">{log.blocked}</td>
                  <td className="px-4 py-3 text-xs text-gray-900">${log.revenue_impact.toFixed(0)}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                      log.company_status === "healthy" ? "text-green-400 bg-green-500/10" :
                      log.company_status === "warning" ? "text-yellow-400 bg-yellow-500/10" :
                      "text-red-400 bg-red-500/10"
                    }`}>
                      {log.company_status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
