// src/api/types.ts

// ── Search ────────────────────────────────────────────────────────────────────

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

// ── Spaces ────────────────────────────────────────────────────────────────────

export interface Space {
  id:          string
  user_id:     string
  title:       string
  description: string
  created_at:  string
  updated_at:  string
}

export interface SpaceCreate {
  title:       string
  description: string
}

export interface SpaceUpdate {
  title?:       string
  description?: string
}

export interface SpaceList {
  spaces: Space[]
  total:  number
}

// ── Prompts ───────────────────────────────────────────────────────────────────

export interface Prompt {
  id:         string
  space_id:   string
  query_text: string
  results:    SearchResponse | null
  created_at: string
}

export interface PromptCreate {
  query_text: string
  top_k:      number
}

export interface PromptList {
  prompts: Prompt[]
  total:   number
}
