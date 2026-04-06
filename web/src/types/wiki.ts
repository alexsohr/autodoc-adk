export interface WikiStructure {
  scope_path: string;
  sections: WikiSection[];
}

export interface WikiSection {
  title: string;
  description: string;
  subsections?: WikiSection[];
  pages: WikiPageRef[];
}

export interface WikiPageRef {
  page_key: string;
  title: string;
  importance: "critical" | "high" | "medium" | "low";
}

export interface WikiPage {
  page_key: string;
  title: string;
  content: string;
  scope_path: string;
  section_path: string[];
  importance: "critical" | "high" | "medium" | "low";
  quality_score: number | null;
  source_files: string[];
  generated_at: string;
}

export interface Scope {
  scope_path: string;
  title: string;
  description: string;
  page_count: number;
}
