"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type Game } from "@/lib/api";
import { Gamepad2, TrendingUp, TrendingDown, Minus } from "lucide-react";

const statusColors: Record<string, string> = {
  growing: "text-green-400 bg-green-500/10",
  stable: "text-blue-400 bg-blue-500/10",
  declining: "text-red-400 bg-red-500/10",
  launching: "text-purple-400 bg-purple-500/10",
};

const trendIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  up: TrendingUp,
  flat: Minus,
  down: TrendingDown,
};

const trendColors: Record<string, string> = {
  up: "text-green-400",
  flat: "text-gray-400",
  down: "text-red-400",
};

function formatNumber(n: number): string {
  if (n >= 1000) return (n / 1000).toFixed(1) + "K";
  return n.toString();
}

function formatCurrency(n: number): string {
  if (n >= 1000) return "$" + (n / 1000).toFixed(1) + "K";
  return "$" + n.toFixed(0);
}

export default function GamesPage() {
  const [games, setGames] = useState<Game[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getGames().then(setGames).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-gray-500">Loading games...</div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-6xl">
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-1">
          <Gamepad2 className="w-5 h-5 text-indigo-400" />
          <h1 className="text-2xl font-bold text-gray-900">Game Portfolio</h1>
        </div>
        <p className="text-sm text-gray-500">管理所有游戏</p>
      </div>

      {/* Game Cards Grid */}
      <div className="grid grid-cols-3 gap-4">
        {games.map((game) => {
          const TrendIcon = trendIcons[game.trend] || trendIcons.flat;
          return (
            <Link
              key={game.id}
              href={`/games/${game.id}`}
              className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-5 hover:border-indigo-400 transition-colors"
            >
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-indigo-500/20 to-purple-500/20 flex items-center justify-center">
                    <Gamepad2 className="w-5 h-5 text-indigo-400" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-gray-900">{game.name}</h3>
                    <p className="text-xs text-gray-500">{game.genre} · {game.market}</p>
                  </div>
                </div>
                <TrendIcon className={`w-4 h-4 ${trendColors[game.trend]}`} />
              </div>

              {/* Health Score */}
              <div className="mb-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-500">Health Score</span>
                  <span className="text-xs font-medium text-gray-900">{game.health_score}</span>
                </div>
                <div className="w-full h-1.5 bg-[#e5e5e5] rounded-full overflow-hidden">
                  <div
                    className={`h-full rounded-full ${
                      game.health_score >= 80 ? "bg-green-500" :
                      game.health_score >= 60 ? "bg-yellow-500" : "bg-red-500"
                    }`}
                    style={{ width: `${game.health_score}%` }}
                  />
                </div>
              </div>

              {/* Metrics */}
              <div className="grid grid-cols-2 gap-3 mb-3">
                <div>
                  <div className="text-xs text-gray-500">DAU</div>
                  <div className="text-sm font-medium text-gray-900">{formatNumber(game.dau)}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Revenue</div>
                  <div className="text-sm font-medium text-green-400">{formatCurrency(game.revenue)}/d</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">ROAS</div>
                  <div className="text-sm font-medium text-gray-900">{game.roas.toFixed(1)}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">LTV</div>
                  <div className="text-sm font-medium text-gray-900">${game.ltv.toFixed(2)}</div>
                </div>
              </div>

              {/* Status */}
              <div className="flex items-center justify-between pt-3 border-t border-[#e5e5e5]">
                <span className={`px-2 py-0.5 rounded text-xs font-medium ${statusColors[game.status] || statusColors.stable}`}>
                  {game.status}
                </span>
                <span className="text-xs text-gray-500">AI: {game.ai_manager}</span>
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}
