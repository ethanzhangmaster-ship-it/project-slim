"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { api, type Event } from "@/lib/api";
import { useSoundNotification } from "@/lib/use-sound-notification";
import { useDesktopNotification } from "@/lib/use-desktop-notification";
import { EventDetailPanel } from "@/components/event-detail-panel";
import { Activity as ActivityIcon, Wifi, WifiOff, RefreshCw, Volume2, VolumeX, Bell, Monitor, MonitorOff } from "lucide-react";

const eventTypeConfig: Record<string, { color: string; dot: string; label: string }> = {
  success: { color: "text-green-600", dot: "bg-green-500", label: "Success" },
  warning: { color: "text-yellow-600", dot: "bg-yellow-500", label: "Warning" },
  info: { color: "text-blue-600", dot: "bg-blue-500", label: "Info" },
  error: { color: "text-red-600", dot: "bg-red-500", label: "Error" },
  decision: { color: "text-purple-600", dot: "bg-purple-500", label: "Decision" },
};

const sourceConfig: Record<string, { label: string; badge: string }> = {
  workspace: { label: "基础事件", badge: "bg-blue-50 text-blue-600" },
  collaboration: { label: "协同事件", badge: "bg-purple-50 text-purple-600" },
  ceo_memory: { label: "CEO 记忆", badge: "bg-indigo-50 text-indigo-600" },
};

export default function ActivityPage() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [liveConnected, setLiveConnected] = useState(false);
  const [liveEvent, setLiveEvent] = useState<Event | null>(null);
  const [filter, setFilter] = useState<string>("all");
  const [soundOn, setSoundOn] = useState(false);
  const [desktopOn, setDesktopOn] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [selectedEvent, setSelectedEvent] = useState<Event | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const { play } = useSoundNotification({ enabled: soundOn });
  const { notify, requestPermission, permission, isSupported } = useDesktopNotification({ enabled: desktopOn });

  // 初始加载历史事件
  useEffect(() => {
    api.getEvents(50).then(setEvents).finally(() => setLoading(false));
  }, []);

  // SSE 实时订阅 — 支持多事件源 + 声音/桌面通知
  useEffect(() => {
    const es = api.subscribeEvents();
    eventSourceRef.current = es;

    es.onopen = () => setLiveConnected(true);
    es.onerror = () => {
      setLiveConnected(false);
      // 浏览器会自动重连, 不需要手动 close
    };
    es.onmessage = (e) => {
      try {
        const newEvent: Event = JSON.parse(e.data);
        setLiveEvent(newEvent);
        // 将新事件插入到列表顶部 (去重)
        let isNew = false;
        setEvents((prev) => {
          if (prev.some((ev) => ev.id === newEvent.id)) return prev;
          isNew = true;
          return [newEvent, ...prev].slice(0, 100); // 最多保留 100 条
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
      eventSourceRef.current = null;
    };
  }, [play, notify]);

  const handleManualRefresh = useCallback(() => {
    api.getEvents(50).then(setEvents);
  }, []);

  const handleToggleSound = useCallback(() => {
    setSoundOn((prev) => !prev);
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
      return;
    }
    setDesktopOn((prev) => !prev);
    setUnreadCount(0);
  }, [desktopOn, permission, requestPermission]);

  const handleClearUnread = useCallback(() => {
    setUnreadCount(0);
  }, []);

  // 按事件源过滤
  const filteredEvents = filter === "all"
    ? events
    : events.filter((e) => (e.source || "workspace") === filter);

  // 统计各事件源数量
  const sourceCounts = {
    all: events.length,
    workspace: events.filter((e) => (e.source || "workspace") === "workspace").length,
    collaboration: events.filter((e) => e.source === "collaboration").length,
    ceo_memory: events.filter((e) => e.source === "ceo_memory").length,
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-gray-500">Loading activity stream...</div>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <ActivityIcon className="w-5 h-5 text-indigo-500" />
            <h1 className="text-2xl font-bold text-gray-900">Activity Stream</h1>
          </div>
          <p className="text-sm text-gray-500">AI 员工实时动态 · 跨 Agent 协同事件流</p>
        </div>
        {/* 实时连接状态 + 声音/桌面通知开关 */}
        <div className="flex items-center gap-3">
          {/* 未读计数徽章 */}
          {unreadCount > 0 && (soundOn || desktopOn) && (
            <span
              onClick={handleClearUnread}
              className="flex items-center gap-1 px-2 py-1 rounded-full text-xs bg-red-50 text-red-600 cursor-pointer hover:bg-red-100 transition-colors"
              title={`${unreadCount} 条未读事件, 点击清除`}
            >
              <Bell className="w-3 h-3" />
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
          {/* 声音开关 */}
          <button
            onClick={handleToggleSound}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs transition-colors ${
              soundOn
                ? "bg-indigo-50 text-indigo-600 hover:bg-indigo-100"
                : "bg-gray-50 text-gray-400 hover:bg-gray-100"
            }`}
            title={soundOn ? "声音通知已开启 (点击关闭)" : "声音通知已关闭 (点击开启)"}
          >
            {soundOn ? <Volume2 className="w-3 h-3" /> : <VolumeX className="w-3 h-3" />}
            {soundOn ? "声音" : "静音"}
          </button>
          {/* 桌面通知开关 (即使最小化也能弹出) */}
          {isSupported && (
            <button
              onClick={handleToggleDesktop}
              className={`flex items-center gap-1 px-2.5 py-1 rounded-full text-xs transition-colors ${
                desktopOn
                  ? "bg-indigo-50 text-indigo-600 hover:bg-indigo-100"
                  : "bg-gray-50 text-gray-400 hover:bg-gray-100"
              }`}
              title={
                desktopOn
                  ? "桌面通知已开启 (点击关闭)"
                  : permission === "denied"
                    ? "桌面通知权限已被拒绝, 请在浏览器设置中恢复"
                    : "桌面通知已关闭 (点击开启, 首次需授权, 最小化也能弹出)"
              }
            >
              {desktopOn ? <Monitor className="w-3 h-3" /> : <MonitorOff className="w-3 h-3" />}
              桌面
            </button>
          )}
          {liveConnected ? (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs bg-green-50 text-green-600">
              <Wifi className="w-3 h-3" />
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-green-500" />
              </span>
              Live
            </span>
          ) : (
            <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs bg-gray-50 text-gray-500">
              <WifiOff className="w-3 h-3" />
              Offline
            </span>
          )}
          <button
            onClick={handleManualRefresh}
            className="flex items-center gap-1 text-xs text-gray-500 hover:text-gray-900 transition-colors"
          >
            <RefreshCw className="w-3 h-3" />
            刷新
          </button>
        </div>
      </div>

      {/* 事件源过滤 */}
      <div className="mb-4 flex items-center gap-2 flex-wrap">
        {[
          { key: "all", label: "全部", count: sourceCounts.all, badge: "bg-gray-100 text-gray-600" },
          { key: "workspace", label: "基础事件", count: sourceCounts.workspace, badge: "bg-blue-50 text-blue-600" },
          { key: "collaboration", label: "协同事件", count: sourceCounts.collaboration, badge: "bg-purple-50 text-purple-600" },
          { key: "ceo_memory", label: "CEO 记忆", count: sourceCounts.ceo_memory, badge: "bg-indigo-50 text-indigo-600" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              filter === tab.key
                ? "bg-indigo-500 text-white"
                : "bg-white text-gray-600 border border-gray-200 hover:bg-gray-50"
            }`}
          >
            {tab.label}
            <span className={`px-1.5 py-0.5 rounded text-[10px] ${
              filter === tab.key ? "bg-white/20" : tab.badge
            }`}>
              {tab.count}
            </span>
          </button>
        ))}
      </div>

      {/* 新事件提示 (SSE 推送时闪烁) */}
      {liveEvent && (
        <div className="mb-4 bg-indigo-50 border border-indigo-200 rounded-lg p-3 flex items-center gap-2 animate-pulse">
          <span className="text-xs font-medium text-indigo-600">新事件:</span>
          <span className="text-xs text-gray-700 truncate flex-1">{liveEvent.message}</span>
          {liveEvent.source && (
            <span className={`px-2 py-0.5 rounded text-[10px] ${(sourceConfig[liveEvent.source] || sourceConfig.workspace).badge}`}>
              {(sourceConfig[liveEvent.source] || sourceConfig.workspace).label}
            </span>
          )}
        </div>
      )}

      {/* Timeline */}
      <div className="relative">
        {/* Vertical line */}
        <div className="absolute left-4 top-0 bottom-0 w-px bg-[#e5e5e5]" />

        <div className="space-y-4">
          {filteredEvents.map((event) => {
            const config = eventTypeConfig[event.event_type] || eventTypeConfig.info;
            const src = sourceConfig[event.source || "workspace"] || sourceConfig.workspace;
            return (
              <div key={event.id} className="relative pl-12">
                {/* Dot */}
                <div className={`absolute left-3 top-3 w-3 h-3 rounded-full ${config.dot} ring-4 ring-[#fafafa]`} />

                {/* Content — 点击打开详情面板 */}
                <div
                  onClick={() => setSelectedEvent(event)}
                  className="bg-[#ffffff] border border-[#e5e5e5] rounded-lg p-4 cursor-pointer hover:border-indigo-300 hover:shadow-md transition-all"
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="text-sm font-medium text-gray-900">{event.agent_name}</span>
                      <span className={`px-2 py-0.5 rounded text-xs ${config.color} bg-gray-50`}>
                        {config.label}
                      </span>
                      {event.source && event.source !== "workspace" && (
                        <span className={`px-2 py-0.5 rounded text-[10px] ${src.badge}`}>
                          {src.label}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-500 whitespace-nowrap">
                      {new Date(event.timestamp).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                  <p className="text-sm text-gray-700">{event.message}</p>
                  {event.game_name && (
                    <div className="mt-2 text-xs text-gray-500">
                      🎮 {event.game_name}
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {filteredEvents.length === 0 && (
        <div className="text-center text-gray-500 py-12">
          {filter === "all" ? "暂无活动记录" : "该事件源暂无记录"}
        </div>
      )}

      {/* 事件详情面板 (点击事件项弹出) */}
      <EventDetailPanel event={selectedEvent} onClose={() => setSelectedEvent(null)} />
    </div>
  );
}
