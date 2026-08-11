"use client";

import { useEffect, useState } from "react";
import { api, type Task } from "@/lib/api";
import { ListTodo, CheckCircle2, Circle, Clock, AlertCircle } from "lucide-react";

const statusConfig: Record<string, { color: string; icon: React.ComponentType<{ className?: string }> }> = {
  pending: { color: "text-gray-400 bg-gray-400/10", icon: Clock },
  running: { color: "text-blue-400 bg-blue-500/10", icon: Circle },
  waiting_approval: { color: "text-yellow-400 bg-yellow-500/10", icon: AlertCircle },
  completed: { color: "text-green-400 bg-green-500/10", icon: CheckCircle2 },
  failed: { color: "text-red-400 bg-red-500/10", icon: AlertCircle },
};

const priorityColors: Record<string, string> = {
  low: "text-gray-500",
  medium: "text-blue-400",
  high: "text-orange-400",
  critical: "text-red-400",
};

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    api.getTasks().then(setTasks).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-gray-500">Loading tasks...</div>
      </div>
    );
  }

  const filtered = filter === "all" ? tasks : tasks.filter((t) => t.status === filter);

  const counts = {
    all: tasks.length,
    pending: tasks.filter((t) => t.status === "pending").length,
    running: tasks.filter((t) => t.status === "running").length,
    waiting_approval: tasks.filter((t) => t.status === "waiting_approval").length,
    completed: tasks.filter((t) => t.status === "completed").length,
  };

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-6">
        <div className="flex items-center gap-2 mb-1">
          <ListTodo className="w-5 h-5 text-indigo-400" />
          <h1 className="text-2xl font-bold text-gray-900">Task Center</h1>
        </div>
        <p className="text-sm text-gray-500">所有 AI 员工工作任务</p>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2 mb-6">
        {Object.entries(counts).map(([key, count]) => (
          <button
            key={key}
            onClick={() => setFilter(key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filter === key
                ? "bg-indigo-500/10 text-indigo-400"
                : "text-gray-500 hover:text-gray-900 hover:bg-black/5"
            }`}
          >
            {key === "all" ? "全部" : key.replace("_", " ")} ({count})
          </button>
        ))}
      </div>

      {/* Task List */}
      <div className="space-y-3">
        {filtered.map((task) => {
          const config = statusConfig[task.status] || statusConfig.pending;
          const StatusIcon = config.icon;
          return (
            <div key={task.id} className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-5">
              <div className="flex items-start justify-between mb-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-sm font-medium text-gray-900">{task.title}</h3>
                    <span className={`text-xs ${priorityColors[task.priority] || priorityColors.medium}`}>
                      {task.priority}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-gray-500">
                    <span>{task.agent_name}</span>
                    <span>·</span>
                    <span>{task.game_name}</span>
                  </div>
                </div>
                <div className={`flex items-center gap-1.5 px-2 py-1 rounded text-xs ${config.color}`}>
                  <StatusIcon className="w-3 h-3" />
                  {task.status.replace("_", " ")}
                </div>
              </div>

              {/* Progress bar */}
              {task.status !== "pending" && (
                <div className="mb-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-gray-500">Progress</span>
                    <span className="text-xs text-gray-400">{task.progress}%</span>
                  </div>
                  <div className="w-full h-1.5 bg-[#e5e5e5] rounded-full overflow-hidden">
                    <div className="h-full bg-indigo-500 rounded-full transition-all" style={{ width: `${task.progress}%` }} />
                  </div>
                </div>
              )}

              {/* Steps */}
              {task.steps.length > 0 && (
                <div className="flex items-center gap-3 flex-wrap">
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
              )}
            </div>
          );
        })}
      </div>

      {filtered.length === 0 && (
        <div className="text-center text-gray-500 py-12">
          暂无任务
        </div>
      )}
    </div>
  );
}
