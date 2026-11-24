export interface LanguageOption {
  code: string
  label: string
  status: string
}

/** One provider's published rate-limit / quota note, with source and as-of date. */
export interface ProviderLimitNote {
  note?: string
  source?: string
  as_of?: string
  [key: string]: unknown
}

export interface HealthResponse {
  ok: true
  time: string
  service: string
  version: string
  providers: string[]
  store: string
  database: DatabaseInfo
  storage: StorageInfo
  frontend_built: boolean
}

export interface MetaResponse {
  ok: true
  version: string
  languages: LanguageOption[]
  default_language: string
  max_text: number
  audio_extensions: string[]
  recording_mimes: string[]
  frontend_built: boolean
  providers: ProviderInfo[]
  models: ModelRecord[]
  voices: VoiceRecord[]
  limits: {
    provider_limits: Record<string, Record<string, ProviderLimitNote>>
    model_text_limits: Record<string, number>
  }
  storage: StorageInfo
  database: DatabaseInfo
  counts: Record<string, number>
  generated_at: string
}

export interface ProviderInfo {
  name: string
  label: string
  voice_kind: 'path' | 'name'
  hosted: boolean
  note?: string
  key_envs?: string[]
  key_present: boolean
  tier_policy?: string
}

export interface ModelInfo {
  id: string
  name: string
  voices: string[]
  formats: string[]
  tier: string
  limits: Record<string, unknown>
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
  tier_filter: string
  tier_policy: string
  details?: Record<string, unknown>
}

/** A model row as persisted in the database (list shape). */
export interface ModelRecord {
  provider_name: string
  slug: string
  title: string
  tier: string
  formats: string[]
  pricing: Record<string, unknown>
  source: string
  updated_at: string
}

export interface VoiceRecord {
  id: string
  provider_name: string
  model_slug: string
  slug: string
  label: string
  origin: string
  path: string | null
  preview_key: string | null
  contributed: boolean
}

export interface Estimate {
  provider: string
  model: string
  tier: string
  characters: number
  estimated_usd: number | null
  basis: string
}

export interface Run {
  id: string
  ok: boolean
  provider: string
  voice: string
  language: string
  model?: string | null
  tier?: string
  format?: string
  audio_url?: string
  out_path?: string
  object_key?: string | null
  storage_backend?: string
  bytes?: number | null
  elapsed_seconds?: number | null
  duration_seconds?: number | null
  characters?: number | null
  cost_usd?: number | null
  created_at: string
  error?: string | null
  text?: string
  metadata?: Record<string, unknown>
}

export interface Recording {
  id: string
  saved_path?: string
  local_path?: string | null
  audio_url: string
  mime: string
  format: string
  bytes: number
  duration_seconds?: number | null
  created_at: string
  source: string
  provider: string
  model: string
  voice: string
  note: string
  storage_backend: string
  object_key: string
}

export interface Contribution {
  id: string
  recording_id: string
  speaker_alias: string
  consent: boolean
  license: string
  language: string
  prompt: string
  mic_device: string
  note: string
  status: 'new' | 'reviewing' | 'accepted' | 'rejected'
  audio_url: string
  saved_path?: string
  bytes: number
  format: string
  duration_seconds?: number | null
  created_at: string
}

export interface Review {
  id: string
  run_id: string
  verdict: 'pass' | 'maybe' | 'fail'
  rating: number | null
  artifacts: string[]
  note: string
  reviewer: string
  created_at: string
}

export interface BudgetLimits {
  daily_usd: number
  monthly_usd: number
  free_only: boolean
}

export interface Gate {
  allowed: boolean
  reasons: string[]
  planned_usd: number | null
  spent_today_usd?: number
  spent_month_usd?: number
  limits: BudgetLimits
}

export interface SynthesizeRequest {
  provider: string
  text: string
  language: string
  voice: string
  model?: string | null
  response_format?: string | null
  base_url?: string | null
  out_name?: string | null
  dry_run: boolean
}

export interface SynthesizeResponse {
  ok: boolean
  dry_run?: boolean
  plan?: Record<string, unknown>
  run?: Run
  estimate?: Estimate
  budget?: Gate
  error?: string
  reasons?: string[]
}

export interface SecretState {
  present: boolean
  source: 'session' | 'environment' | 'missing'
  hint: string
}

export interface SecretsStatus {
  ok?: boolean
  secrets: Record<string, SecretState>
  session_count: number
}

export interface DatabaseInfo {
  dialect: string
  url: string
  sqlite_path: string | null
}

export interface StorageInfo {
  ok?: boolean
  preferred: string
  active: string
  local: { backend: string; root?: string; bytes_used?: number }
  r2: {
    backend: string
    bucket: string
    endpoint: string
    configured: boolean
    account_id_masked?: string
    access_key_masked?: string
  }
}

export interface SettingsResponse {
  ok: true
  tier_policy: Record<string, string>
  budget: BudgetLimits
  storage: StorageInfo
  database: DatabaseInfo
}

export interface UsageProviderRow {
  provider: string
  tier: string
  calls: number
  characters: number
  audio_seconds: number
  cost_usd: number
}

export interface UsageModelRow {
  provider: string
  model: string
  tier: string
  calls: number
  cost_usd: number
}

export interface UsageResponse {
  ok: true
  window_days: number
  totals: { calls: number; characters: number; audio_seconds: number; cost_usd: number }
  by_provider: UsageProviderRow[]
  by_model: UsageModelRow[]
  budget: BudgetLimits
  spend_today_usd: number
  spend_month_usd: number
  generated_at: string
}
