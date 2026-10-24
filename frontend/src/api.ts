import type { KnowledgeBaseSummary, ResearchState } from './types'

function messageForStatus(status: number): string {
  if (status === 422) return '请求未通过校验，请检查输入的研究主题、文件和资料状态后重试。'
  if (status === 503) return '服务暂不可用，请检查后端及外部服务后重试。'
  return `请求失败（HTTP ${status}），请稍后重试。`
}

async function requestJson<T>(url: string, init: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(url, init)
  } catch {
    throw new Error('无法连接到本地服务，请确认 FastAPI 已启动。')
  }
  if (!response.ok) throw new Error(messageForStatus(response.status))
  try {
    return await response.json() as T
  } catch {
    throw new Error('服务返回了无法读取的数据，请稍后重试。')
  }
}

export async function uploadKnowledgeBase(files: File[]): Promise<KnowledgeBaseSummary> {
  const body = new FormData()
  files.forEach((file) => body.append('files', file))
  // 浏览器为 FormData 自行设置 multipart boundary，不能手写 Content-Type。
  return requestJson('/api/knowledge-bases', { method: 'POST', body })
}

export async function createHybridResearch(topic: string, knowledgeBaseId: string): Promise<ResearchState> {
  return requestJson('/api/research', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ topic, retrieval_mode: 'hybrid', knowledge_base_id: knowledgeBaseId }),
  })
}
