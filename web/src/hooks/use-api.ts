import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, queryKeys } from '@/lib/api'
import type {
  BudgetLimits,
  Contribution,
  Review,
  SynthesizeRequest,
  SynthesizeResponse,
} from '@/lib/types'

/** API health: service, database, storage, frontend build flag. */
export function useHealthQuery() {
  return useQuery({ queryKey: queryKeys.health, queryFn: api.health })
}

/** Provider list for the studio. */
export function useProvidersQuery() {
  return useQuery({ queryKey: queryKeys.providers, queryFn: api.providers })
}

/** Live model/voice/format catalogs for the given providers. */
export function useCatalogsQueries(names: string[]) {
  return useQueries({
    queries: names.map((name) => ({
      queryKey: queryKeys.catalog(name),
      queryFn: () => api.catalog(name),
      enabled: names.length > 0,
    })),
  })
}

export function useRunsQuery() {
  return useQuery({ queryKey: queryKeys.runs, queryFn: api.runs })
}

export function useRecordingsQuery() {
  return useQuery({ queryKey: queryKeys.recordings, queryFn: api.recordings })
}

/** Synthesis request; invalidates the runs list on success. */
export function useSynthesizeMutation(handlers?: {
  onSuccess?: (response: SynthesizeResponse) => void | Promise<void>
  onError?: (error: Error) => void
}) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: SynthesizeRequest) => api.synthesize(payload),
    onSuccess: async (response) => {
      await handlers?.onSuccess?.(response)
      await queryClient.invalidateQueries({ queryKey: queryKeys.runs })
    },
    onError: (error: Error) => handlers?.onError?.(error),
  })
}

/** Recording upload; invalidates the recordings list on success. */
export function useUploadRecordingMutation(handlers?: {
  onSuccess?: () => void | Promise<void>
  onError?: (error: Error) => void
}) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (form: FormData) => api.uploadRecording(form),
    onSuccess: async () => {
      await handlers?.onSuccess?.()
      await queryClient.invalidateQueries({ queryKey: queryKeys.recordings })
    },
    onError: (error: Error) => handlers?.onError?.(error),
  })
}

/** Studio metadata (languages, models, voices, limits, storage, counts). */
export function useMetaQuery() {
  return useQuery({ queryKey: queryKeys.meta, queryFn: api.meta })
}

/** Session key presence. Values never reach the browser state. */
export function useSecretsQuery() {
  return useQuery({ queryKey: queryKeys.secrets, queryFn: api.secrets })
}

export function useSetSecretsMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (values: Record<string, string>) => api.setSecrets(values),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.secrets }),
  })
}

export function useClearSecretMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (name: string) => api.clearSecret(name),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.secrets }),
  })
}

export function useSettingsQuery() {
  return useQuery({ queryKey: queryKeys.settings, queryFn: api.settings })
}

export interface SettingsPatch {
  tier_policy?: Record<string, string>
  budget?: Partial<BudgetLimits>
  storage?: { preferred: 'local' | 'r2' | 'auto' }
}

export function useSaveSettingsMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (patch: SettingsPatch) => api.saveSettings(patch),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.settings }),
        queryClient.invalidateQueries({ queryKey: queryKeys.providers }),
        queryClient.invalidateQueries({ queryKey: ['catalog'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.usage }),
      ])
    },
  })
}

export function useUsageQuery(days = 30) {
  return useQuery({ queryKey: [...queryKeys.usage, days], queryFn: () => api.usage(days) })
}

export function useRefreshCatalogsMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (providers?: string[]) => api.refreshCatalogs(providers),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['catalog'] }),
        queryClient.invalidateQueries({ queryKey: queryKeys.meta }),
        queryClient.invalidateQueries({ queryKey: queryKeys.providers }),
      ])
    },
  })
}

/** Sound-check verdicts. */
export function useReviewsQuery(runId?: string) {
  return useQuery({
    queryKey: runId ? [...queryKeys.reviews, runId] : queryKeys.reviews,
    queryFn: () => api.reviews(runId),
  })
}

export interface ReviewPayload {
  run_id: string
  verdict: Review['verdict']
  rating?: number
  artifacts?: string[]
  note?: string
  reviewer?: string
}

export function useAddReviewMutation(handlers?: { onSuccess?: () => void }) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: ReviewPayload) => api.review(payload),
    onSuccess: async () => {
      handlers?.onSuccess?.()
      await queryClient.invalidateQueries({ queryKey: queryKeys.reviews })
    },
  })
}

/** Voice contributions. */
export function useContributionsQuery(status = '') {
  return useQuery({
    queryKey: status ? [...queryKeys.contributions, status] : queryKeys.contributions,
    queryFn: () => api.contributions(status),
  })
}

export function useContributeMutation(handlers?: { onSuccess?: (row: Contribution) => void }) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (form: FormData) => api.contribute(form),
    onSuccess: async (data) => {
      handlers?.onSuccess?.(data.contribution)
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.contributions }),
        queryClient.invalidateQueries({ queryKey: queryKeys.recordings }),
        queryClient.invalidateQueries({ queryKey: queryKeys.meta }),
      ])
    },
  })
}

export function useSetContributionStatusMutation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: string }) =>
      api.setContributionStatus(id, status),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: queryKeys.contributions }),
        queryClient.invalidateQueries({ queryKey: queryKeys.meta }),
      ])
    },
  })
}
