import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { createHybridResearch, uploadKnowledgeBase } from './api'
import type { ResearchState } from './types'

vi.mock('./api', () => ({ uploadKnowledgeBase: vi.fn(), createHybridResearch: vi.fn() }))

const upload = vi.mocked(uploadKnowledgeBase)
const research = vi.mocked(createHybridResearch)
afterEach(cleanup)
const ready = { knowledge_base_id: 'kb-1', status: 'ready', document_count: 1, chunk_count: 2 }
const completed = { task_id: 'task-1', topic: '研究主题', status: 'completed', report: { title: '报告标题', markdown: '# 报告标题', html: '<h1>报告标题</h1>', used_source_ids: [] }, plan: null, evidence: [], errors: [], usage: { llm_requests: 1, search_requests: 1, input_tokens: 2, output_tokens: 3, tavily_credits: 1, estimated_cost_usd: 0 }, round_number: 1, created_at: '2026-10-24T00:00:00', retrieval_mode: 'hybrid', knowledge_base_id: 'kb-1' } as ResearchState

function fill(topic = '研究主题', files: File[] = [new File(['hello'], 'note.md')]) {
  fireEvent.change(screen.getByLabelText('研究主题'), { target: { value: topic } })
  fireEvent.change(screen.getByLabelText('参考资料'), { target: { files } })
  fireEvent.click(screen.getByRole('button', { name: '开始混合研究' }))
}

beforeEach(() => {
  vi.clearAllMocks()
  upload.mockResolvedValue(ready)
  research.mockResolvedValue(completed)
})

describe('hybrid research form', () => {
  it('rejects blank topic before upload', () => {
    render(<App />)
    fill('   ')
    expect(screen.getByRole('alert')).toHaveTextContent(/研究主题/)
    expect(upload).not.toHaveBeenCalled()
  })

  it('rejects absent, unsupported and oversized files', () => {
    render(<App />)
    fill('研究主题', [])
    expect(screen.getByRole('alert')).toHaveTextContent(/至少选择/)
    fill('研究主题', [new File(['x'], 'bad.txt')])
    expect(screen.getByRole('alert')).toHaveTextContent(/PDF|Markdown/)
    fill('研究主题', [new File([new Uint8Array(10 * 1024 * 1024 + 1)], 'big.pdf')])
    expect(screen.getByRole('alert')).toHaveTextContent(/10 MiB/)
    expect(upload).not.toHaveBeenCalled()
  })

  it('rejects more than five files and more than 30 MiB total', () => {
    render(<App />)
    fill('研究主题', Array.from({ length: 6 }, (_, n) => new File(['x'], `${n}.md`)))
    expect(screen.getByRole('alert')).toHaveTextContent(/5/)
    fill('研究主题', Array.from({ length: 4 }, (_, n) => new File([new Uint8Array(8 * 1024 * 1024)], `${n}.md`)))
    expect(screen.getByRole('alert')).toHaveTextContent(/30 MiB/)
  })

  it('uploads once then researches once and does not accept duplicate clicks', async () => {
    let resolveUpload!: (value: typeof ready) => void
    upload.mockReturnValue(new Promise((resolve) => { resolveUpload = resolve }))
    render(<App />)
    fill()
    fireEvent.click(screen.getByRole('button', { name: /正在上传资料/ }))
    expect(upload).toHaveBeenCalledOnce()
    expect(research).not.toHaveBeenCalled()
    resolveUpload(ready)
    await waitFor(() => expect(research).toHaveBeenCalledWith('研究主题', 'kb-1'))
    await waitFor(() => expect(screen.getByText('报告标题')).toBeInTheDocument())
    expect(research).toHaveBeenCalledOnce()
  })

  it('stops if upload fails or knowledge base is not ready', async () => {
    upload.mockRejectedValueOnce(new Error('上传失败，请重试。'))
    render(<App />)
    fill()
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/上传失败/))
    expect(research).not.toHaveBeenCalled()
    upload.mockResolvedValueOnce({ ...ready, status: 'pending' })
    fill()
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/未就绪/))
    expect(research).not.toHaveBeenCalled()
  })

  it('shows research errors and failed task status as errors', async () => {
    research.mockRejectedValueOnce(new Error('服务暂不可用'))
    render(<App />)
    fill()
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/暂不可用/))
    research.mockResolvedValueOnce({ ...completed, status: 'failed', report: null })
    fill()
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent(/研究失败/))
    expect(screen.queryByText('报告标题')).not.toBeInTheDocument()
  })
})
