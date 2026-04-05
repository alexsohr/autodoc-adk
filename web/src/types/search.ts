export interface SearchResult {
  page_key: string;
  title: string;
  scope_path?: string;
  best_chunk_heading_path?: string[];
  score: number;
  snippet: string;
  best_chunk_content?: string;
}

export interface SearchResponse {
  results: SearchResult[];
  total: number;
  search_type: string;
}
