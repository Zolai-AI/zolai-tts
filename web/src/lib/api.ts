import type {
  BudgetLimits,
  HealthResponse,
  Catalog,
  Contribution,
  MetaResponse,
  ProviderInfo,
  Recording,
  Review,
  Run,
  SecretsStatus,
  SettingsResponse,
  SynthesizeRequest,
  SynthesizeResponse,
  UsageResponse,
} from './types'

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init?.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(init?.headers ?? {}),
    },
  })
  const body = (await response.json().catch(() => ({}))) as Record<string, unknown>
  if (!response.ok || body.ok === false) {
    throw new ApiError(
      String(body.error ?? `Request failed (${response.status})`),
      response.status,
    )
  }
  return body as T
}

export const api = {
  health: () => request<HealthResponse>('/api/health'),
  meta: () => request<MetaResponse>('/api/meta'),
  providers: () => request<{ ok: true; providers: ProviderInfo[] }>('/api/providers'),
  catalog: (name: string, refresh = true) =>
    request<{ ok: true; catalog: Catalog }>(
      `/api/providers/${encodeURIComponent(name)}/catalog${refresh ? '?refresh=true' : ''}`,
    ),
  synthesize: (payload: SynthesizeRequest) =>
    request<SynthesizeResponse>('/api/synthesize', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  runs: () => request<{ ok: true; runs: Run[] }>('/api/runs'),
  run: (id: string) => request<{ ok: true; run: Run; reviews: Review[] }>(`/api/runs/${id}`),
  recordings: () => request<{ ok: true; recordings: Recording[] }>('/api/recordings'),
  uploadRecording: (form: FormData) =>
    request<{ ok: true; recording: Recording }>('/api/recordings', {
      method: 'POST',
      body: form,
    }),

  // Settings, keys, cost
  secrets: () => request<SecretsStatus>('/api/secrets'),
  setSecrets: (values: Record<string, string>) =>
    request<SecretsStatus>('/api/secrets', {
      method: 'POST',
      body: JSON.stringify({ values }),
    }),
  clearSecret: (name: string) =>
    request<SecretsStatus>(`/api/secrets/${encodeURIComponent(name)}`, { method: 'DELETE' }),
  settings: () => request<SettingsResponse>('/api/settings'),
  saveSettings: (patch: {
    tier_policy?: Record<string, string>
    budget?: Partial<BudgetLimits>
    storage?: { preferred: 'local' | 'r2' | 'auto' }
  }) => request<{ ok: true; changed: string[] }>('/api/settings', { method: 'POST', body: JSON.stringify(patch) }),
  usage: (days = 30) => request<UsageResponse>(`/api/usage?days=${days}`),
  refreshCatalogs: (providers?: string[]) =>
    request<{ ok: true; refreshed: Record<string, unknown> }>('/api/catalog/refresh', {
      method: 'POST',
      body: JSON.stringify(providers ? { providers } : {}),
    }),

  // Sound-check + contributions
  review: (payload: { run_id: string; verdict: string; rating?: number; artifacts?: string[]; note?: string }) =>
    request<{ ok: true; review: Review }>('/api/reviews', { method: 'POST', body: JSON.stringify(payload) }),
  reviews: (runId?: string) =>
    request<{ ok: true; reviews: Review[] }>(`/api/reviews${runId ? `?run_id=${runId}` : ''}`),
  contribute: (form: FormData) =>
    request<{ ok: true; contribution: Contribution }>('/api/contributions', { method: 'POST', body: form }),
  contributions: (status = '') =>
    request<{ ok: true; contributions: Contribution[] }>(`/api/contributions${status ? `?status=${status}` : ''}`),
  setContributionStatus: (id: string, status: string) =>
    request<{ ok: true; contribution: Contribution }>(`/api/contributions/${id}/status`, {
      method: 'POST',
      body: JSON.stringify({ status }),
    }),
}

export const queryKeys = {
  meta: ['meta'] as const,
  health: ['health'] as const,
  providers: ['providers'] as const,
  catalog: (name: string) => ['catalog', name] as const,
  runs: ['runs'] as const,
  recordings: ['recordings'] as const,
  secrets: ['secrets'] as const,
  settings: ['settings'] as const,
  usage: ['usage'] as const,
  reviews: ['reviews'] as const,
  contributions: ['contributions'] as const,
}

/** Format helpers shared by the studio panels. */
export function formatBytes(value: number | null | undefined): string {
  if (value === null || value === undefined) return '—'
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} kB`
  return `${(value / 1024 / 1024).toFixed(2)} MB`
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return '—'
  if (seconds < 60) return `${seconds.toFixed(2)} s`
  const mins = Math.floor(seconds / 60)
  return `${mins}m ${(seconds - mins * 60).toFixed(0)}s`
}
