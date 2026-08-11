"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { api, type Event } from "@/lib/api";
import { useSoundNotification } from "@/lib/use-sound-notification";
import { useDesktopNotification } from "@/lib/use-desktop-notification";
import { EventDetailPanel } from "@/components/event-detail-panel";
import { Wifi, WifiOff, Volume2, VolumeX, Bell, Monitor, MonitorOff } from "lucide-react";

const eventTypeConfig: Record<string, { color: string; dot: string }> = {
  success: { color: "text-green-600", dot: "bg-green-500" },
  warning: { color: "text-yellow-600", dot: "bg-yellow-500" },
  info: { color: "text-blue-600", dot: "bg-blue-500" },
  error: { color: "text-red-600", dot: "bg-red-500" },
  decision: { color: "text-purple-600", dot: "bg-purple-500" },
};

const sourceBadge: Record<string, { label: string; className: string }> = {
  collaboration: { label: "协同", className: "bg-purple-50 text-purple-600" },
  ceo_memory: { label: "记忆", className: "bg-indigo-50 text-indigo-600" },
  workspace: { label: "", className: "" },
};

interface LiveEventStreamProps {
  /** 最大显示条数 (默认 8) */
  maxItems?: number;
  /** 是否显示连接状态徽章 (默认 true) */
  showStatus?: boolean;
  /** 是否显示事件源标签 (默认 true) */
  showSource?: boolean;
  /** 是否显示声音开关 (默认 true) */
  showSoundToggle?: boolean;
  /** 是否显示桌面通知开关 (默认 true) */
  showDesktopToggle?: boolean;
}

/**
 * 实时事件流组件 — SSE 订阅多事件源 + 声音/桌面通知.
 *
 * 事件源:
 *   - workspace: 基础事件流
 *   - collaboration: 跨 Agent 协同记录
 *   - ceo_memory: CEO 执行记忆
 *
 * 声音通知:
 *   - 按事件类型区分音色 (success/warning/error/decision/info)
 *   - 默认关闭, 用户点击喇叭按钮开启
 *   - 使用 Web Audio API, 无需音频文件
 *
 * 桌面通知:
 *   - 使用浏览器 Notification API, 即使最小化也能弹出
 *   - 默认关闭, 首次点击触发权限请求
 *   - 点击通知聚焦窗口
 *
 * 用法:
 *   <LiveEventStream maxItems={8} />
 *   <LiveEventStream showStatus={false} maxItems={5} />
 */
export default function LiveEventStream({
  maxItems = 8,
  showStatus = true,
  showSource = true,
  showSoundToggle = true,
  showDesktopToggle = true,
}: LiveEventStreamProps) {
  const [events, setEvents] = useState<Event[]>([]);
  const [connected, setConnected] = useState(false);
  const [soundOn, setSoundOn] = useState(false);
  const [desktopOn, setDesktopOn] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const esRef = useRef<EventSource | null>(null);

  const { play } = useSoundNotification({ enabled: soundOn });
  const { notify, requestPermission, permission, isSupported } = useDesktopNotification({ enabled: desktopOn });

  // 初始加载历史事件
  useEffect(() => {
    api.getEvents(maxItems).then(setEvents).catch(() => {});
  }, [maxItems]);

  // SSE 实时订阅
  useEffect(() => {
    const es = api.subscribeEvents();
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);
    es.onmessage = (e) => {
      try {
        const newEvent: Event = JSON.parse(e.data);
        let isNew = false;
        setEvents((prev) => {
          if (prev.some((ev) => ev.id === newEvent.id)) return prev;
          isNew = true;
          return [newEvent, ...prev].slice(0, maxItems);
        });
        // 只对新事件播放声音 + 桌面通知 + 计数
        if (isNew) {
          setUnreadCount((c) => c + 1);
          play(newEvent.event_type);
          notify({
            eventType: newEvent.event_type,
            title: newEvent.agent_name || "AI Studio",
            body: newEvent.message,
            clickUrl: "/activity",
          });
        }
      } catch {
        // 忽略解析错误
      }
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [maxItems, play, notify]);

  const handleToggleSound = useCallback(() => {
    setSoundOn((prev) => !prev);
    // 开启时重置未读计数
    setUnreadCount(0);
  }, []);

  const handleToggleDesktop = useCallback(async () => {
    // 首次开启时请求权限
    if (!desktopOn && permission !== "granted") {
      const result = await requestPermission();
      if (result === "granted") {
        setDesktopOn(true);
        setUnreadCount(0);
      }
      // 权限被拒绝或用户关闭对话框时, 不开启
      return;
    }
    setDesktopOn((prev) => !prev);
    setUnreadCount(0);
  }, [desktopOn, permission, requestPermission]);

  const handleClearUnread = useCallback(() => {
    setUnreadCount(0);
  }, []);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-gray-900">实时活动</h2>
          {unreadCount > 0 && soundOn && (
            <span
              onClick={handleClearUnread}
              className="flex items-center gap-1 px-1.5 py-0.5 rounded-full text-[10px] bg-red-50 text-red-600 cursor-pointer hover:bg-red-100 transition-colors"
              title={`${unreadCount} 条未读事件, 点击清除`}
            >
              <Bell className="w-2.5 h-2.5" />
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {/* 声音开关 */}
          {showSoundToggle && (
            <button
              onClick={handleToggleSound}
              className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] transition-colors ${
                soundOn
                  ? "bg-indigo-50 text-indigo-600 hover:bg-indigo-100"
                  : "bg-gray-50 text-gray-400 hover:bg-gray-100"
              }`}
              title={soundOn ? "声音通知已开启 (点击关闭)" : "声音通知已关闭 (点击开启)"}
            >
              {soundOn ? <Volume2 className="w-2.5 h-2.5" /> : <VolumeX className="w-2.5 h-2.5" />}
              {soundOn ? "声音" : "静音"}
            </button>
          )}
          {/* 桌面通知开关 (即使最小化也能弹出) */}
          {showDesktopToggle && isSupported && (
            <button
              onClick={handleToggleDesktop}
              className={`flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] transition-colors ${
                desktopOn
                  ? "bg-indigo-50 text-indigo-600 hover:bg-indigo-100"
                  : "bg-gray-50 text-gray-400 hover:bg-gray-100"
              }`}
              title={
                desktopOn
                  ? "桌面通知已开启 (点击关闭)"
                  : permission === "denied"
                    ? "桌面通知权限已被拒绝, 请在浏览器设置中恢复"
                    : "桌面通知已关闭 (点击开启, 首次需授权)"
              }
            >
              {desktopOn ? <Monitor className="w-2.5 h-2.5" /> : <MonitorOff className="w-2.5 h-2.5" />}
              {desktopOn ? "桌面" : "桌面"}
            </button>
          )}
          {/* 连接状态 */}
          {showStatus && (
            <>
              {connected ? (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] bg-green-50 text-green-600">
                  <Wifi className="w-2.5 h-2.5" />
                  <span className="relative flex h-1 w-1">
                    <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                    <span className="relative inline-flex rounded-full h-1 w-1 bg-green-500" />
                  </span>
                  Live
                </span>
              ) : (
                <span className="flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] bg-gray-50 text-gray-400">
                  <WifiOff className="w-2.5 h-2.5" />
                  Offline
                </span>
              )}
            </>
          )}
        </div>
      </div>

      {/* Event list */}
      <div className="space-y-2.5">
        {events.length === 0 && (
          <div className="text-xs text-gray-400 text-center py-6">
            等待事件...
          </div>
        )}
        {events.map((event) => {
          const config = eventTypeConfig[event.event_type] || eventTypeConfig.info;
          const src = event.source ? sourceBadge[event.source] : null;
          return (
            <div
              key={event.id}
              onClick={() => setSelectedEvent(event)}
              className="flex items-start gap-2.5 cursor-pointer hover:bg-gray-50 -mx-1 px-1 py-0.5 rounded transition-colors"
            >
              <div className={`w-2 h-2 rounded-full mt-1.5 flex-shrink-0 ${config.dot}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5">
                  <span className="text-sm text-gray-900 truncate">{event.message}</span>
                  {showSource && src && src.label && (
                    <span className={`px-1.5 py-0.5 rounded text-[9px] flex-shrink-0 ${src.className}`}>
                      {src.label}
                    </span>
                  )}
                </div>
                <div className="text-xs text-gray-500 mt-0.5">
                  {event.agent_name}
                  {event.game_name && <span> · {event.game_name}</span>}
                  <span> · {new Date(event.timestamp).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}</span>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* 事件详情面板 (点击事件项弹出) */}
      <EventDetailPanel event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
