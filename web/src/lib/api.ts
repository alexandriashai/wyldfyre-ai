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

// Conversations API
export const conversationsApi = {
  async list(token: string) {
    const response = await fetch(`${API_BASE_URL}/api/conversations`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<Array<{
      id: string;
      title: string;
      created_at: string;
      updated_at: string;
      message_count: number;
    }>>(response);
  },

  async get(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/conversations/${id}`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<{
      id: string;
      title: string;
      messages: Array<{
        id: string;
        role: 'user' | 'assistant';
        content: string;
        created_at: string;
      }>;
    }>(response);
  },

  async create(token: string, title?: string) {
    const response = await fetch(`${API_BASE_URL}/api/conversations`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify({ title }),
    });
    return handleResponse<{
      id: string;
      title: string;
      created_at: string;
    }>(response);
  },

  async delete(token: string, id: string) {
    const response = await fetch(`${API_BASE_URL}/api/conversations/${id}`, {
      method: 'DELETE',
      headers: getHeaders(token),
    });
    return handleResponse<{ message: string }>(response);
  },
};

// Memory API
export const memoryApi = {
  async search(token: string, query: string, params?: { phase?: string; limit?: number }) {
    const searchParams = new URLSearchParams({ query });
    if (params?.phase) searchParams.set('phase', params.phase);
    if (params?.limit) searchParams.set('limit', params.limit.toString());

    const response = await fetch(`${API_BASE_URL}/api/memory/search?${searchParams}`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<Array<{
      content: string;
      phase: string;
      category: string;
      score: number;
      created_at: string;
    }>>(response);
  },
};

// Domains API
export const domainsApi = {
  async list(token: string) {
    const response = await fetch(`${API_BASE_URL}/api/domains`, {
      method: 'GET',
      headers: getHeaders(token),
    });
    return handleResponse<Array<{
      id: string;
      domain_name: string;
      status: string;
      ssl_enabled: boolean;
      ssl_expires_at: string | null;
      created_at: string;
    }>>(response);
  },

  async create(token: string, data: {
    domain_name: string;
    proxy_target?: string;
    ssl_enabled?: boolean;
  }) {
    const response = await fetch(`${API_BASE_URL}/api/domains`, {
      method: 'POST',
      headers: getHeaders(token),
      body: JSON.stringify(data),
    });
    return handleResponse<{
      id: string;
      domain_name: string;
      status: string;
    }>(response);
  },

  async deploy(token: string, domainName: string) {
    const response = await fetch(`${API_BASE_URL}/api/domains/${domainName}/deploy`, {
      method: 'POST',
      headers: getHeaders(token),
    });
    return handleResponse<{ task_id: string; message: string }>(response);
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
