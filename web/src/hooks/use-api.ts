import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, queryKeys } from '@/lib/api'
import type { SynthesizeRequest, SynthesizeResponse } from '@/lib/types'

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
