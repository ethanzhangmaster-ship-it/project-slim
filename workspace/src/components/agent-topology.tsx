"use client";

import { useState, useMemo } from "react";
import type { TopologyNode, TopologyEdge, TopologyDepartment } from "@/lib/api";
import { AgentDetailPanel } from "@/components/event-detail-panel";

const edgeTypeColors: Record<string, { stroke: string; label: string }> = {
  trigger: { stroke: "#8b5cf6", label: "决策触发" },
  data_flow: { stroke: "#0ea5e9", label: "数据传递" },
  collaboration: { stroke: "#d946ef", label: "协同" },
  alert: { stroke: "#f59e0b", label: "告警" },
  feedback: { stroke: "#10b981", label: "回流" },
  broadcast: { stroke: "#3b82f6", label: "广播" },
};

interface AgentTopologyProps {
  nodes: TopologyNode[];
  edges: TopologyEdge[];
  departments: TopologyDepartment[];
}

/**
 * 交互式 Agent 拓扑可视化组件.
 *
 * 按部门分组布局, SVG 渲染节点和连线, 支持悬停高亮.
 *
 * 布局策略:
 *   - 4 个部门从上到下排列 (管理 → 研发 → 增长 → 运营)
 *   - 每个部门内 Agent 水平排列
 *   - 边用贝塞尔曲线连接, 按类型着色
 */
export default function AgentTopology({ nodes, edges, departments }: AgentTopologyProps) {
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);
  const [hoveredEdge, setHoveredEdge] = useState<number | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<{
    id: string;
    name: string;
    department?: string;
    color: string;
  } | null>(null);

  // 计算节点位置 (按部门分组, 水平排列)
  const nodePositions = useMemo(() => {
    const positions: Record<string, { x: number; y: number }> = {};
    const deptY: Record<string, number> = {};
    const deptSpacing = 140;
    departments.forEach((dept, idx) => {
      deptY[dept.id] = 60 + idx * deptSpacing;
    });

    departments.forEach((dept) => {
      const deptNodes = nodes.filter((n) => dept.agents.includes(n.id));
      const nodeSpacing = 160;
      const totalWidth = (deptNodes.length - 1) * nodeSpacing;
      const startX = 400 - totalWidth / 2; // 居中
      deptNodes.forEach((node, idx) => {
        positions[node.id] = { x: startX + idx * nodeSpacing, y: deptY[dept.id] };
      });
    });

    return positions;
  }, [nodes, departments]);

  const nodeMap = useMemo(() => {
    const map: Record<string, TopologyNode> = {};
    nodes.forEach((n) => { map[n.id] = n; });
    return map;
  }, [nodes]);

  // 检查节点是否在悬停链路上
  const isNodeActive = (nodeId: string): boolean => {
    if (!hoveredNode) return false;
    if (hoveredNode === nodeId) return true;
    return edges.some(
      (e) =>
        (e.from === hoveredNode && e.to === nodeId) ||
        (e.to === hoveredNode && e.from === nodeId)
    );
  };

  const isEdgeActive = (idx: number): boolean => {
    if (hoveredEdge === idx) return true;
    if (!hoveredNode) return false;
    const edge = edges[idx];
    return edge.from === hoveredNode || edge.to === hoveredNode;
  };

  return (
    <div className="w-full">
      {/* 图例 */}
      <div className="flex items-center gap-3 mb-3 flex-wrap">
        {Object.entries(edgeTypeColors).map(([type, config]) => (
          <div key={type} className="flex items-center gap-1.5">
            <div
              className="w-4 h-0.5 rounded-full"
              style={{ backgroundColor: config.stroke }}
            />
            <span className="text-[10px] text-gray-500">{config.label}</span>
          </div>
        ))}
      </div>

      {/* SVG 拓扑图 */}
      <div className="overflow-x-auto">
        <svg
          width="800"
          height={60 + departments.length * 140 + 40}
          className="min-w-full"
          style={{ maxWidth: "800px", margin: "0 auto", display: "block" }}
        >
          {/* 部门背景区域 */}
          {departments.map((dept) => {
            const deptNodes = nodes.filter((n) => dept.agents.includes(n.id));
            if (deptNodes.length === 0) return null;
            const minY = 60 + departments.indexOf(dept) * 140 - 35;
            return (
              <g key={dept.id}>
                <rect
                  x="20"
                  y={minY}
                  width="760"
                  height="80"
                  rx="12"
                  fill={dept.color}
                  opacity="0.04"
                  stroke={dept.color}
                  strokeOpacity="0.15"
                  strokeWidth="1"
                />
                <text x="30" y={minY + 16} className="text-[10px] font-medium" fill={dept.color}>
                  {dept.id}
                </text>
              </g>
            );
          })}

          {/* 边 (连线) */}
          {edges.map((edge, idx) => {
            const from = nodePositions[edge.from];
            const to = nodePositions[edge.to];
            if (!from || !to) return null;

            const config = edgeTypeColors[edge.type] || { stroke: "#9ca3af", label: edge.type };
            const active = isEdgeActive(idx);

            // 贝塞尔曲线控制点 (垂直方向偏移)
            const midY = (from.y + to.y) / 2;
            const isSameRow = Math.abs(from.y - to.y) < 20;
            const ctrlY = isSameRow ? from.y - 40 : midY;
            const ctrlX = (from.x + to.x) / 2;

            const path = `M ${from.x} ${from.y} Q ${ctrlX} ${ctrlY} ${to.x} ${to.y}`;

            // 标签位置 (路径中点)
            const labelX = ctrlX;
            const labelY = isSameRow ? ctrlY - 8 : midY - 2;

            return (
              <g
                key={idx}
                onMouseEnter={() => setHoveredEdge(idx)}
                onMouseLeave={() => setHoveredEdge(null)}
                style={{ cursor: "pointer" }}
              >
                {/* 透明粗线用于悬停命中 */}
                <path d={path} fill="none" stroke="transparent" strokeWidth="16" />
                {/* 可见线 */}
                <path
                  d={path}
                  fill="none"
                  stroke={config.stroke}
                  strokeWidth={active ? 2.5 : 1.5}
                  strokeOpacity={active ? 1 : 0.4}
                  markerEnd="url(#arrowhead)"
                  style={{ transition: "stroke-opacity 0.2s, stroke-width 0.2s" }}
                />
                {/* 边标签 */}
                {active && (
                  <g>
                    <rect
                      x={labelX - edge.label.length * 3.5 - 4}
                      y={labelY - 9}
                      width={edge.label.length * 7 + 8}
                      height="18"
                      rx="4"
                      fill="white"
                      stroke={config.stroke}
                      strokeOpacity="0.3"
                    />
                    <text
                      x={labelX}
                      y={labelY + 4}
                      textAnchor="middle"
                      className="text-[9px]"
                      fill={config.stroke}
                    >
                      {edge.label}
                    </text>
                  </g>
                )}
              </g>
            );
          })}

          {/* 箭头标记定义 */}
          <defs>
            <marker
              id="arrowhead"
              viewBox="0 0 10 10"
              refX="8"
              refY="5"
              markerWidth="6"
              markerHeight="6"
              orient="auto"
            >
              <path d="M 0 0 L 10 5 L 0 10 z" fill="#9ca3af" />
            </marker>
          </defs>

          {/* 节点 */}
          {nodes.map((node) => {
            const pos = nodePositions[node.id];
            if (!pos) return null;
            const active = isNodeActive(node.id);
            const dimmed = hoveredNode !== null && !active;

            return (
              <g
                key={node.id}
                onMouseEnter={() => setHoveredNode(node.id)}
                onMouseLeave={() => setHoveredNode(null)}
                onClick={() => setSelectedAgent({
                  id: node.id,
                  name: node.name,
                  department: node.department,
                  color: node.color,
                })}
                style={{ cursor: "pointer" }}
                opacity={dimmed ? 0.3 : 1}
              >
                {/* 节点圆形 */}
                <circle
                  cx={pos.x}
                  cy={pos.y}
                  r={active ? 26 : 22}
                  fill="white"
                  stroke={node.color}
                  strokeWidth={active ? 3 : 2}
                  style={{ transition: "r 0.2s, stroke-width 0.2s" }}
                />
                {/* 节点首字母 */}
                <text
                  x={pos.x}
                  y={pos.y + 5}
                  textAnchor="middle"
                  className="text-xs font-bold"
                  fill={node.color}
                >
                  {node.name.charAt(0)}
                </text>
                {/* 节点名称 */}
                <text
                  x={pos.x}
                  y={pos.y + 42}
                  textAnchor="middle"
                  className="text-[10px] font-medium"
                  fill="#374151"
                >
                  {node.name}
                </text>
                {/* 角色 */}
                <text
                  x={pos.x}
                  y={pos.y + 54}
                  textAnchor="middle"
                  className="text-[8px]"
                  fill="#9ca3af"
                >
                  {node.role}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      {/* 悬停时显示节点详情 */}
      {hoveredNode && nodeMap[hoveredNode] && (
        <div className="mt-3 bg-gray-50 border border-gray-200 rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: nodeMap[hoveredNode].color }}
            />
            <span className="text-sm font-medium text-gray-900">{nodeMap[hoveredNode].name}</span>
            <span className="text-[10px] text-gray-500">
              {nodeMap[hoveredNode].department} · {nodeMap[hoveredNode].role}
            </span>
          </div>
          {/* 关联边 */}
          <div className="flex flex-wrap gap-1.5 mt-2">
            {edges
              .filter((e) => e.from === hoveredNode || e.to === hoveredNode)
              .map((e, idx) => {
                const config = edgeTypeColors[e.type] || { stroke: "#9ca3af", label: e.type };
                const isOut = e.from === hoveredNode;
                const target = isOut ? e.to : e.from;
                const targetNode = nodeMap[target];
                return (
                  <span
                    key={idx}
                    className="px-2 py-0.5 rounded text-[10px] border"
                    style={{
                      borderColor: config.stroke + "40",
                      color: config.stroke,
                      backgroundColor: config.stroke + "08",
                    }}
                  >
                    {isOut ? "→" : "←"} {targetNode?.name || target} ({e.label})
                  </span>
                );
              })}
          </div>
        </div>
      )}

      {/* 拓扑统计 */}
      <div className="mt-3 flex items-center gap-4 text-[10px] text-gray-500">
        <span>{nodes.length} 个 Agent</span>
        <span>{edges.length} 条协同链路</span>
        <span>{departments.length} 个部门</span>
        <span className="text-indigo-500">· 点击节点查看协同记录</span>
      </div>

      {/* Agent 协同记录面板 (点击节点弹出) */}
      <AgentDetailPanel
        agentId={selectedAgent?.id || null}
        agentName={selectedAgent?.name}
        agentDepartment={selectedAgent?.department}
        agentColor={selectedAgent?.color}
        onClose={() => setSelectedAgent(null)}
      />
    </div>
  );
}
