"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { api, type Agent, type Task, type Decision } from "@/lib/api";
import { CheckCircle2, Circle, ArrowLeft } from "lucide-react";
import Link from "next/link";

const statusColors: Record<string, string> = {
  running: "text-green-400 bg-green-500/10",
  idle: "text-gray-400 bg-gray-400/10",
  offline: "text-red-400 bg-red-500/10",
};

interface AgentDetail extends Agent {
  tasks: Task[];
  decisions: Decision[];
}

export default function AgentDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [agent, setAgent] = useState<AgentDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) api.getAgent(id).then(setAgent).finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-gray-500">Loading agent...</div>
      </div>
    );
  }

  if (!agent) {
    return (
      <div className="p-8">
        <div className="text-red-400">Agent not found</div>
        <Link href="/organization" className="text-indigo-400 text-sm mt-4 inline-block">← Back to Organization</Link>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl">
      <Link href="/organization" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900 mb-6">
        <ArrowLeft className="w-4 h-4" /> Back to Organization
      </Link>

      {/* Agent Header */}
      <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6 mb-6">
        <div className="flex items-center gap-4">
          <div
            className="w-16 h-16 rounded-xl flex items-center justify-center text-gray-900 font-bold text-xl"
            style={{ backgroundColor: agent.avatar_color }}
          >
            {agent.name.charAt(0)}
          </div>
          <div className="flex-1">
            <h1 className="text-xl font-bold text-gray-900">{agent.name}</h1>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-sm text-gray-500">{agent.department}</span>
              <span className={`px-2 py-0.5 rounded text-xs ${statusColors[agent.status] || statusColors.idle}`}>
                {agent.status}
              </span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-gray-900">{(agent.confidence * 100).toFixed(0)}%</div>
            <div className="text-xs text-gray-500">Confidence</div>
          </div>
        </div>

        {/* Capabilities */}
        <div className="mt-6">
          <h3 className="text-xs text-gray-500 mb-2">Capabilities</h3>
          <div className="flex flex-wrap gap-2">
            {agent.capabilities.map((cap) => (
              <span key={cap} className="px-3 py-1 rounded-lg bg-[#f5f5f5] text-xs text-gray-700 border border-[#e5e5e5]">
                {cap}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* Current Tasks */}
      <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6 mb-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-4">当前任务</h2>
        <div className="space-y-3">
          {agent.tasks.map((task) => (
            <div key={task.id} className="p-4 rounded-lg bg-[#f5f5f5]">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-gray-900">{task.title}</span>
                <span className="text-xs text-gray-500">{task.progress}%</span>
              </div>
              <div className="w-full h-1.5 bg-[#e5e5e5] rounded-full overflow-hidden mb-3">
                <div className="h-full bg-indigo-500 rounded-full" style={{ width: `${task.progress}%` }} />
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                {task.steps.map((step, i) => (
                  <div key={i} className="flex items-center gap-1 text-xs">
                    {step.done ? (
                      <CheckCircle2 className="w-3 h-3 text-green-400" />
                    ) : (
                      <Circle className="w-3 h-3 text-gray-600" />
                    )}
                    <span className={step.done ? "text-gray-700" : "text-gray-600"}>{step.name}</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
          {agent.tasks.length === 0 && (
            <div className="text-sm text-gray-500">暂无任务</div>
          )}
        </div>
      </div>

      {/* Recent Decisions */}
      <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-4">最近决策</h2>
        <div className="space-y-3">
          {agent.decisions.map((d) => (
            <div key={d.id} className="p-4 rounded-lg bg-[#f5f5f5]">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-900">{d.action}</span>
                <span className="text-xs text-indigo-400">{(d.confidence * 100).toFixed(0)}%</span>
              </div>
              <p className="text-xs text-gray-400 mb-2">{d.reason}</p>
              <div className="flex items-center gap-2 text-xs">
                <span className="text-green-400">{d.impact}</span>
                <span className="text-gray-600">·</span>
                <span className="text-gray-500">{d.game_name}</span>
              </div>
            </div>
          ))}
          {agent.decisions.length === 0 && (
            <div className="text-sm text-gray-500">暂无决策</div>
          )}
        </div>
      </div>
    </div>
  );
}
