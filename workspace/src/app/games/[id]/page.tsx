"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api, type Game, type Event, type Task } from "@/lib/api";
import { ArrowLeft, Gamepad2, Users, DollarSign, TrendingUp, Activity, Bot, CheckCircle2, Clock } from "lucide-react";

interface GameDetail extends Game {
  recent_events: Event[];
  tasks: Task[];
  ai_team: Array<{ id: string; name: string }>;
}

const statusColors: Record<string, string> = {
  growing: "text-green-400 bg-green-500/10",
  stable: "text-blue-400 bg-blue-500/10",
  declining: "text-red-400 bg-red-500/10",
  launching: "text-purple-400 bg-purple-500/10",
};

function formatNumber(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return n.toString();
}

function formatCurrency(n: number): string {
  if (n >= 1000) return "$" + (n / 1000).toFixed(1) + "K";
  return "$" + n.toFixed(0);
}

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

export default function GameDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [game, setGame] = useState<GameDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (id) api.getGame(id).then(setGame).finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-gray-500">Loading game...</div>
      </div>
    );
  }

  if (!game) {
    return (
      <div className="p-8">
        <div className="text-red-400">Game not found</div>
        <Link href="/games" className="text-indigo-400 text-sm mt-4 inline-block">← Back to Games</Link>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-5xl space-y-6">
      <Link href="/games" className="inline-flex items-center gap-1 text-sm text-gray-500 hover:text-gray-900">
        <ArrowLeft className="w-4 h-4" /> Back to Games
      </Link>

      {/* Game Header */}
      <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-16 h-16 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 flex items-center justify-center">
              <Gamepad2 className="w-8 h-8 text-indigo-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900">{game.name}</h1>
              <p className="text-sm text-gray-500 mt-1">
                {game.genre} · {game.market} · ID: {game.id}
              </p>
            </div>
          </div>
          <span className={`px-3 py-1 rounded-lg text-sm font-medium ${statusColors[game.status] || statusColors.stable}`}>
            {game.status}
          </span>
        </div>

        {/* Health Score */}
        <div className="mt-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm text-gray-500">Health Score</span>
            <span className="text-lg font-bold text-gray-900">{game.health_score}</span>
          </div>
          <div className="w-full h-2 bg-[#e5e5e5] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full ${
                game.health_score >= 80 ? "bg-green-500" :
                game.health_score >= 60 ? "bg-yellow-500" : "bg-red-500"
              }`}
              style={{ width: `${game.health_score}%` }}
            />
          </div>
        </div>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <Users className="w-4 h-4 text-blue-400" />
            <span className="text-xs text-gray-500">DAU</span>
          </div>
          <div className="text-2xl font-bold text-gray-900">{formatNumber(game.dau)}</div>
        </div>
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-4 h-4 text-green-400" />
            <span className="text-xs text-gray-500">Revenue / day</span>
          </div>
          <div className="text-2xl font-bold text-gray-900">{formatCurrency(game.revenue)}</div>
        </div>
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-4 h-4 text-purple-400" />
            <span className="text-xs text-gray-500">ROAS</span>
          </div>
          <div className="text-2xl font-bold text-gray-900">{game.roas.toFixed(2)}</div>
        </div>
        <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-5">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-4 h-4 text-yellow-400" />
            <span className="text-xs text-gray-500">Spend / day</span>
          </div>
          <div className="text-2xl font-bold text-gray-900">{formatCurrency(game.spend)}</div>
        </div>
      </div>

      {/* Retention Metrics */}
      <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-4">Retention & LTV</h2>
        <div className="grid grid-cols-4 gap-4">
          <div>
            <div className="text-xs text-gray-500">D1 Retention</div>
            <div className="text-lg font-medium text-gray-900 mt-1">
              {game.retention_d1 > 0 ? `${(game.retention_d1 * 100).toFixed(1)}%` : "—"}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">D7 Retention</div>
            <div className="text-lg font-medium text-gray-900 mt-1">
              {game.retention_d7 > 0 ? `${(game.retention_d7 * 100).toFixed(1)}%` : "—"}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">D30 Retention</div>
            <div className="text-lg font-medium text-gray-900 mt-1">
              {game.retention_d30 > 0 ? `${(game.retention_d30 * 100).toFixed(1)}%` : "—"}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">LTV</div>
            <div className="text-lg font-medium text-gray-900 mt-1">${game.ltv.toFixed(2)}</div>
          </div>
        </div>
      </div>

      {/* AI Team */}
      <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Bot className="w-4 h-4 text-indigo-400" />
          AI Management Team
        </h2>
        <div className="flex flex-wrap gap-3">
          {game.ai_team.map((member) => (
            <div key={member.id} className="flex items-center gap-2 bg-[#fafafa] border border-[#e5e5e5] rounded-lg px-3 py-2">
              <div className="w-6 h-6 rounded-full bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
                <span className="text-white text-xs font-bold">{member.name.charAt(0)}</span>
              </div>
              <span className="text-sm text-gray-900">{member.name}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Events */}
      <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <Activity className="w-4 h-4 text-blue-400" />
          Recent Events
        </h2>
        {game.recent_events.length === 0 ? (
          <p className="text-sm text-gray-500">暂无事件</p>
        ) : (
          <div className="space-y-2">
            {game.recent_events.slice(0, 10).map((event) => (
              <div key={event.id} className="flex items-start gap-3 py-2 border-b border-[#e5e5e5] last:border-0">
                <div className={`w-2 h-2 rounded-full mt-1.5 ${
                  event.event_type === "success" ? "bg-green-500" :
                  event.event_type === "error" ? "bg-red-500" :
                  event.event_type === "warning" ? "bg-yellow-500" : "bg-blue-500"
                }`} />
                <div className="flex-1">
                  <p className="text-sm text-gray-900">{event.message}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-gray-500">{event.agent_name}</span>
                    <span className="text-xs text-gray-500">·</span>
                    <span className="text-xs text-gray-500">{formatTime(event.timestamp)}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Tasks */}
      <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6">
        <h2 className="text-sm font-semibold text-gray-900 mb-4 flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-green-400" />
          Related Tasks
        </h2>
        {game.tasks.length === 0 ? (
          <p className="text-sm text-gray-500">暂无关联任务</p>
        ) : (
          <div className="space-y-2">
            {game.tasks.slice(0, 10).map((task) => (
              <div key={task.id} className="flex items-center justify-between py-2 border-b border-[#e5e5e5] last:border-0">
                <div className="flex items-center gap-3">
                  <div className={`w-2 h-2 rounded-full ${
                    task.status === "completed" ? "bg-green-500" :
                    task.status === "running" ? "bg-blue-500" :
                    task.status === "waiting_approval" ? "bg-yellow-500" : "bg-gray-400"
                  }`} />
                  <div>
                    <p className="text-sm text-gray-900">{task.title}</p>
                    <p className="text-xs text-gray-500">{task.agent_name}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-500">{task.status}</span>
                  <span className="text-xs text-gray-500">·</span>
                  <span className="text-xs text-gray-500 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {formatTime(task.created_at)}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
