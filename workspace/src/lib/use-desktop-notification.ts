"use client";

import { useCallback, useEffect, useRef, useState } from "react";

/**
 * 事件类型 → 桌面通知渲染参数映射.
 *
 * 不同事件类型使用不同标题前缀和图标符号, 便于视觉区分.
 * 图标使用 emoji (跨平台兼容, 无需静态资源).
 */
const notificationProfiles: Record<string, { prefix: string; icon: string; tag: string }> = {
  // 成功: 绿色对勾
  success: { prefix: "✅", icon: "✅", tag: "success" },
  // 告警/警告: 黄色三角
  warning: { prefix: "⚠️", icon: "⚠️", tag: "warning" },
  // 错误: 红色圆圈
  error: { prefix: "❌", icon: "❌", tag: "error" },
  // 决策: 紫色决策球
  decision: { prefix: "🔮", icon: "🔮", tag: "decision" },
  // 信息: 蓝色信息圈
  info: { prefix: "ℹ️", icon: "ℹ️", tag: "info" },
};

/** Notification 权限状态 (扩展标准 PermissionState) */
type NotificationPermissionState = "default" | "granted" | "denied" | "unsupported";

interface UseDesktopNotificationOptions {
  /** 是否启用桌面通知 (默认 false, 需用户手动开启) */
  enabled: boolean;
  /** 通知显示时长 (毫秒, 默认 5000; 部分浏览器忽略此值) */
  autoCloseMs?: number;
}

interface NotifyParams {
  /** 事件类型 (success/warning/error/decision/info) */
  eventType: string;
  /** 通知标题 (通常为 Agent 名称或事件摘要) */
  title: string;
  /** 通知正文 (事件消息) */
  body: string;
  /** 可选: 点击通知后跳转的 URL (如 /activity) */
  clickUrl?: string;
}

/**
 * 桌面通知 Hook — 使用浏览器 Notification API.
 *
 * 特性:
 *   - 即使浏览器最小化或失焦也能弹出系统级通知
 *   - 按事件类型区分图标和标题前缀
 *   - 权限管理: 自动检测、按需请求
 *   - 点击通知聚焦窗口并可选跳转 URL
 *   - tag 去重: 同类型通知覆盖旧的, 避免堆积
 *
 * 与 useSoundNotification 协同:
 *   - 声音通知: 即时听觉提示 (需页面可见时才有意义)
 *   - 桌面通知: 系统级视觉提示 (即使最小化也能触达)
 *   - 两者可同时启用, 互补不冲突
 *
 * 浏览器兼容:
 *   - Chrome/Edge/Firefox: 完全支持
 *   - Safari 16.4+: 支持
 *   - 需 HTTPS 或 localhost 才能申请权限
 *   - 首次需用户交互 (点击开启按钮) 才能请求权限
 *
 * 用法:
 *   const { notify, requestPermission, permission } = useDesktopNotification({ enabled: desktopOn });
 *
 *   // 请求权限 (绑定到按钮点击)
 *   <button onClick={requestPermission}>启用桌面通知</button>
 *
 *   // 在收到新事件时调用
 *   notify({ eventType: "success", title: "GrowthLoop", body: "预算调整完成" });
 */
export function useDesktopNotification({ enabled, autoCloseMs = 5000 }: UseDesktopNotificationOptions) {
  const [permission, setPermission] = useState<NotificationPermissionState>("default");
  // clickUrl 处理器 (避免闭包陈旧)
  const clickHandlerRef = useRef<(() => void) | null>(null);

  // 初始化: 检测浏览器支持和当前权限
  useEffect(() => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      setPermission("unsupported");
      return;
    }
    setPermission(Notification.permission as NotificationPermissionState);
  }, []);

  /**
   * 请求通知权限 (必须在用户交互内调用, 如按钮点击).
   *
   * @returns 最终权限状态
   */
  const requestPermission = useCallback(async (): Promise<NotificationPermissionState> => {
    if (typeof window === "undefined" || !("Notification" in window)) {
      return "unsupported";
    }
    try {
      const result = await Notification.requestPermission();
      setPermission(result as NotificationPermissionState);
      return result as NotificationPermissionState;
    } catch {
      return "denied";
    }
  }, []);

  /**
   * 显示桌面通知.
   *
   * @param params - 通知参数
   */
  const notify = useCallback(
    (params: NotifyParams): boolean => {
      if (!enabled) return false;
      if (typeof window === "undefined" || !("Notification" in window)) return false;
      if (Notification.permission !== "granted") return false;

      const profile = notificationProfiles[params.eventType] || notificationProfiles.info;
      const title = `${profile.prefix} ${params.title}`;

      try {
        const notification = new Notification(title, {
          body: params.body,
          icon: profile.icon,
          tag: profile.tag, // 同 tag 通知覆盖旧的
          // silent: true, // 不播放系统提示音 (我们有自己的声音通知)
          // requireInteraction: false, // 自动关闭
        });

        // 点击通知: 聚焦窗口 + 可选跳转
        notification.onclick = () => {
          window.focus();
          if (params.clickUrl) {
            window.location.href = params.clickUrl;
          }
          notification.close();
        };

        // 自动关闭 (部分浏览器忽略, 但 Chrome 桌面端遵守)
        if (autoCloseMs > 0) {
          setTimeout(() => {
            try {
              notification.close();
            } catch {
              // 已自动关闭
            }
          }, autoCloseMs);
        }

        return true;
      } catch {
        // 通知创建失败 (如 Service Worker 冲突)
        return false;
      }
    },
    [enabled, autoCloseMs],
  );

  // 清理挂载时的 clickHandler (防内存泄漏)
  useEffect(() => {
    return () => {
      clickHandlerRef.current = null;
    };
  }, []);

  return {
    /** 显示桌面通知 (返回是否成功创建) */
    notify,
    /** 请求通知权限 (绑定到按钮 onClick) */
    requestPermission,
    /** 当前权限状态 */
    permission,
    /** 是否已就绪 (权限已授予) */
    isReady: permission === "granted",
    /** 浏览器是否支持 Notification API */
    isSupported: permission !== "unsupported",
  };
}
