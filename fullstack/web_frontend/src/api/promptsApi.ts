// src/api/promptsApi.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { http } from './client'
import type { Prompt, PromptCreate, PromptList } from './types'

export function usePrompts(spaceId: string) {
  return useQuery<PromptList>({
    queryKey: ['prompts', spaceId],
    queryFn:  async () =>
      (await http.get<PromptList>(`/spaces/${spaceId}/prompts`)).data,
    enabled: !!spaceId,
  })
}

export function useCreatePrompt(spaceId: string) {
  const qc = useQueryClient()
  return useMutation<Prompt, Error, PromptCreate>({
    mutationFn: async (data) =>
      (await http.post<Prompt>(`/spaces/${spaceId}/prompts`, data)).data,
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['prompts', spaceId] }),
  })
}

export function useDeletePrompt(spaceId: string) {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: async (promptId) => {
      await http.delete(`/spaces/${spaceId}/prompts/${promptId}`)
    },
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['prompts', spaceId] }),
  })
}
