import type {
  Catalog,
  ProviderInfo,
  Recording,
  Run,
  SynthesizeRequest,
  SynthesizeResponse,
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
  providers: () => request<{ ok: true; providers: ProviderInfo[] }>('/api/providers'),
  catalog: (name: string) =>
    request<{ ok: true; catalog: Catalog }>(
      `/api/providers/${encodeURIComponent(name)}/catalog?refresh=true`,
    ),
  synthesize: (payload: SynthesizeRequest) =>
    request<SynthesizeResponse>('/api/synthesize', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  runs: () => request<{ ok: true; runs: Run[] }>('/api/runs'),
  recordings: () => request<{ ok: true; recordings: Recording[] }>('/api/recordings'),
  uploadRecording: (form: FormData) =>
    request<{ ok: true; recording: Recording }>('/api/recordings', {
      method: 'POST',
      body: form,
    }),
}

export const queryKeys = {
  providers: ['providers'] as const,
  catalog: (name: string) => ['catalog', name] as const,
  runs: ['runs'] as const,
  recordings: ['recordings'] as const,
}
