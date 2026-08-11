"use client";

import { useRef, useCallback, useEffect } from "react";

/**
 * 事件声音类型 → 音频参数映射.
 *
 * 使用 Web Audio API 生成简短提示音, 无需音频文件.
 * 不同事件类型使用不同频率和波形, 便于听觉区分.
 */
const soundProfiles: Record<string, { freq: number; duration: number; type: OscillatorType; volume: number }> = {
  // 成功: 高频清脆音 (880Hz, 短)
  success: { freq: 880, duration: 0.15, type: "sine", volume: 0.15 },
  // 告警/警告: 中频双音 (523Hz, 中)
  warning: { freq: 523, duration: 0.25, type: "triangle", volume: 0.18 },
  // 错误: 低频沉音 (330Hz, 长)
  error: { freq: 330, duration: 0.35, type: "sawtooth", volume: 0.2 },
  // 决策: 上升音 (660Hz → 880Hz)
  decision: { freq: 660, duration: 0.2, type: "sine", volume: 0.15 },
  // 信息: 柔和音 (440Hz, 短)
  info: { freq: 440, duration: 0.1, type: "sine", volume: 0.1 },
};

interface UseSoundOptions {
  /** 是否启用声音 (默认 false, 需用户手动开启) */
  enabled: boolean;
  /** 音量倍率 (0-1, 默认 1) */
  volumeScale?: number;
}

/**
 * 事件声音通知 Hook — 使用 Web Audio API 生成提示音.
 *
 * 特性:
 *   - 无需音频文件, 纯代码生成
 *   - 按事件类型区分音色 (success/warning/error/decision/info)
 *   - AudioContext 懒加载, 首次播放时创建
 *   - 浏览器自动策略: 需用户交互后才能播放 (点击开启按钮即满足)
 *
 * 用法:
 *   const { play } = useSoundNotification({ enabled: soundOn });
 *   // 在收到新事件时调用
 *   play("success");
 *
 * @param options.enabled - 是否启用声音
 * @param options.volumeScale - 音量倍率 (0-1)
 */
export function useSoundNotification({ enabled, volumeScale = 1 }: UseSoundOptions) {
  const audioCtxRef = useRef<AudioContext | null>(null);

  // 懒加载 AudioContext (需用户交互后才能创建)
  const getAudioContext = useCallback((): AudioContext | null => {
    if (typeof window === "undefined") return null;
    if (audioCtxRef.current) return audioCtxRef.current;

    try {
      const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
      if (!AudioContextClass) return null;
      audioCtxRef.current = new AudioContextClass();
      return audioCtxRef.current;
    } catch {
      return null;
    }
  }, []);

  /**
   * 播放指定类型的提示音.
   *
   * @param eventType - 事件类型 (success/warning/error/decision/info)
   */
  const play = useCallback((eventType: string) => {
    if (!enabled) return;

    const ctx = getAudioContext();
    if (!ctx) return;

    // 浏览器可能 suspended (自动策略), 尝试 resume
    if (ctx.state === "suspended") {
      ctx.resume().catch(() => {});
    }

    const profile = soundProfiles[eventType] || soundProfiles.info;
    const { freq, duration, type, volume } = profile;
    const finalVolume = Math.min(1, volume * volumeScale);

    try {
      const oscillator = ctx.createOscillator();
      const gainNode = ctx.createGain();

      oscillator.type = type;
      oscillator.frequency.setValueAtTime(freq, ctx.currentTime);

      // 包络: 快速上升 + 指数衰减 (避免爆音)
      gainNode.gain.setValueAtTime(0, ctx.currentTime);
      gainNode.gain.linearRampToValueAtTime(finalVolume, ctx.currentTime + 0.01);
      gainNode.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);

      oscillator.connect(gainNode);
      gainNode.connect(ctx.destination);

      oscillator.start(ctx.currentTime);
      oscillator.stop(ctx.currentTime + duration);

      // decision 类型: 播放上升双音
      if (eventType === "decision") {
        const osc2 = ctx.createOscillator();
        const gain2 = ctx.createGain();
        osc2.type = "sine";
        osc2.frequency.setValueAtTime(freq * 1.33, ctx.currentTime + duration * 0.5);
        gain2.gain.setValueAtTime(0, ctx.currentTime + duration * 0.5);
        gain2.gain.linearRampToValueAtTime(finalVolume * 0.8, ctx.currentTime + duration * 0.5 + 0.01);
        gain2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + duration);
        osc2.connect(gain2);
        gain2.connect(ctx.destination);
        osc2.start(ctx.currentTime + duration * 0.5);
        osc2.stop(ctx.currentTime + duration);
      }
    } catch {
      // 忽略播放错误 (如 AudioContext 不可用)
    }
  }, [enabled, volumeScale, getAudioContext]);

  // 组件卸载时清理 AudioContext
  useEffect(() => {
    return () => {
      if (audioCtxRef.current) {
        audioCtxRef.current.close().catch(() => {});
        audioCtxRef.current = null;
      }
    };
  }, []);

  return { play };
}
