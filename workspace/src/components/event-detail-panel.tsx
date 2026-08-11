"use client";

import { useEffect, useState, useCallback } from "react";
import { api, type Event } from "@/lib/api";
import { X, Clock, User, Gamepad2, Tag, Database, Activity } from "lucide-react";

/** 事件类型 → 颜色和标签映射 (与 live-event-stream 保持一致) */
const eventTypeConfig: Record<string, { color: string; bg: string; dot: string; label: string }> = {
  success: { color: "text-green-600", bg: "bg-green-50", dot: "bg-green-500", label: "Success" },
  warning: { color: "text-yellow-600", bg: "bg-yellow-50", dot: "bg-yellow-500", label: "Warning" },
  info: { color: "text-blue-600", bg: "bg-blue-50", dot: "bg-blue-500", label: "Info" },
  error: { color: "text-red-600", bg: "bg-red-50", dot: "bg-red-500", label: "Error" },
  decision: { color: "text-purple-600", bg: "bg-purple-50", dot: "bg-purple-500", label: "Decision" },
};

/** 事件源 → 标签映射 */
const sourceConfig: Record<string, { label: string; badge: string }> = {
  workspace: { label: "基础事件", badge: "bg-blue-50 text-blue-600" },
  collaboration: { label: "协同事件", badge: "bg-purple-50 text-purple-600" },
  ceo_memory: { label: "CEO 记忆", badge: "bg-indigo-50 text-indigo-600" },
};

/** 格式化时间戳为本地可读时间 */
function formatTime(iso: string): string {
  if (!iso) return "-";
  try {
    return new Date(iso).toLocaleString("zh-CN", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  } catch {
    return iso;
  }
}

/** 安全地格式化 JSON 数据 (带缩进) */
function formatJsonData(data: unknown): string {
  if (data === null || data === undefined) return "";
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

/** 判断值是否为"有意义"的非空值 (用于过滤显示字段) */
function hasValue(value: unknown): boolean {
  if (value === null || value === undefined) return false;
  if (typeof value === "string") return value.trim() !== "";
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === "object") return Object.keys(value as object).length > 0;
  return true;
}

interface EventDetailPanelProps {
  /** 要展示的事件; 传 null 关闭面板 */
  event: Event | null;
  /** 关闭回调 */
  onClose: () => void;
}

/**
 * 事件详情面板 — 点击事件项弹出完整协同记录.
 *
 * 特性:
 *   - Modal 覆盖层, 点击背景或 ESC 关闭
 *   - 展示事件全部字段 (id/timestamp/agent/game/type/source/message)
 *   - 格式化展示原始 data 字段 (JSON 缩进)
 *   - 事件类型颜色编码
 *   - 响应式布局 (移动端全屏, 桌面端居中 max-w-2xl)
 *   - 滚动锁定 (打开时禁止背景滚动)
 *
 * 用法:
 *   const [selected, setSelected] = useState<Event | null>(null);
 *   <EventDetailPanel event={selected} onClose={() => setSelected(null)} />
 *   <div onClick={() => setSelected(event)}>...</div>
 */
export function EventDetailPanel({ event, onClose }: EventDetailPanelProps) {
  // ESC 键关闭 + 滚动锁定
  useEffect(() => {
    if (!event) return;
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleEsc);
    // 锁定背景滚动
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleEsc);
      document.body.style.overflow = prevOverflow;
    };
  }, [event, onClose]);

  if (!event) return null;

  const config = eventTypeConfig[event.event_type] || eventTypeConfig.info;
  const src = event.source ? sourceConfig[event.source] : null;
  const jsonData = formatJsonData(event.data);
  const hasJsonData = hasValue(event.data);

  return (
    <>
      {/* 背景遮罩 (点击关闭) */}
      <div
        className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4"
        onClick={onClose}
      >
        {/* 面板容器 (阻止冒泡) */}
        <div
          className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-start justify-between p-5 border-b border-gray-100">
            <div className="flex items-start gap-3 flex-1 min-w-0">
              {/* 事件类型圆点 */}
              <div className={`w-2.5 h-2.5 rounded-full mt-1.5 flex-shrink-0 ${config.dot}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className="text-base font-semibold text-gray-900 truncate">
                    {event.message}
                  </span>
                </div>
                <div className="flex items-center gap-2 flex-wrap">
                  <span className={`px-2 py-0.5 rounded text-xs ${config.color} ${config.bg}`}>
                    {config.label}
                  </span>
                  {src && (
                    <span className={`px-2 py-0.5 rounded text-[10px] ${src.badge}`}>
                      {src.label}
                    </span>
                  )}
                </div>
              </div>
            </div>
            <button
              onClick={onClose}
              className="ml-2 p-1 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors flex-shrink-0"
              aria-label="关闭"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body (可滚动) */}
          <div className="flex-1 overflow-y-auto p-5 space-y-4">
            {/* 基本字段网格 */}
            <div className="grid grid-cols-2 gap-3">
              <FieldItem icon={<Clock className="w-3.5 h-3.5" />} label="时间" value={formatTime(event.timestamp)} />
              <FieldItem icon={<User className="w-3.5 h-3.5" />} label="Agent" value={event.agent_name || "-"} />
              <FieldItem icon={<Tag className="w-3.5 h-3.5" />} label="Agent ID" value={event.agent_id || "-"} mono />
              <FieldItem icon={<Gamepad2 className="w-3.5 h-3.5" />} label="游戏" value={event.game_name || "-"} />
            </div>

            {/* Event ID (单独一行, 等宽字体) */}
            <FieldItem icon={<Activity className="w-3.5 h-3.5" />} label="事件 ID" value={event.id} mono />

            {/* 原始数据 (JSON) */}
            {hasJsonData && (
              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <Database className="w-3.5 h-3.5 text-gray-500" />
                  <span className="text-xs font-medium text-gray-700">原始数据 (Raw Data)</span>
                </div>
                <pre className="bg-gray-50 border border-gray-200 rounded-lg p-3 text-xs text-gray-800 overflow-x-auto max-h-72 font-mono leading-relaxed">
                  {jsonData}
                </pre>
              </div>
            )}

            {/* 无原始数据时的提示 */}
            {!hasJsonData && (
              <div className="text-xs text-gray-400 text-center py-4 bg-gray-50 rounded-lg">
                此事件无附加原始数据
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-5 py-3 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between">
            <span className="text-[10px] text-gray-400">
              按 ESC 关闭 · 点击背景关闭
            </span>
            <button
              onClick={onClose}
              className="px-3 py-1 rounded-lg text-xs bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
            >
              关闭
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

/** 单个字段展示项 */
function FieldItem({
  icon,
  label,
  value,
  mono = false,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex items-center gap-1 text-gray-500">
        {icon}
        <span className="text-[10px] uppercase tracking-wide">{label}</span>
      </div>
      <span className={`text-sm text-gray-900 ${mono ? "font-mono break-all" : ""}`}>
        {value}
      </span>
    </div>
  );
}


// ── Agent 协同记录面板 (从拓扑节点点击) ────────────────────────


interface AgentDetailPanelProps {
  /** 要展示的 Agent ID; 传 null 关闭 */
  agentId: string | null;
  /** Agent 名称 (从拓扑节点传入, 避免重复查询) */
  agentName?: string;
  /** Agent 部门 */
  agentDepartment?: string;
  /** Agent 颜色 (拓扑节点颜色) */
  agentColor?: string;
  /** 关闭回调 */
  onClose: () => void;
}

/**
 * Agent 协同记录面板 — 点击拓扑节点弹出该 Agent 最近事件.
 *
 * 特性:
 *   - 显示 Agent 基本信息 (名称/部门/角色)
 *   - 加载该 Agent 最近 20 条事件 (前端过滤)
 *   - 点击单条事件可展开详情 (复用 EventDetailPanel)
 *   - ESC 键关闭 + 滚动锁定
 *
 * 用法:
 *   const [agentId, setAgentId] = useState<string | null>(null);
 *   <AgentDetailPanel agentId={agentId} agentName="..." onClose={() => setAgentId(null)} />
 */
export function AgentDetailPanel({
  agentId,
  agentName,
  agentDepartment,
  agentColor,
  onClose,
}: AgentDetailPanelProps) {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);

  // 加载该 Agent 的事件 (前端过滤, 复用 /api/events)
  useEffect(() => {
    if (!agentId) return;
    setLoading(true);
    setError(null);
    api.getEvents(100)
      .then((all) => {
        // 按 agent_id 或 agent_name 过滤 (兼容两种匹配方式)
        const filtered = all.filter(
          (e) => e.agent_id === agentId || e.agent_name === agentName,
        );
        setEvents(filtered.slice(0, 20));
      })
      .catch((err) => setError(err.message || "加载失败"))
      .finally(() => setLoading(false));
  }, [agentId, agentName]);

  // ESC 键关闭 + 滚动锁定
  useEffect(() => {
    if (!agentId) return;
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        if (selectedEvent) {
          setSelectedEvent(null);
        } else {
          onClose();
        }
      }
    };
    document.addEventListener("keydown", handleEsc);
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handleEsc);
      document.body.style.overflow = prevOverflow;
    };
  }, [agentId, selectedEvent, onClose]);

  if (!agentId) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4"
        onClick={onClose}
      >
        <div
          className="bg-white rounded-xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-start justify-between p-5 border-b border-gray-100">
            <div className="flex items-center gap-3">
              {/* Agent 颜色圆点 */}
              <div
                className="w-3 h-3 rounded-full flex-shrink-0"
                style={{ backgroundColor: agentColor || "#6b7280" }}
              />
              <div>
                <h3 className="text-base font-semibold text-gray-900">
                  {agentName || agentId}
                </h3>
                <p className="text-xs text-gray-500">
                  {agentDepartment ? `${agentDepartment} · ` : ""}最近协同记录
                </p>
              </div>
            </div>
            <button
              onClick={onClose}
              className="ml-2 p-1 rounded-lg text-gray-400 hover:text-gray-700 hover:bg-gray-100 transition-colors flex-shrink-0"
              aria-label="关闭"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Body (事件列表, 可滚动) */}
          <div className="flex-1 overflow-y-auto p-4">
            {loading && (
              <div className="text-center py-12 text-sm text-gray-500">
                加载中...
              </div>
            )}
            {error && (
              <div className="text-center py-12 text-sm text-red-500">
                {error}
              </div>
            )}
            {!loading && !error && events.length === 0 && (
              <div className="text-center py-12 text-sm text-gray-400">
                该 Agent 暂无协同记录
              </div>
            )}
            {!loading && !error && events.length > 0 && (
              <div className="space-y-2">
                {events.map((evt) => {
                  const config = eventTypeConfig[evt.event_type] || eventTypeConfig.info;
                  const src = evt.source ? sourceConfig[evt.source] : null;
                  return (
                    <button
                      key={evt.id}
                      onClick={() => setSelectedEvent(evt)}
                      className="w-full text-left flex items-start gap-2.5 p-2.5 rounded-lg hover:bg-gray-50 transition-colors border border-transparent hover:border-gray-200"
                    >
                      <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${config.dot}`} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5 mb-0.5">
                          <span className="text-sm text-gray-900 truncate">{evt.message}</span>
                          {src && (
                            <span className={`px-1.5 py-0.5 rounded text-[9px] flex-shrink-0 ${src.badge}`}>
                              {src.label}
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-gray-500">
                          {formatTime(evt.timestamp)}
                          {evt.game_name && <span> · {evt.game_name}</span>}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="px-5 py-3 border-t border-gray-100 bg-gray-50/50 flex items-center justify-between">
            <span className="text-[10px] text-gray-400">
              {events.length > 0 ? `${events.length} 条记录 · ` : ""}按 ESC 关闭
            </span>
            <button
              onClick={onClose}
              className="px-3 py-1 rounded-lg text-xs bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors"
            >
              关闭
            </button>
          </div>
        </div>
      </div>

      {/* 嵌套: 点击单条事件弹出详情 */}
      <EventDetailPanel
        event={selectedEvent}
        onClose={() => setSelectedEvent(null)}
      />
    </>
  );
}
