const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://127.0.0.1:8080";

export interface KPI {
  games: number;
  total_dau: number;
  total_revenue: number;
  total_spend: number;
  avg_roas: number;
  avg_ltv: number;
  ai_tasks: number;
  automation_rate: number;
}

export interface Briefing {
  date: string;
  greeting: string;
  highlights: Array<{
    type: string;
    title: string;
    detail: string;
    suggestion: string;
  }>;
  alerts: Array<{
    type: string;
    title: string;
    detail: string;
  }>;
}

export interface Game {
  id: string;
  name: string;
  genre: string;
  status: string;
  health_score: number;
  dau: number;
  revenue: number;
  spend: number;
  roas: number;
  ltv: number;
  retention_d1: number;
  retention_d7: number;
  retention_d30: number;
  ai_manager: string;
  market: string;
  trend: string;
}

export interface Agent {
  id: string;
  name: string;
  department: string;
  status: string;
  confidence: number;
  capabilities: string[];
  last_active: string;
  current_task_ids: string[];
  recent_decision_ids: string[];
  avatar_color: string;
}

export interface Task {
  id: string;
  title: string;
  agent_id: string;
  agent_name: string;
  game_id: string;
  game_name: string;
  status: string;
  priority: string;
  progress: number;
  steps: Array<{ name: string; done: boolean }>;
  created_at: string;
}

export interface Event {
  id: string;
  timestamp: string;
  agent_id: string;
  agent_name: string;
  event_type: string;
  message: string;
  game_id: string;
  game_name: string;
  /** 事件源 (workspace | collaboration | ceo_memory) — SSE 多事件源标识 */
  source?: string;
  /** 原始记录数据 — SSE 多事件源附加字段 */
  data?: Record<string, unknown>;
}

export interface Decision {
  id: string;
  agent_id: string;
  agent_name: string;
  game_id: string;
  game_name: string;
  action: string;
  reason: string;
  confidence: number;
  impact: string;
  status: string;
  created_at: string;
}

export interface Dashboard {
  kpi: KPI;
  briefing: Briefing;
  games: Game[];
  recent_events: Event[];
  active_tasks: Task[];
}

export interface OrganizationNode {
  id: string;
  name: string;
  type: string;
  children: OrganizationNode[];
  agent_id: string;
  status: string;
}

export interface ExecutionMemory {
  execution_id: string;
  action_id: string;
  decision_id: string;
  game_id: string;
  strategy_type: string;
  domain: string;
  action_type: string;
  status: string;
  success: boolean;
  real_api_called: boolean;
  rolled_back: boolean;
  detail: string;
  created_at: string;
}

export interface ExecutionExperience {
  record_id: string;
  action: string;
  context: Record<string, unknown>;
  result: Record<string, unknown>;
  reward: number;
  success: boolean;
  provider: string;
  execution_id: string;
  verdict: string;
  timestamp: string;
  metadata: Record<string, unknown>;
}

export interface OperatorMemory {
  date: string;
  decisions: number;
  executed: number;
  approved: number;
  blocked: number;
  observed: number;
  revenue_impact: number;
  top_game: string;
  company_status: string;
  real_api_called: boolean;
}

export interface MemoryData {
  execution_memory: ExecutionMemory[];
  execution_experience: ExecutionExperience[];
  operator_memory: OperatorMemory[];
  summary: {
    total_executions: number;
    successful_executions: number;
    success_rate: number;
    total_experiences: number;
    positive_rewards: number;
    positive_rate: number;
    operator_logs: number;
  };
}

async function fetchAPI<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function postAPI<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  return res.json();
}

export interface ApprovalResponse {
  decision_id: string;
  status: "approved" | "rejected";
  approver: string;
  message: string;
}

export interface LoopTriggerResponse {
  status: string;
  cycle_number: number;
  dry_run: boolean;
  fetch_meta_ads: boolean;
  duration_seconds: number;
  actions_planned: number;
  actions_executed: number;
  actions_succeeded?: number;
  success_rate?: number;
  evaluated_count: number;
  pending_created: number;
  message: string;
  meta_ads_data?: {
    creatives_fetched: number;
    signals_generated: number;
    predictions_generated?: number;
    fetch_error?: string;
  };
  reality_scores?: Array<{
    game_id: string;
    composite: number;
    decision_level: string;
    coverage: number;
    freshness: number;
    consistency: number;
  }>;
  diagnosis_summary?: {
    root_cause: string;
    confidence: number;
    creative_id: string;
    evidence: string[];
  };
  strategy_summary?: {
    strategy_type: string;
    intensity: number;
    target_creative_id: string;
    time_horizon_days: number;
  };
  action_details?: Array<{
    action_id: string;
    action_type: string;
    creative_id: string;
    adset_id: string;
    risk_level: string;
    approval_level: number;
    confidence: number;
    budget_impact: number;
    status: string;
    reason: string;
  }>;
}

export interface LoopCycleSummary {
  cycle_number: number;
  loop_id: string;
  started_at: string;
  completed_at: string;
  duration_ms: number;
  signal_count: number;
  actions_planned: number;
  actions_executed: number;
  actions_skipped: number;
  actions_rolled_back: number;
  success_count: number;
  success_rate: number;
  action_types: Record<string, number>;
  dry_run: boolean;
}

export interface CEODailyRunStageResult {
  stage: string;
  status: string;  // ok / skipped / failed
  detail: string;
  payload?: Record<string, unknown>;
}

export interface CEODailyRunResponse {
  status: string;           // completed / partial / skipped / failed
  run_id: string;
  date: string;
  stages: CEODailyRunStageResult[];
  decisions: Record<string, number>;
  executions: Record<string, number>;
  errors: string[];
  report_id: string;
  real_api_called: boolean;
  summary: Record<string, unknown>;
  duration_seconds: number;
}

export interface ChurnAnalysis {
  game_id: string;
  analysis_date: string;
  total_players: number;
  at_risk_count: number;
  lapsed_count: number;
  churning_count: number;
  avg_churn_risk: number;
  segments: Record<string, number>;
  lifecycle_stages: Record<string, number>;
  high_value_at_risk: number;
}

export interface CampaignAction {
  action_type: string;
  target_count: number;
  content: string;
  trigger_delay_hours: number;
}

export interface WinbackCampaign {
  campaign_id: string;
  game_id: string;
  campaign_type: string;
  target_segment: string;
  target_count: number;
  rewards_pool: number;
  duration_days: number;
  expected_participation: number;
  expected_retention_uplift: number;
  actions: CampaignAction[];
  created_at: string;
}

export interface CampaignEvaluation {
  campaign_id: string;
  participation_rate: number;
  retention_uplift: number;
  revenue_uplift: number;
  player_satisfaction: number;
  campaign?: WinbackCampaign;
}

export interface CampaignExecutionAction {
  action_id: string;
  campaign_id: string;
  game_id: string;
  action_type: string;
  target_count: number;
  content: string;
  trigger_delay_hours: number;
  rewards_amount: number;
  risk_level: string;
  approval_level: number;
  status: string;
  error_message: string;
  executed_at: string;
  platform_response: Record<string, unknown>;
}

export interface CampaignExecutionResult {
  execution_id: string;
  campaign_id: string;
  game_id: string;
  campaign_type: string;
  target_segment: string;
  target_count: number;
  rewards_pool: number;
  dry_run: boolean;
  approval_level: number;
  status: string;
  blocked_reason: string;
  actions: CampaignExecutionAction[];
  approved_by: string;
  approved_at: string;
  created_at: string;
  completed_at: string;
}

export interface LiveOpsExecutionSummary {
  execution_id: string;
  campaign_id: string;
  game_id: string;
  campaign_type: string;
  target_segment: string;
  target_count: number;
  rewards_pool: number;
  dry_run: boolean;
  approval_level: number;
  status: string;
  blocked_reason: string;
  action_count: number;
  action_summary: Record<string, number>;
  approved_by: string;
  created_at: string;
  completed_at: string;
}

export interface LiveOpsOverview {
  total_executions: number;
  status_breakdown: Record<string, number>;
  completed: number;
  blocked: number;
  dry_run: number;
  failed: number;
  rejected: number;
  success_rate: number;
  total_rewards_distributed: number;
  total_push_delivered: number;
  total_reward_grant_delivered: number;
  total_email_delivered: number;
  total_in_app_delivered: number;
  by_game: Record<string, {
    executions: number;
    completed: number;
    blocked: number;
    rewards_distributed: number;
    target_count: number;
  }>;
  recent_executions: LiveOpsExecutionSummary[];
}

export interface TopologyNode {
  id: string;
  name: string;
  role: string;
  color: string;
  department?: string;
}

export interface TopologyEdge {
  from: string;
  to: string;
  label: string;
  type: string;
}

export interface TopologyDepartment {
  id: string;
  color: string;
  agents: string[];
}

export interface LiveOpsMemoryEvent {
  execution_id: string;
  action_id: string;
  decision_id: string;
  game_id: string;
  strategy_type: string;
  domain: string;
  action_type: string;
  status: string;
  success: boolean;
  real_api_called: boolean;
  rolled_back: boolean;
  detail: string;
  created_at: string;
}

export interface CEOLiveOpsStage {
  stage: string;
  status: string;
  detail: string;
  payload?: Record<string, unknown>;
  run_id: string;
  business_date: string;
}

export interface CrossAgentOverview {
  topology: {
    nodes: TopologyNode[];
    edges: TopologyEdge[];
    departments: TopologyDepartment[];
  };
  recent_events: LiveOpsMemoryEvent[];
  ceo_liveops_stage: CEOLiveOpsStage | null;
  collaboration_stats: {
    total_liveops_events: number;
    ceo_liveops_triggered: boolean;
    broadcast_types: string[];
    feedback_channels: string[];
    collaboration_links?: Array<{ name: string; endpoint: string; active: boolean }>;
    topology_summary?: { total_agents: number; total_edges: number; total_departments: number };
  };
}

// ── LiveOps → Growth 双向协同: ChurnAlertBridge ──────────────

export interface GrowthResponseAction {
  action_type: string;  // pause_campaign | reallocate_budget | reduce_budget | monitor
  target?: string;
  from_target?: string;
  to_target?: string;
  ratio?: number;
  reason: string;
  priority: string;  // high | medium | low
  expected_effect: string;
  execution_result?: {
    success: boolean;
    status: string;  // simulated | executed
    message: string;
    executed_at: string;
    dry_run: boolean;
  };
  rollback_result?: {
    success: boolean;
    status: string;  // rolled_back
    message: string;
    rolled_back_at: string;
  };
}

export interface ChurnResponse {
  response_id: string;
  alert_campaign_id: string;
  alert_timestamp: string;
  game_id: string;
  high_value_at_risk: number;
  target_segment: string;
  rewards_pool: number;
  severity: string;  // high | medium | low
  actions: GrowthResponseAction[];
  action_count: number;
  created_at: string;
  status: string;  // executed | partial_executed | rolled_back | suggested
  source: string;
  executed_at?: string;
  dry_run?: boolean;
  rolled_back_at?: string;
}

export interface ChurnResponseStats {
  total_responses: number;
  severity_distribution: { high: number; medium: number; low: number };
  status_distribution: Record<string, number>;
  action_type_distribution: Record<string, number>;
  by_game: Record<string, number>;
  recent_responses: ChurnResponse[];
}

// ── 系统监控 ──────────────────────────────────────────────────

export interface MonitorAlert {
  alert_id: string;
  severity: "critical" | "warning" | "info";
  category: string;
  message: string;
  current_value: number;
  threshold: number;
  suggestion: string;
}

export interface FileStats {
  exists: boolean;
  path: string;
  size_mb: number;
  record_count: number;
  last_modified: string;
  hours_since_update: number;
}

export interface MonitorOverview {
  health: {
    status: "healthy" | "degraded" | "critical";
    timestamp: string;
    alerts_count: number;
    critical_alerts: number;
    warning_alerts: number;
  };
  alerts: MonitorAlert[];
  growth_loop: {
    total_cycles: number;
    total_actions_planned: number;
    total_actions_executed: number;
    total_actions_rolled_back: number;
    success_rate: number;
    latest_cycle: {
      cycle_number: number;
      completed_at: string;
      actions_planned: number;
      actions_executed: number;
      duration_ms: number;
    };
  };
  liveops: {
    total_executions: number;
    completed: number;
    blocked: number;
    dry_run: number;
    failed: number;
    success_rate: number;
  };
  churn_alert: {
    total_responses: number;
    executed: number;
    rolled_back: number;
    suggested: number;
    partial_executed: number;
  };
  approval_queue: {
    ceo_pending: number;
    liveops_pending: number;
    total_pending: number;
    oldest_ceo_pending_hours: number;
  };
  data_files: Record<string, FileStats>;
  timestamp: string;
}

export const api = {
  getDashboard: () => fetchAPI<Dashboard>("/api/dashboard"),
  getKPI: () => fetchAPI<KPI>("/api/kpi"),
  getBriefing: () => fetchAPI<Briefing>("/api/briefing"),
  getOrganization: () => fetchAPI<OrganizationNode>("/api/organization"),
  getAgents: () => fetchAPI<Agent[]>("/api/agents"),
  getAgent: (id: string) => fetchAPI<Agent & { tasks: Task[]; decisions: Decision[] }>(`/api/agents/${id}`),
  getTasks: () => fetchAPI<Task[]>("/api/tasks"),
  getEvents: (limit = 50) => fetchAPI<Event[]>(`/api/events?limit=${limit}`),
  getDecisions: () => fetchAPI<Decision[]>("/api/decisions"),
  getGames: () => fetchAPI<Game[]>("/api/games"),
  getGame: (id: string) => fetchAPI<Game & { recent_events: Event[]; tasks: Task[]; ai_team: Array<{ id: string; name: string }> }>(`/api/games/${id}`),
  getMemory: (limit = 50) => fetchAPI<MemoryData>(`/api/memory?limit=${limit}`),
  // 执行层
  approveDecision: (id: string, approver = "workspace_admin") =>
    postAPI<ApprovalResponse>(`/api/decisions/${id}/approve`, { approver }),
  rejectDecision: (id: string, approver = "workspace_admin", reason = "") =>
    postAPI<ApprovalResponse>(`/api/decisions/${id}/reject`, { approver, reason }),
  triggerLoop: (dryRun = true, fetchMetaAds = false) =>
    postAPI<LoopTriggerResponse>("/api/loop/trigger", { dry_run: dryRun, fetch_meta_ads: fetchMetaAds }),
  getLoopHistory: (limit = 10) =>
    fetchAPI<LoopCycleSummary[]>(`/api/loop/history?limit=${limit}`),
  getLoopCycle: (cycleNumber: number) =>
    fetchAPI<Record<string, unknown>>(`/api/loop/cycle/${cycleNumber}`),
  triggerCEODailyRun: (businessDate = "", force = false, useRealData = false) =>
    postAPI<CEODailyRunResponse>("/api/ceo/daily-run", {
      business_date: businessDate,
      force,
      use_real_data: useRealData,
    }),
  // LiveOps Agent
  getChurnAnalysis: (gameId: string) =>
    fetchAPI<ChurnAnalysis>(`/api/liveops/churn-analysis/${gameId}`),
  designWinbackCampaign: (gameId: string, analysis?: Partial<ChurnAnalysis>) =>
    postAPI<WinbackCampaign>("/api/liveops/winback-campaign", {
      game_id: gameId,
      analysis: analysis || null,
    }),
  listLiveopsCampaigns: (gameId?: string) =>
    fetchAPI<WinbackCampaign[]>(`/api/liveops/campaigns${gameId ? `?game_id=${gameId}` : ""}`),
  getLiveopsCampaign: (campaignId: string) =>
    fetchAPI<WinbackCampaign>(`/api/liveops/campaigns/${campaignId}`),
  evaluateLiveopsCampaign: (campaignId: string) =>
    postAPI<CampaignEvaluation>(`/api/liveops/campaigns/${campaignId}/evaluate`),
  executeLiveopsCampaign: (campaignId: string, dryRun = true) =>
    postAPI<CampaignExecutionResult>(`/api/liveops/campaigns/${campaignId}/execute`, { dry_run: dryRun }),
  listLiveopsExecutions: (campaignId?: string) =>
    fetchAPI<CampaignExecutionResult[]>(`/api/liveops/executions${campaignId ? `?campaign_id=${campaignId}` : ""}`),
  getLiveopsExecution: (executionId: string) =>
    fetchAPI<CampaignExecutionResult>(`/api/liveops/executions/${executionId}`),
  listLiveopsPendingApprovals: () =>
    fetchAPI<CampaignExecutionResult[]>(`/api/liveops/pending-approvals`),
  approveLiveopsExecution: (executionId: string, approver = "workspace_admin") =>
    postAPI<CampaignExecutionResult>(`/api/liveops/executions/${executionId}/approve`, { approver }),
  rejectLiveopsExecution: (executionId: string, approver = "workspace_admin", reason = "") =>
    postAPI<CampaignExecutionResult>(`/api/liveops/executions/${executionId}/reject`, { approver, reason }),
  getLiveopsStats: (recentLimit = 10) =>
    fetchAPI<LiveOpsOverview>(`/api/liveops/stats?recent_limit=${recentLimit}`),
  getCrossAgentOverview: () =>
    fetchAPI<CrossAgentOverview>("/api/liveops/cross-agent"),
  // LiveOps → Growth 双向协同
  listChurnResponses: (gameId?: string, limit = 50) =>
    fetchAPI<ChurnResponse[]>(`/api/growth/churn-responses?${gameId ? `game_id=${gameId}&` : ""}limit=${limit}`),
  getChurnResponseStats: () =>
    fetchAPI<ChurnResponseStats>("/api/growth/churn-responses/stats"),
  getChurnResponse: (responseId: string) =>
    fetchAPI<ChurnResponse>(`/api/growth/churn-responses/${responseId}`),
  rollbackChurnResponse: (responseId: string) =>
    postAPI<{ response_id: string; status: string; message: string }>(
      `/api/growth/churn-responses/${responseId}/rollback`
    ),
  getChurnResponseAuditLogs: (limit = 50) =>
    fetchAPI<Record<string, unknown>[]>(`/api/growth/churn-responses/audit/logs?limit=${limit}`),
  // 系统监控
  getMonitorOverview: () =>
    fetchAPI<MonitorOverview>("/api/monitor/overview"),
  getMonitorHealth: () =>
    fetchAPI<MonitorOverview["health"]>("/api/monitor/health"),
  getMonitorAlerts: () =>
    fetchAPI<MonitorAlert[]>("/api/monitor/alerts"),
  subscribeEvents: () => new EventSource(`${API_BASE}/api/events/stream`),
};
