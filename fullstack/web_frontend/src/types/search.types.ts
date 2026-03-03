// src/api/types.ts

export interface MetadataFilters {
  channel_name?:          string
  channel_name_in?:       string[]
  transcript_language?:   string
  video_upload_date_gte?: string
  video_upload_date_lte?: string
}

export interface SearchRequest {
  query:         string
  filters:       MetadataFilters
  top_k:         number
  use_llm:       boolean
  llm_question?: string
}

export interface VideoResult {
  video_url:            string
  video_title:          string
  channel_name:         string
  video_thumbnail_url:  string
  video_upload_date:    string
  video_length:         string
  score:                number
  snippet:              string
  channel_joining_date: string
  transcript_language:  string
}

export interface SearchResponse {
  query:         string
  results:       VideoResult[]
  llm_answer:    string | null
  total_matches: number
}