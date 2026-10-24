export type KnowledgeBaseSummary = {
  knowledge_base_id: string
  document_count: number
  chunk_count: number
  status: string
}

export type ResearchQuestion = { id: string; text: string; round_number: number }
export type ResearchPlan = { topic: string; questions: ResearchQuestion[] }
export type Evidence = {
  source_id: string
  question_id: string
  title: string
  source_type: 'web' | 'document'
  url: string | null
  document_name: string | null
  page_number: number | null
  chunk_index: number | null
  content: string
}
export type ResearchReport = {
  title: string
  markdown: string
  html: string | null
  used_source_ids: string[]
}
export type Usage = {
  llm_requests: number
  search_requests: number
  input_tokens: number
  output_tokens: number
  tavily_credits: number
  estimated_cost_usd: number
}
export type ResearchState = {
  task_id: string
  topic: string
  status: 'pending' | 'planning' | 'researching' | 'reflecting' | 'reporting' | 'completed' | 'failed'
  retrieval_mode: 'web' | 'document' | 'hybrid'
  knowledge_base_id: string | null
  created_at: string
  round_number: number
  plan: ResearchPlan | null
  evidence: Evidence[]
  errors: string[]
  usage: Usage
  report: ResearchReport | null
}
