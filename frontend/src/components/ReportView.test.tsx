import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import ReportView from './ReportView'
import { reportDownload } from '../reportDownload'
import type { ResearchState } from '../types'

const state: ResearchState = {
  task_id: 'task-1', topic: '研究主题', status: 'completed', retrieval_mode: 'hybrid', knowledge_base_id: 'kb-1', created_at: '2026-10-24T00:00:00', round_number: 2,
  plan: { topic: '研究主题', questions: [{ id: 'Q1', text: '市场需求是什么？', round_number: 1 }] },
  evidence: [
    { source_id: 'S1', question_id: 'Q1', title: '网页标题', source_type: 'web', url: 'https://example.com/article', document_name: null, page_number: null, chunk_index: null, content: '网页证据' },
    { source_id: 'S2', question_id: 'Q1', title: '产品资料', source_type: 'document', url: null, document_name: 'brief.pdf', page_number: 3, chunk_index: 2, content: '文档证据' },
  ],
  report: { title: '研究报告', markdown: '# 研究报告\n正文 [S1] [S2]', html: '<h1>研究报告</h1>', used_source_ids: ['S1', 'S2'] },
  errors: [], usage: { llm_requests: 3, search_requests: 4, input_tokens: 20, output_tokens: 10, tavily_credits: 4, estimated_cost_usd: 0.01 },
}

afterEach(cleanup)

describe('sourced report', () => {
  it('shows markdown report and can switch to plan and sources', () => {
    render(<ReportView state={state} />)
    expect(screen.getByRole('heading', { name: '研究报告' })).toBeInTheDocument()
    expect(screen.getByText(/正文/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: '研究计划' }))
    expect(screen.getByText('市场需求是什么？')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('tab', { name: '来源' }))
    expect(screen.getByRole('link', { name: /网页标题/ })).toHaveAttribute('href', 'https://example.com/article')
    expect(screen.getByText(/brief.pdf/)).toBeInTheDocument()
    expect(screen.getByText(/第 3 页/)).toBeInTheDocument()
  })

  it('downloads exactly the returned Markdown and HTML', async () => {
    expect(await reportDownload(state.report!, 'markdown').blob.text()).toBe(state.report!.markdown)
    expect(await reportDownload(state.report!, 'html').blob.text()).toBe(state.report!.html)
    expect(reportDownload(state.report!, 'markdown').filename).toBe('task-report.md')
  })

  it('never executes raw HTML embedded in model markdown', () => {
    const attack = { ...state, report: { ...state.report!, markdown: 'Safe <img src=x onerror="alert(1)"> <script>alert(1)</script>' } }
    render(<ReportView state={attack} />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(document.querySelector('script')).toBeNull()
  })

  it('does not invent a report if it is missing', () => {
    render(<ReportView state={{ ...state, report: null }} />)
    expect(screen.getByText(/没有可展示的报告/)).toBeInTheDocument()
  })

  it('does not turn untrusted evidence URL into a clickable link', () => {
    render(<ReportView state={{ ...state, evidence: [{ ...state.evidence[0], url: 'javascript:alert(1)' }] }} />)
    fireEvent.click(screen.getByRole('tab', { name: '来源' }))
    expect(screen.queryByRole('link', { name: /网页标题/ })).not.toBeInTheDocument()
  })
})
