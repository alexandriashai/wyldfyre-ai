/**
 * Wyld Fyre AI - API Client
 *
 * Handles all API requests to the backend.
 */

import { getToken, setToken, getRefreshToken, setRefreshToken, isTokenExpired, removeToken } from './auth';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Token refresh state to prevent concurrent refresh attempts
let refreshPromise: Promise<string | null> | null = null;

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

/**
 * Attempt to refresh the access token using the refresh token.
 * Returns the new access token or null if refresh fails.
 */
async function doTokenRefresh(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;

  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) return null;

    const data = await response.json();
    setToken(data.access_token);
    if (data.refresh_token) {
      setRefreshToken(data.refresh_token);
    }
    return data.access_token;
  } catch {
    return null;
  }
}

/**
 * Get a valid token, refreshing if expired.
 * Deduplicates concurrent refresh attempts.
 */
async function getValidToken(token?: string | null): Promise<string | null> {
  const currentToken = token || getToken();
  if (!currentToken) return null;

  if (!isTokenExpired(currentToken)) {
    return currentToken;
  }

  // Token expired — attempt refresh (deduplicated)
  if (!refreshPromise) {
    refreshPromise = doTokenRefresh().finally(() => {
      refreshPromise = null;
    });
  }
  return refreshPromise;
}

/**
 * Authenticated fetch wrapper that handles token refresh on 401.
 */
export async function authenticatedFetch(
  url: string,
  token?: string | null,
  options: RequestInit = {}
): Promise<Response> {
  // Get a valid token (refresh if needed)
  let validToken = await getValidToken(token);

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(validToken ? { Authorization: `Bearer ${validToken}` } : {}),
      ...(options.headers || {}),
    },
  });

  // If 401, try refreshing and retry once
  if (response.status === 401 && validToken) {
    refreshPromise = null; // Clear any stale promise
    const newToken = await doTokenRefresh();
    if (newToken) {
      // Retry with new token
      return fetch(url, {
        ...options,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${newToken}`,
          ...(options.headers || {}),
        },
      });
    }
    // Refresh failed — clear auth and redirect to login
    removeToken();
    if (typeof window !== 'undefined') {
      window.location.href = '/login';
    }
  }

  return response;
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
  root_path: string | null;
  primary_url: string | null;
  terminal_user: string | null;
  status: 'active' | 'archived' | 'completed';
  color: string | null;
  icon: string | null;
  user_id: string;
  created_at: string;
  updated_at: string;
  // Docker settings
  docker_enabled: boolean;
  docker_project_type: string | null;
  docker_node_version: string | null;
  docker_php_version: string | null;
  docker_python_version: string | null;
  docker_memory_limit: string | null;
  docker_cpu_limit: string | null;
  docker_expose_ports: string | null;
  docker_env_vars: string | null;
  docker_container_status: string | null;
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

  async create(token: string, data: { name: string; description?: string; agent_context?: string; root_path?: string; primary_url?: string; color?: string; icon?: string }) {
    const response = await fetch(`${API_BASE_URL}/api/projects`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<Project>(response);
  },

  async update(token: string, id: string, data: {
    name?: string;
    description?: string;
    agent_context?: string;
    root_path?: string;
    primary_url?: string;
    terminal_user?: string;
    status?: string;
    color?: string;
    icon?: string;
    // Docker settings
    docker_enabled?: boolean;
    docker_project_type?: string;
    docker_node_version?: string;
    docker_php_version?: string;
    docker_python_version?: string;
    docker_memory_limit?: string;
    docker_cpu_limit?: string;
    docker_expose_ports?: string;
    docker_env_vars?: string;
  }) {
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
  tags: string[];
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
    tags?: string[];
    page?: number;
    page_size?: number;
  }) {
    const searchParams = new URLSearchParams();
    if (params?.project_id) searchParams.set('project_id', params.project_id);
    if (params?.domain_id) searchParams.set('domain_id', params.domain_id);
    if (params?.status) searchParams.set('status', params.status);
    if (params?.search) searchParams.set('search', params.search);
    if (params?.tags?.length) searchParams.set('tags', params.tags.join(','));
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

  async create(token: string, data: { title?: string; project_id: string; domain_id?: string }) {
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

  async getActivePlan(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/conversations/${id}/active-plan`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      conversation_id: string;
      has_active_plan: boolean;
      plan: {
        id: string;
        title: string;
        description?: string;
        status: string;
        steps: Array<{
          id: string;
          order: number;
          title: string;
          description: string;
          status: string;
          agent?: string;
          todos?: string[];
          output?: string;
          error?: string;
          started_at?: string;
          completed_at?: string;
        }>;
        current_step: number;
        progress: number;
        created_at: string;
        approved_at?: string;
        metadata?: Record<string, unknown>;
      } | null;
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

  async updateTags(token: string, id: string, tags: string[]) {
    const response = await fetch(`${API_BASE_URL}/api/conversations/${id}/tags`, {
      method: 'PUT',
      headers: getHeaders(token),
      body: JSON.stringify({ tags }),
    });
    return handleResponse<Conversation>(response);
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

  async learnings(token: string, phase?: string, projectId?: string, scope?: string) {
    const searchParams = new URLSearchParams();
    if (phase) searchParams.set('phase', phase);
    if (projectId) searchParams.set('project_id', projectId);
    if (scope) searchParams.set('scope', scope);

    const url = `${API_BASE_URL}/api/memory/learnings${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      learnings: Array<{
        id: string;
        phase: string;
        category?: string;
        content: string;
        outcome: string;
        created_at: string;
        scope?: string;
        project_id?: string;
        project_name?: string;
      }>;
    }>(response);
  },

  async store(token: string, data: {
    content: string;
    phase?: string;
    category?: string;
    scope?: string;
    project_id?: string;
    domain_id?: string;
    confidence?: number;
  }) {
    const response = await fetch(`${API_BASE_URL}/api/memory/learnings`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{
      id: string;
      content: string;
      phase?: string;
      category?: string;
      scope?: string;
      created_at?: string;
      message?: string;
      error?: string;
    }>(response);
  },

  async get(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/memory/learnings/${id}`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      id: string;
      content: string;
      phase?: string;
      category?: string;
      confidence?: number;
      created_at?: string;
      updated_at?: string;
      metadata?: Record<string, unknown>;
    }>(response);
  },

  async update(token: string, id: string, data: {
    content?: string;
    phase?: string;
    category?: string;
    confidence?: number;
    scope?: string;
    project_id?: string | null;
    metadata?: Record<string, unknown>;
  }) {
    const response = await fetch(`${API_BASE_URL}/api/memory/learnings/${id}`, {
      method: 'PUT',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{
      id: string;
      content: string;
      phase?: string;
      category?: string;
      confidence?: number;
      scope?: string;
      project_id?: string;
      updated_at?: string;
      message?: string;
    }>(response);
  },

  async delete(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/memory/learnings/${id}`, {
      method: 'DELETE',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string; id: string }>(response);
  },

  async synthesize(token: string, data: {
    content: string;
    project_id?: string;
    domain_id?: string;
    conversation_id?: string;
    verify?: boolean;
    mode?: "conversation" | "codebase" | "question";
    question?: string;
    file_patterns?: string[];
  }) {
    const response = await fetch(`${API_BASE_URL}/api/memory/synthesize`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{
      proposals: Array<{
        action: "create" | "update" | "delete";
        content: string | null;
        category?: string;
        confidence: number;
        verified: boolean;
        scope: string;
        evidence?: string;
        evidence_detail?: {
          verdict: "VERIFIED" | "PARTIALLY_VERIFIED" | "UNVERIFIED" | "CONTRADICTED";
          supporting_evidence: string[];
          contradicting_evidence: string[];
          files_searched: number;
          summary?: string;
        };
        reason?: string;
        related_existing?: { id: string; content: string; similarity: number } | null;
      }>;
      answer?: string;
      mode: string;
      files_analyzed?: string[];
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

// System AI Config Types
export interface SystemAIConfig {
  router_enabled: boolean;
  router_up_threshold: number;
  router_down_threshold: number;
  router_latency_budget_ms: number;
  router_type: string;
  aider_enabled: boolean;
  aider_default_model: string;
  aider_edit_format: string;
  aider_map_tokens: number;
}

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

  async getSystemAI(token: string) {
    const response = await fetch(`${API_BASE_URL}/api/settings/system/ai`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<SystemAIConfig>(response);
  },

  async updateSystemAI(token: string, data: SystemAIConfig) {
    const response = await fetch(`${API_BASE_URL}/api/settings/system/ai`, {
      method: 'PUT',
      headers: getHeaders(token),
      body: JSON.stringify(data),
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

// Workspace Types
export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number | null;
  modified_at?: string | null;
  children?: FileNode[] | null;
  is_binary?: boolean;
}

export interface FileTreeResponse {
  root: string;
  nodes: FileNode[];
}

export interface FileContentResponse {
  path: string;
  content: string;
  size: number;
  language: string | null;
  is_binary: boolean;
}

export interface GitFileStatus {
  path: string;
  status: string;
}

export interface GitStatusResponse {
  branch: string | null;
  is_clean: boolean;
  modified: GitFileStatus[];
  untracked: string[];
  staged: GitFileStatus[];
  ahead: number;
  behind: number;
  has_remote: boolean;
}

export interface GitLogEntry {
  hash: string;
  short_hash: string;
  message: string;
  author: string;
  date: string;
  files_changed: number | null;
}

export interface DeployResponse {
  deploy_id: string;
  status: string;
  stages: Array<{ name: string; status: string; message?: string | null }>;
  commit_hash: string | null;
  message: string | null;
}

export interface DeployHistoryEntry {
  id: string;
  commit_hash: string | null;
  message: string | null;
  domain: string | null;
  deploy_method: string | null;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  duration_ms: number | null;
}

export interface FileSearchResult {
  path: string;
  line_number: number;
  line_content: string;
  context_before: string[];
  context_after: string[];
}

// Workspace API
export const workspaceApi = {
  // File operations
  async getFileTree(token: string, projectId: string, params?: { path?: string; depth?: number; show_hidden?: boolean }) {
    const searchParams = new URLSearchParams();
    if (params?.path) searchParams.set('path', params.path);
    if (params?.depth) searchParams.set('depth', params.depth.toString());
    if (params?.show_hidden) searchParams.set('show_hidden', 'true');

    const url = `${API_BASE_URL}/api/projects/${projectId}/files${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetch(url, { headers: getHeaders(token) });
    return handleResponse<FileTreeResponse>(response);
  },

  async getFileContent(token: string, projectId: string, path: string) {
    const searchParams = new URLSearchParams({ path });
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/files/content?${searchParams}`, {
      headers: getHeaders(token),
    });
    return handleResponse<FileContentResponse>(response);
  },

  async writeFileContent(token: string, projectId: string, path: string, content: string) {
    const searchParams = new URLSearchParams({ path });
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/files/content?${searchParams}`, {
      method: 'PUT',
      headers: getHeaders(token),
      body: JSON.stringify({ content }),
    });
    return handleResponse<FileContentResponse>(response);
  },

  async createFile(token: string, projectId: string, path: string, isDirectory: boolean = false) {
    const searchParams = new URLSearchParams({ path });
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/files?${searchParams}`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ is_directory: isDirectory }),
    });
    return handleResponse<FileNode>(response);
  },

  async deleteFile(token: string, projectId: string, path: string) {
    const searchParams = new URLSearchParams({ path });
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/files?${searchParams}`, {
      method: 'DELETE',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },

  async renameFile(token: string, projectId: string, oldPath: string, newPath: string) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/files/rename`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ old_path: oldPath, new_path: newPath }),
    });
    return handleResponse<FileNode>(response);
  },

  async searchFiles(token: string, projectId: string, query: string, glob?: string) {
    const searchParams = new URLSearchParams({ q: query });
    if (glob) searchParams.set('glob', glob);
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/files/search?${searchParams}`, {
      headers: getHeaders(token),
    });
    return handleResponse<{ query: string; matches: FileSearchResult[]; total_matches: number; files_searched: number }>(response);
  },

  // Git operations
  async getGitStatus(token: string, projectId: string) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/status`, {
      headers: getHeaders(token),
    });
    return handleResponse<GitStatusResponse>(response);
  },

  async gitCommit(token: string, projectId: string, message: string, files?: string[]) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/commit`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ message, files }),
    });
    return handleResponse<{ commit_hash: string; message: string; files_changed: number }>(response);
  },

  async gitPush(token: string, projectId: string) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/push`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },

  async getGitLog(token: string, projectId: string, limit: number = 20) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/log?limit=${limit}`, {
      headers: getHeaders(token),
    });
    return handleResponse<{ entries: GitLogEntry[]; branch: string | null }>(response);
  },

  async getGitDiff(token: string, projectId: string) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/diff`, {
      headers: getHeaders(token),
    });
    return handleResponse<{ diff: string; files_changed: number; insertions: number; deletions: number }>(response);
  },

  async getGitFileContent(token: string, projectId: string, path: string, ref: string = "HEAD") {
    const searchParams = new URLSearchParams({ path, ref });
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/file-content?${searchParams}`, {
      headers: getHeaders(token),
    });
    return handleResponse<{ content: string; ref: string; path: string }>(response);
  },

  // Deploy operations
  async deploy(token: string, projectId: string, message?: string, domainId?: string) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/deploy`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ message, domain_id: domainId }),
    });
    return handleResponse<DeployResponse>(response);
  },

  async getDeployHistory(token: string, projectId: string, limit: number = 10) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/deploys?limit=${limit}`, {
      headers: getHeaders(token),
    });
    return handleResponse<{ deploys: DeployHistoryEntry[]; total: number }>(response);
  },

  async rollback(token: string, projectId: string, commitHash?: string) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/rollback`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ commit_hash: commitHash }),
    });
    return handleResponse<{ revert_commit_hash: string; message: string; deploy_triggered: boolean }>(response);
  },

  // Health
  async getProjectHealth(token: string, projectId: string) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/health`, {
      headers: getHeaders(token),
    });
    return handleResponse<{ domain: string; status: string; response_time_ms: number | null; checked_at: string | null }>(response);
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
  input_tokens?: number;
  output_tokens?: number;
  cached_tokens?: number;
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

// Integration Types
export interface Template {
  id: string;
  name: string;
  category: string;
  description: string | null;
  html: string;
  css: string | null;
  js: string | null;
  thumbnail_url: string | null;
  tags: string[];
  is_public: boolean;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface GrapesJSBlock {
  id: string;
  label: string;
  category: string;
  content: string;
  attributes?: Record<string, unknown>;
}

export interface IntegrationStatus {
  name: string;
  enabled: boolean;
  healthy: boolean;
  url: string | null;
  version: string | null;
  message: string | null;
}

export interface IntegrationsStatus {
  grapesjs: IntegrationStatus;
  nocobase: IntegrationStatus;
  webstudio: IntegrationStatus;
  mobirise: IntegrationStatus;
}

// Integrations API
export const integrationsApi = {
  // Template Library
  async listTemplates(token: string, params?: { category?: string; search?: string; tag?: string; page?: number }) {
    const searchParams = new URLSearchParams();
    if (params?.category) searchParams.set('category', params.category);
    if (params?.search) searchParams.set('search', params.search);
    if (params?.tag) searchParams.set('tag', params.tag);
    if (params?.page) searchParams.set('page', params.page.toString());

    const url = `${API_BASE_URL}/api/integrations/templates${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetch(url, { headers: getHeaders(token) });
    return handleResponse<{ templates: Template[]; total: number; page: number; per_page: number }>(response);
  },

  async getTemplate(token: string, templateId: string) {
    const response = await fetch(`${API_BASE_URL}/api/integrations/templates/${templateId}`, {
      headers: getHeaders(token),
    });
    return handleResponse<Template>(response);
  },

  async createTemplate(token: string, data: {
    name: string;
    category?: string;
    description?: string;
    html: string;
    css?: string;
    js?: string;
    tags?: string[];
    is_public?: boolean;
  }) {
    const response = await fetch(`${API_BASE_URL}/api/integrations/templates`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<Template>(response);
  },

  async updateTemplate(token: string, templateId: string, data: Partial<{
    name: string;
    category: string;
    description: string;
    html: string;
    css: string;
    tags: string[];
    is_public: boolean;
  }>) {
    const response = await fetch(`${API_BASE_URL}/api/integrations/templates/${templateId}`, {
      method: 'PUT',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<Template>(response);
  },

  async deleteTemplate(token: string, templateId: string) {
    const response = await fetch(`${API_BASE_URL}/api/integrations/templates/${templateId}`, {
      method: 'DELETE',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },

  async getGrapesJSBlocks(token: string, category?: string) {
    const searchParams = new URLSearchParams();
    if (category) searchParams.set('category', category);

    const url = `${API_BASE_URL}/api/integrations/templates/blocks/grapesjs${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetch(url, { headers: getHeaders(token) });
    return handleResponse<{ blocks: GrapesJSBlock[] }>(response);
  },

  // NocoBase
  async createNocoBaseCollection(token: string, data: {
    name: string;
    title?: string;
    fields: Array<{ name: string; type: string; title?: string; required?: boolean; unique?: boolean }>;
  }) {
    const response = await fetch(`${API_BASE_URL}/api/integrations/nocobase/collections`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{ name: string; title: string | null; fields: unknown[]; created_at: string | null }>(response);
  },

  async nocobaseProxy(token: string, method: string, path: string, body?: Record<string, unknown>, params?: Record<string, string>) {
    const response = await fetch(`${API_BASE_URL}/api/integrations/nocobase/proxy`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ method, path, body, params }),
    });
    return handleResponse<{ status_code: number; data: unknown; error: string | null }>(response);
  },

  // Webstudio
  async webstudioExport(token: string, projectId: string, data: {
    project_url: string;
    output_format?: string;
    output_path?: string;
  }) {
    const response = await fetch(`${API_BASE_URL}/api/integrations/projects/${projectId}/webstudio/export`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{ status: string; output_path: string | null; files_created: number; message: string | null }>(response);
  },

  async webstudioBuild(token: string, projectId: string, projectPath?: string) {
    const response = await fetch(`${API_BASE_URL}/api/integrations/projects/${projectId}/webstudio/build`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ project_path: projectPath }),
    });
    return handleResponse<{ status: string; build_path: string | null; message: string | null }>(response);
  },

  // Mobirise
  async mobiriseImport(token: string, projectId: string, data: {
    source_path: string;
    target_path?: string;
    import_assets?: boolean;
  }) {
    const response = await fetch(`${API_BASE_URL}/api/integrations/projects/${projectId}/mobirise/import`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{ status: string; files_imported: number; html_files: string[]; asset_files: string[]; message: string | null }>(response);
  },

  // Status
  async getStatus(token: string) {
    const response = await fetch(`${API_BASE_URL}/api/integrations/status`, {
      headers: getHeaders(token),
    });
    return handleResponse<IntegrationsStatus>(response);
  },
};

// GitHub Types
export interface GitHubGlobalSettings {
  enabled: boolean;
  pat_configured: boolean;
  pat_source: 'env' | 'admin' | null;
  pat_last_updated: string | null;
}

export interface GitHubTestResult {
  success: boolean;
  username: string | null;
  scopes: string[] | null;
  error: string | null;
}

export interface GitHubProjectSettings {
  has_override: boolean;
  repo_url: string | null;
  repo_name: string | null;
  repo_linked: boolean;
}

export interface GitHubRepo {
  id: number;
  name: string;
  full_name: string;
  html_url: string;
  clone_url: string;
  private: boolean;
  description: string | null;
  default_branch?: string | null;
}

export interface GitHubPullRequest {
  number: number;
  title: string;
  body: string | null;
  state: string;
  head: string;
  base: string;
  html_url: string;
  created_at: string;
  user: string;
  mergeable: boolean | null;
  draft: boolean;
  merged?: boolean;
  merge_commit_sha?: string | null;
  comments?: number;
  review_comments?: number;
  commits?: number;
  additions?: number;
  deletions?: number;
  changed_files?: number;
}

export interface GitHubIssue {
  number: number;
  title: string;
  body: string | null;
  state: string;
  html_url: string;
  created_at: string;
  user: string;
  labels: string[];
  comments: number;
}

export interface Branch {
  name: string;
  commit: string;
  is_current: boolean;
  is_remote: boolean;
  upstream: string | null;
  ahead: number;
  behind: number;
}

export interface BranchListResponse {
  current: string;
  branches: Branch[];
}

export interface BranchResponse {
  name: string;
  commit: string;
  is_current: boolean;
}

export interface MergeResponse {
  success: boolean;
  merged_commit: string | null;
  conflicts: string[] | null;
  message: string | null;
}

export interface ConflictCheckResponse {
  has_conflicts: boolean;
  conflicting_files: string[];
  merge_in_progress: boolean;
  rebase_in_progress: boolean;
}

// GitHub API
export const githubApi = {
  // Global settings (admin only)
  async getGlobalSettings(token: string) {
    const response = await fetch(`${API_BASE_URL}/api/github/settings`, {
      headers: getHeaders(token),
    });
    return handleResponse<GitHubGlobalSettings>(response);
  },

  async updateGlobalSettings(token: string, data: { enabled?: boolean; pat?: string; clear_pat?: boolean }) {
    const response = await fetch(`${API_BASE_URL}/api/github/settings`, {
      method: 'PUT',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<GitHubGlobalSettings>(response);
  },

  async testGlobalPat(token: string) {
    const response = await fetch(`${API_BASE_URL}/api/github/settings/test`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<GitHubTestResult>(response);
  },

  async testPat(token: string, pat: string) {
    const response = await fetch(`${API_BASE_URL}/api/github/test`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ pat }),
    });
    return handleResponse<GitHubTestResult>(response);
  },

  // Repository management
  async listRepos(token: string, page: number = 1, perPage: number = 30) {
    const searchParams = new URLSearchParams({ page: page.toString(), per_page: perPage.toString() });
    const response = await fetch(`${API_BASE_URL}/api/github/repos?${searchParams}`, {
      headers: getHeaders(token),
    });
    return handleResponse<GitHubRepo[]>(response);
  },

  async createRepo(token: string, data: { name: string; description?: string; private?: boolean }) {
    const response = await fetch(`${API_BASE_URL}/api/github/repos`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<GitHubRepo>(response);
  },

  // Project settings
  async getProjectSettings(token: string, projectId: string) {
    const response = await fetch(`${API_BASE_URL}/api/github/projects/${projectId}/settings`, {
      headers: getHeaders(token),
    });
    return handleResponse<GitHubProjectSettings>(response);
  },

  async updateProjectSettings(token: string, projectId: string, data: { pat?: string; repo_url?: string; clear_pat?: boolean }) {
    const response = await fetch(`${API_BASE_URL}/api/github/projects/${projectId}/settings`, {
      method: 'PUT',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<GitHubProjectSettings>(response);
  },

  async clearProjectSettings(token: string, projectId: string) {
    const response = await fetch(`${API_BASE_URL}/api/github/projects/${projectId}/settings`, {
      method: 'DELETE',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },

  async linkRepo(token: string, projectId: string, data: { repo_url: string; init_git?: boolean }) {
    const response = await fetch(`${API_BASE_URL}/api/github/projects/${projectId}/repo/link`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{ message: string }>(response);
  },

  async initRepo(token: string, projectId: string, data: { name: string; description?: string; private?: boolean }) {
    const response = await fetch(`${API_BASE_URL}/api/github/projects/${projectId}/repo/init`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<GitHubRepo>(response);
  },

  // Pull Requests
  async listPullRequests(token: string, projectId: string, state: string = 'open') {
    const searchParams = new URLSearchParams({ state });
    const response = await fetch(`${API_BASE_URL}/api/github/projects/${projectId}/pulls?${searchParams}`, {
      headers: getHeaders(token),
    });
    return handleResponse<GitHubPullRequest[]>(response);
  },

  async createPullRequest(token: string, projectId: string, data: { title: string; body?: string; head?: string; base?: string; draft?: boolean }) {
    const response = await fetch(`${API_BASE_URL}/api/github/projects/${projectId}/pulls`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<GitHubPullRequest>(response);
  },

  async getPullRequest(token: string, projectId: string, number: number) {
    const response = await fetch(`${API_BASE_URL}/api/github/projects/${projectId}/pulls/${number}`, {
      headers: getHeaders(token),
    });
    return handleResponse<GitHubPullRequest>(response);
  },

  async mergePullRequest(token: string, projectId: string, number: number, data: { merge_method?: 'merge' | 'squash' | 'rebase'; commit_message?: string }) {
    const response = await fetch(`${API_BASE_URL}/api/github/projects/${projectId}/pulls/${number}/merge`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{ success: boolean; sha: string | null; message: string }>(response);
  },

  // Issues
  async listIssues(token: string, projectId: string, state: string = 'open', labels?: string) {
    const searchParams = new URLSearchParams({ state });
    if (labels) searchParams.set('labels', labels);
    const response = await fetch(`${API_BASE_URL}/api/github/projects/${projectId}/issues?${searchParams}`, {
      headers: getHeaders(token),
    });
    return handleResponse<GitHubIssue[]>(response);
  },

  async createIssue(token: string, projectId: string, data: { title: string; body?: string; labels?: string[] }) {
    const response = await fetch(`${API_BASE_URL}/api/github/projects/${projectId}/issues`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<GitHubIssue>(response);
  },
};

// Add branch management methods to workspaceApi
export const branchApi = {
  async getBranches(token: string, projectId: string, includeRemote: boolean = true) {
    const searchParams = new URLSearchParams({ include_remote: includeRemote.toString() });
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/branches?${searchParams}`, {
      headers: getHeaders(token),
    });
    return handleResponse<BranchListResponse>(response);
  },

  async createBranch(token: string, projectId: string, data: { name: string; start_point?: string; checkout?: boolean }) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/branches`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<BranchResponse>(response);
  },

  async checkoutBranch(token: string, projectId: string, data: { branch: string; create?: boolean }) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/branches/checkout`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<BranchResponse>(response);
  },

  async deleteBranch(token: string, projectId: string, branchName: string, force: boolean = false) {
    const searchParams = new URLSearchParams({ force: force.toString() });
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/branches/${encodeURIComponent(branchName)}?${searchParams}`, {
      method: 'DELETE',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },

  async renameBranch(token: string, projectId: string, data: { old_name: string; new_name: string }) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/branches/rename`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{ message: string }>(response);
  },

  async mergeBranch(token: string, projectId: string, data: { source: string; no_ff?: boolean; squash?: boolean; message?: string }) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/merge`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<MergeResponse>(response);
  },

  async rebaseBranch(token: string, projectId: string, onto: string) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/rebase`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ onto }),
    });
    return handleResponse<MergeResponse>(response);
  },

  async abortMerge(token: string, projectId: string) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/abort`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },

  async checkConflicts(token: string, projectId: string) {
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/conflicts`, {
      headers: getHeaders(token),
    });
    return handleResponse<ConflictCheckResponse>(response);
  },

  async gitFetch(token: string, projectId: string, prune: boolean = false) {
    const searchParams = new URLSearchParams({ prune: prune.toString() });
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/fetch?${searchParams}`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },

  async gitPull(token: string, projectId: string, branch?: string, rebase: boolean = false) {
    const searchParams = new URLSearchParams({ rebase: rebase.toString() });
    if (branch) searchParams.set('branch', branch);
    const response = await fetch(`${API_BASE_URL}/api/projects/${projectId}/git/pull?${searchParams}`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },
};

// Plan CRUD Types
export interface TodoItem {
  text: string;
  completed: boolean;
}

export interface StepProgress {
  index: number;
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'skipped' | 'failed';
  agent?: string;
  todos: TodoItem[];
  notes: string[];
  completed_todos: number;
  total_todos: number;
  output?: string;
  error?: string;
  started_at?: string;
  completed_at?: string;
  estimated_duration?: string;
}

export interface PlanListItem {
  id: string;
  title: string;
  description?: string;
  status: string;
  created_at: string;
  updated_at?: string;
  total_steps: number;
  completed_steps: number;
  is_running: boolean;
  is_stuck: boolean;
  conversation_id?: string;
  project_id?: string;
}

export interface PlanDetail {
  id: string;
  title: string;
  description?: string;
  status: string;
  steps: StepProgress[];
  current_step_index: number;
  total_steps: number;
  completed_steps: number;
  is_running: boolean;
  is_complete: boolean;
  is_stuck: boolean;
  overall_progress: number;
  created_at: string;
  updated_at?: string;
  approved_at?: string;
  completed_at?: string;
  conversation_id?: string;
  user_id?: string;
  exploration_notes: string[];
  files_explored: string[];
  metadata: Record<string, unknown>;
}

export interface PlanHistoryEntry {
  timestamp: string;
  action: string;
  changes: Record<string, unknown>;
  actor?: string;
  details?: string;
}

export interface PlanOperationResponse {
  success: boolean;
  plan_id: string;
  message: string;
  plan?: PlanDetail;
}

// Plans API
export const plansApi = {
  async listPlans(token: string, options?: { status?: string; project_id?: string; limit?: number; offset?: number }) {
    const searchParams = new URLSearchParams();
    if (options?.status) searchParams.set('status', options.status);
    if (options?.project_id) searchParams.set('project_id', options.project_id);
    if (options?.limit) searchParams.set('limit', options.limit.toString());
    if (options?.offset) searchParams.set('offset', options.offset.toString());

    const url = `${API_BASE_URL}/api/plans${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      plans: PlanListItem[];
      total: number;
      offset: number;
      limit: number;
      filter_status?: string;
    }>(response);
  },

  async getPlan(token: string, planId: string, includeHistory: boolean = false) {
    const searchParams = new URLSearchParams();
    if (includeHistory) searchParams.set('include_history', 'true');

    const url = `${API_BASE_URL}/api/plans/${planId}${searchParams.toString() ? `?${searchParams}` : ''}`;
    const response = await fetch(url, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<PlanDetail>(response);
  },

  async updatePlan(token: string, planId: string, data: {
    title?: string;
    description?: string;
    steps?: Array<Record<string, unknown>>;
    status?: string;
    metadata?: Record<string, unknown>;
  }) {
    const response = await fetch(`${API_BASE_URL}/api/plans/${planId}`, {
      method: 'PATCH',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<PlanOperationResponse>(response);
  },

  async deletePlan(token: string, planId: string) {
    const response = await fetch(`${API_BASE_URL}/api/plans/${planId}`, {
      method: 'DELETE',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },

  async getPlanHistory(token: string, planId: string, limit: number = 50) {
    const searchParams = new URLSearchParams({ limit: limit.toString() });
    const response = await fetch(`${API_BASE_URL}/api/plans/${planId}/history?${searchParams}`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      plan_id: string;
      entries: PlanHistoryEntry[];
      total_entries: number;
    }>(response);
  },

  async clonePlan(token: string, planId: string, newTitle?: string, resetStatus: boolean = true) {
    const response = await fetch(`${API_BASE_URL}/api/plans/${planId}/clone`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ new_title: newTitle, reset_status: resetStatus }),
    });
    return handleResponse<PlanOperationResponse>(response);
  },

  async followUpPlan(token: string, planId: string, context?: string, action: string = 'analyze_and_resume') {
    const response = await fetch(`${API_BASE_URL}/api/plans/${planId}/follow-up`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ context, action }),
    });
    return handleResponse<PlanOperationResponse>(response);
  },

  async modifyPlan(token: string, planId: string, request: string, constraints?: string[]) {
    const response = await fetch(`${API_BASE_URL}/api/plans/${planId}/modify`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ request, constraints }),
    });
    return handleResponse<PlanOperationResponse>(response);
  },

  async pausePlan(token: string, planId: string) {
    const response = await fetch(`${API_BASE_URL}/api/plans/${planId}/pause`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<PlanOperationResponse>(response);
  },

  async resumePlan(token: string, planId: string) {
    const response = await fetch(`${API_BASE_URL}/api/plans/${planId}/resume`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<PlanOperationResponse>(response);
  },
};
