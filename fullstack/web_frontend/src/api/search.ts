// src/api/searchApi.ts
import axios from 'axios'
import { useMutation } from '@tanstack/react-query'
import type { SearchRequest, SearchResponse } from './types'

const client = axios.create({
  baseURL: '/search',          // proxied to http://127.0.0.1:8000 by Vite
  headers: { 'Content-Type': 'application/json' },
  withCredentials: true,       // HTTPOnly cookies ready for when auth is added
})

export async function postSearch(req: SearchRequest): Promise<SearchResponse> {
  const { data } = await client.post<SearchResponse>('', req)
  return data
}

export function useSearch() {
  return useMutation<SearchResponse, Error, SearchRequest>({
    mutationFn: postSearch,
  })
}