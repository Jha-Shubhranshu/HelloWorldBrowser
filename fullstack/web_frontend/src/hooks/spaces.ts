// src/api/spacesApi.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { http } from '../api/client'
import type { Space, SpaceCreate, SpaceList, SpaceUpdate } from '../api/types'

const SPACES_KEY = ['spaces']

export function useSpaces() {
  return useQuery<SpaceList>({
    queryKey: SPACES_KEY,
    queryFn:  async () => (await http.get<SpaceList>('/spaces')).data,
  })
}

export function useSpace(id: string) {
  return useQuery<Space>({
    queryKey: ['spaces', id],
    queryFn:  async () => (await http.get<Space>(`/spaces/${id}`)).data,
    enabled:  !!id,
  })
}

export function useCreateSpace() {
  const qc = useQueryClient()
  return useMutation<Space, Error, SpaceCreate>({
    mutationFn: async (data) => (await http.post<Space>('/spaces', data)).data,
    onSuccess:  () => qc.invalidateQueries({ queryKey: SPACES_KEY }),
  })
}

export function useUpdateSpace(id: string) {
  const qc = useQueryClient()
  return useMutation<Space, Error, SpaceUpdate>({
    mutationFn: async (data) => (await http.patch<Space>(`/spaces/${id}`, data)).data,
    onSuccess:  () => {
      qc.invalidateQueries({ queryKey: SPACES_KEY })
      qc.invalidateQueries({ queryKey: ['spaces', id] })
    },
  })
}

export function useDeleteSpace() {
  const qc = useQueryClient()
  return useMutation<void, Error, string>({
    mutationFn: async (id) => { await http.delete(`/spaces/${id}`) },
    onSuccess:  () => qc.invalidateQueries({ queryKey: SPACES_KEY }),
  })
}