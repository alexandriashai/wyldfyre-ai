/**
 * Wyld Fyre AI - API Client
 *
 * Handles all API requests to the backend.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public details?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let errorMessage = `HTTP error ${response.status}`;
    let details: unknown;

    try {
      const errorData = await response.json();
      errorMessage = errorData.detail || errorData.message || errorMessage;
      details = errorData;
    } catch {
      // Response wasn't JSON
    }

    throw new ApiError(response.status, errorMessage, details);
  }

  // Handle empty responses
  const text = await response.text();
  if (!text) {
    return {} as T;
  }

  return JSON.parse(text) as T;
}

function getHeaders(token?: string | null): HeadersInit {
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
}

// Authentication API
export const authApi = {
  async login(email: string, password: string) {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ email, password }),
    });
    return handleResponse<{
      access_token: string;
      refresh_token: string;
      expires_in: number;
      user: {
        id: string;
        email: string;
        username: string;
        display_name: string | null;
        is_admin: boolean;
      };
    }>(response);
  },

  async register(email: string, password: string, displayName?: string) {
    const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({
        email,
        password,
        display_name: displayName,
      }),
    });
    return handleResponse<{
      access_token: string;
      refresh_token: string;
      expires_in: number;
      user: {
        id: string;
        email: string;
        username: string;
        display_name: string | null;
        is_admin: boolean;
      };
    }>(response);
  },

  async logout(token: string) {
    const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },

  async me(token: string) {
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      id: string;
      email: string;
      username: string;
      display_name: string | null;
      is_admin: boolean;
      role: string;
    }>(response);
  },

  async refreshToken(refreshToken: string) {
    const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: getHeaders(),
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    return handleResponse<{
      access_token: string;
      refresh_token: string;
      expires_in: number;
    }>(response);
  },
};

// Agent Tool Types
export interface ToolInfo {
  name: string;
  description: string;
  category: string;
  permission_level: number;
}

export interface AgentToolsResponse {
  agent_name: string;
  agent_type: string;
  description: string;
  permission_level: number;
  tools: ToolInfo[];
  capabilities: string[];
  allowed_capabilities: string[];
}

// Agents API
export const agentsApi = {
  async list(token: string) {
    const response = await fetch(`${API_BASE_URL}/api/agents`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<Array<{
      name: string;
      type: string;
      status: string;
      uptime_seconds: number;
      tasks_completed: number;
      current_task_id: string | null;
    }>>(response);
  },

  async get(token: string, name: string) {
    const response = await fetch(`${API_BASE_URL}/api/agents/${name}`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      name: string;
      type: string;
      status: string;
      uptime_seconds: number;
      tasks_completed: number;
      current_task_id: string | null;
      tools: string[];
    }>(response);
  },

  async getTools(token: string, name: string) {
    const response = await fetch(`${API_BASE_URL}/api/agents/${name}/tools`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<AgentToolsResponse>(response);
  },

  async logs(token: string, name: string, limit: number = 100) {
    const searchParams = new URLSearchParams({ limit: limit.toString() });
    const response = await fetch(`${API_BASE_URL}/api/agents/${name}/logs?${searchParams}`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    // API returns {agent, logs, count} - extract the logs array
    const data = await handleResponse<{
      agent: string;
      logs: Array<{
        timestamp: string;
        level: string;
        message: string;
      }>;
      count: number;
    }>(response);
    return data.logs || [];
  },

  async restart(token: string, name: string) {
    const response = await fetch(`${API_BASE_URL}/api/agents/${name}/restart`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },
};

// Tasks API
export const tasksApi = {
  async list(token: string, params?: { status?: string; limit?: number; offset?: number }) {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.offset) searchParams.set('offset', params.offset.toString());

    const url = `${API_BASE_URL}/api/tasks${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<Array<{
      id: string;
      task_type: string;
      status: string;
      created_at: string;
      completed_at: string | null;
      duration_ms: number | null;
    }>>(response);
  },

  async get(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/tasks/${id}`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      id: string;
      task_type: string;
      status: string;
      input_data: unknown;
      output_data: unknown;
      error_message: string | null;
      created_at: string;
      completed_at: string | null;
      duration_ms: number | null;
    }>(response);
  },

  async create(token: string, data: { task_type: string; payload: unknown }) {
    const response = await fetch(`${API_BASE_URL}/api/tasks`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{
      id: string;
      task_type: string;
      status: string;
    }>(response);
  },

  async cancel(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/tasks/${id}/cancel`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },
};

// Projects API
export interface Project {
  id: string;
  name: string;
  description: string | null;
  agent_context: string | null;
  status: 'active' | 'archived' | 'completed';
  color: string | null;
  icon: string | null;
  user_id: string;
  created_at: string;
  updated_at: string;
}

export interface ProjectWithStats extends Project {
  conversation_count: number;
  task_count: number;
  domain_count: number;
  total_cost: number;
}

export const projectsApi = {
  async list(token: string, params?: { status?: string; page?: number; page_size?: number }) {
    const searchParams = new URLSearchParams();
    if (params?.status) searchParams.set('status', params.status);
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.page_size) searchParams.set('page_size', params.page_size.toString());

    const url = `${API_BASE_URL}/api/projects${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      projects: Project[];
      total: number;
      page: number;
      page_size: number;
    }>(response);
  },

  async get(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${id}`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<ProjectWithStats>(response);
  },

  async create(token: string, data: { name: string; description?: string; agent_context?: string; color?: string; icon?: string }) {
    const response = await fetch(`${API_BASE_URL}/api/projects`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<Project>(response);
  },

  async update(token: string, id: string, data: { name?: string; description?: string; agent_context?: string; status?: string; color?: string; icon?: string }) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${id}`, {
      method: 'PATCH',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<Project>(response);
  },

  async delete(token: string, id: string, archive: boolean = true) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${id}?archive=${archive}`, {
      method: 'DELETE',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },
};

// Conversation Types
export interface Conversation {
  id: string;
  title: string | null;
  summary: string | null;
  status: 'ACTIVE' | 'ARCHIVED' | 'DELETED';
  message_count: number;
  last_message_at: string | null;
  plan_content: string | null;
  plan_status: 'DRAFT' | 'PENDING' | 'APPROVED' | 'REJECTED' | 'COMPLETED' | null;
  plan_approved_at: string | null;
  user_id: string;
  project_id: string | null;
  domain_id: string | null;
  created_at: string;
  updated_at: string;
}

// Conversations API
export const conversationsApi = {
  async list(token: string, params?: {
    project_id?: string;
    domain_id?: string;
    status?: string;
    search?: string;
    page?: number;
    page_size?: number;
  }) {
    const searchParams = new URLSearchParams();
    if (params?.project_id) searchParams.set('project_id', params.project_id);
    if (params?.domain_id) searchParams.set('domain_id', params.domain_id);
    if (params?.status) searchParams.set('status', params.status);
    if (params?.search) searchParams.set('search', params.search);
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.page_size) searchParams.set('page_size', params.page_size.toString());

    const url = `${API_BASE_URL}/api/conversations${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      conversations: Conversation[];
      total: number;
      page: number;
      page_size: number;
    }>(response);
  },

  async get(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/conversations/${id}`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    const data = await handleResponse<{
      conversation: Conversation;
      messages: Array<{
        id: string;
        role: 'user' | 'assistant';
        content: string;
        agent?: string;
        timestamp: string;
      }>;
    }>(response);
    // Map to expected format
    return {
      ...data.conversation,
      messages: data.messages.map(m => ({
        ...m,
        created_at: m.timestamp,
      })).reverse(), // Reverse to show oldest first
    };
  },

  async create(token: string, data: { title?: string; project_id?: string; domain_id?: string }) {
    const response = await fetch(`${API_BASE_URL}/api/conversations`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<Conversation>(response);
  },

  async update(token: string, id: string, data: { title?: string; project_id?: string; domain_id?: string; status?: string }) {
    const response = await fetch(`${API_BASE_URL}/api/conversations/${id}`, {
      method: 'PATCH',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<Conversation>(response);
  },

  async delete(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/conversations/${id}`, {
      method: 'DELETE',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },

  // Plan management
  async getPlan(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/conversations/${id}/plan`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      conversation_id: string;
      plan_content: string | null;
      plan_status: string | null;
      plan_approved_at: string | null;
    }>(response);
  },

  async updatePlan(token: string, id: string, data: { plan_content: string; plan_status?: string }) {
    const response = await fetch(`${API_BASE_URL}/api/conversations/${id}/plan`, {
      method: 'PUT',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{
      conversation_id: string;
      plan_content: string;
      plan_status: string;
      message: string;
    }>(response);
  },

  async approvePlan(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/conversations/${id}/plan/approve`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<{
      conversation_id: string;
      plan_status: string;
      plan_approved_at: string;
      message: string;
    }>(response);
  },

  async rejectPlan(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/conversations/${id}/plan/reject`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<{
      conversation_id: string;
      plan_status: string;
      message: string;
    }>(response);
  },
};

// Memory API
export const memoryApi = {
  async search(token: string, query: string, limit?: number) {
    const searchParams = new URLSearchParams({ query });
    if (limit) searchParams.set('limit', limit.toString());

    const response = await fetch(`${API_BASE_URL}/api/memory/search?${searchParams}`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      results: Array<{
        id: string;
        content: string;
        phase: string;
        category: string;
        score: number;
        created_at: string;
        metadata: Record<string, unknown>;
      }>;
    }>(response);
  },

  async stats(token: string) {
    const response = await fetch(`${API_BASE_URL}/api/memory/stats`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      total_memories: number;
      by_tier: Record<string, number>;
      by_agent: Record<string, number>;
    }>(response);
  },

  async learnings(token: string, phase?: string) {
    const searchParams = new URLSearchParams();
    if (phase) searchParams.set('phase', phase);

    const url = `${API_BASE_URL}/api/memory/learnings${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      learnings: Array<{
        id: string;
        phase: string;
        content: string;
        outcome: string;
        created_at: string;
      }>;
    }>(response);
  },
};

// Domain Types
export interface Domain {
  id: string;
  domain_name: string;
  status: string;
  ssl_enabled: boolean;
  ssl_expires_at: string | null;
  web_root: string | null;
  proxy_target: string | null;
  nginx_config_path: string | null;
  project_id: string | null;
  project_name: string | null;
  created_at: string;
}

// Domains API
export const domainsApi = {
  async list(token: string, params?: { project_id?: string; status?: string }) {
    const searchParams = new URLSearchParams();
    if (params?.project_id) searchParams.set('project_id', params.project_id);
    if (params?.status) searchParams.set('status', params.status);

    const url = `${API_BASE_URL}/api/domains${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<Domain[]>(response);
  },

  async create(token: string, data: {
    domain_name: string;
    proxy_target?: string;
    web_root?: string;
    ssl_enabled?: boolean;
    project_id?: string;
  }) {
    const response = await fetch(`${API_BASE_URL}/api/domains`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<Domain>(response);
  },

  async deploy(token: string, domainName: string) {
    const response = await fetch(`${API_BASE_URL}/api/domains/${domainName}/deploy`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<{ task_id: string; message: string }>(response);
  },

  async sync(token: string, domainName: string) {
    const response = await fetch(`${API_BASE_URL}/api/domains/${domainName}/sync`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<{ task_id: string; message: string; success: boolean }>(response);
  },

  async update(token: string, domainName: string, data: {
    proxy_target?: string;
    web_root?: string;
    ssl_enabled?: boolean;
    project_id?: string | null;
  }) {
    const response = await fetch(`${API_BASE_URL}/api/domains/${domainName}`, {
      method: 'PUT',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<Domain>(response);
  },

  async delete(token: string, domainName: string) {
    const response = await fetch(`${API_BASE_URL}/api/domains/${domainName}`, {
      method: 'DELETE',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },
};

// Health API
export const healthApi = {
  async check() {
    const response = await fetch(`${API_BASE_URL}/health/live`, {
      method: 'GET',
    });
    return handleResponse<{ status: string }>(response);
  },

  async ready() {
    const response = await fetch(`${API_BASE_URL}/health/ready`, {
      method: 'GET',
    });
    return handleResponse<{
      status: string;
      checks: Record<string, { status: string; message?: string }>;
    }>(response);
  },
};

// Settings API
export const settingsApi = {
  async updateProfile(token: string, data: { display_name?: string }) {
    const response = await fetch(`${API_BASE_URL}/api/settings/profile`, {
      method: 'PATCH',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{ message: string }>(response);
  },

  async updatePassword(token: string, data: { current_password: string; new_password: string }) {
    const response = await fetch(`${API_BASE_URL}/api/auth/password`, {
      method: 'PUT',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{ message: string }>(response);
  },

  async getNotifications(token: string) {
    const response = await fetch(`${API_BASE_URL}/api/settings/notifications`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      task_completions: boolean;
      agent_errors: boolean;
      ssl_expiration: boolean;
      system_updates: boolean;
    }>(response);
  },

  async updateNotifications(token: string, data: {
    task_completions?: boolean;
    agent_errors?: boolean;
    ssl_expiration?: boolean;
    system_updates?: boolean;
  }) {
    const response = await fetch(`${API_BASE_URL}/api/settings/notifications`, {
      method: 'PATCH',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{ message: string }>(response);
  },

  async getApiKeys(token: string) {
    const response = await fetch(`${API_BASE_URL}/api/settings/api-keys`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<Array<{
      id: string;
      name: string;
      key_prefix: string;
      created_at: string;
      last_used_at: string | null;
    }>>(response);
  },

  async createApiKey(token: string, data: { name: string }) {
    const response = await fetch(`${API_BASE_URL}/api/settings/api-keys`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{ id: string; key: string; name: string }>(response);
  },

  async deleteApiKey(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/settings/api-keys/${id}`, {
      method: 'DELETE',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },
};

// Push Notifications API
export const notificationsApi = {
  async subscribe(token: string, subscription: {
    endpoint: string;
    keys: {
      p256dh: string;
      auth: string;
    };
  }) {
    const response = await fetch(`${API_BASE_URL}/api/notifications/subscribe`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(subscription),
    });
    return handleResponse<{ message: string }>(response);
  },

  async unsubscribe(token: string, endpoint: string) {
    const response = await fetch(`${API_BASE_URL}/api/notifications/unsubscribe`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ endpoint }),
    });
    return handleResponse<{ message: string }>(response);
  },
};

// Usage Types
export interface ModelBreakdown {
  model: string;
  cost: number;
  percentage: number;
}

export interface AgentBreakdown {
  agent_type: string;
  cost: number;
  percentage: number;
}

export interface DailySummary {
  total_cost: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cached_tokens: number;
  request_count: number;
  period_start: string;
  period_end: string;
  breakdown_by_model: ModelBreakdown[];
  breakdown_by_agent: AgentBreakdown[];
}

export interface DailyUsagePoint {
  date: string;
  cost: number;
  tokens: number;
  requests: number;
}

export interface UsageHistory {
  period_days: number;
  total_cost: number;
  total_tokens: number;
  total_requests: number;
  daily_data: DailyUsagePoint[];
}

export interface BudgetAlert {
  id: string;
  name: string;
  description: string | null;
  threshold_amount: number;
  period: string;
  current_spend: number;
  percentage_used: number;
  is_exceeded: boolean;
  is_active: boolean;
  last_triggered_at: string | null;
  trigger_count: number;
}

export interface BudgetStatus {
  daily_spend: number;
  daily_limit: number;
  daily_percentage: number;
  hourly_rate: number;
  projected_daily: number;
  alerts: BudgetAlert[];
}

export interface UsageRecord {
  id: string;
  provider: string;
  model: string;
  usage_type: string;
  input_tokens: number;
  output_tokens: number;
  cached_tokens: number;
  cost_total: number;
  agent_type: string | null;
  agent_name: string | null;
  task_id: string | null;
  correlation_id: string | null;
  latency_ms: number | null;
  created_at: string;
}

// Usage Analytics API
export const usageApi = {
  async daily(token: string, date?: string) {
    const searchParams = new URLSearchParams();
    if (date) searchParams.set('date', date);

    const url = `${API_BASE_URL}/api/usage/daily${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<DailySummary>(response);
  },

  async byAgent(token: string, days: number = 30) {
    const searchParams = new URLSearchParams({ days: days.toString() });

    const response = await fetch(`${API_BASE_URL}/api/usage/by-agent?${searchParams}`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      period_days: number;
      total_cost: number;
      breakdown: AgentBreakdown[];
    }>(response);
  },

  async history(token: string, days: number = 30) {
    const searchParams = new URLSearchParams({ days: days.toString() });

    const response = await fetch(`${API_BASE_URL}/api/usage/history?${searchParams}`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<UsageHistory>(response);
  },

  async budget(token: string) {
    const response = await fetch(`${API_BASE_URL}/api/usage/budget`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<BudgetStatus>(response);
  },

  async records(token: string, params?: {
    page?: number;
    page_size?: number;
    agent_type?: string;
    model?: string;
  }) {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.set('page', params.page.toString());
    if (params?.page_size) searchParams.set('page_size', params.page_size.toString());
    if (params?.agent_type) searchParams.set('agent_type', params.agent_type);
    if (params?.model) searchParams.set('model', params.model);

    const url = `${API_BASE_URL}/api/usage/records${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      records: UsageRecord[];
      total: number;
      page: number;
      page_size: number;
    }>(response);
  },
};
