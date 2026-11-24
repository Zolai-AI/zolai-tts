export interface ProviderInfo {
  name: string
  label: string
  voice_kind: 'path' | 'name'
  hosted: boolean
  note?: string
  key_env?: string | null
  key_present: boolean
}

export interface ModelInfo {
  id: string
  name: string
  voices: string[]
  formats: string[]
}

export interface Catalog {
  provider: string
  models: string[]
  model_infos: ModelInfo[]
  voices: string[]
  formats: string[]
  source: string
  error: string | null
  key_env: string | null
  key_present: boolean
}

export interface Run {
  id: string
  ok: boolean
  provider: string
  voice: string
  language: string
  model?: string | null
  format?: string
  audio_url?: string
  duration_seconds?: number | null
  created_at: string
  error?: string
  text?: string
}

export interface Recording {
  id: string
  saved_path: string
  audio_url: string
  mime: string
  format: string
  bytes: number
  created_at: string
  source_name: string
  context: { provider?: string; model?: string; voice?: string; note?: string }
}

export interface SynthesizeRequest {
  provider: string
  text: string
  language: string
  voice: string
  model?: string | null
  response_format?: string | null
  base_url?: string | null
  dry_run: boolean
}

export interface SynthesizeResponse {
  ok: boolean
  dry_run?: boolean
  plan?: Record<string, unknown>
  run?: Run
  error?: string
}
