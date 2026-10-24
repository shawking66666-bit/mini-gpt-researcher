import { afterEach, describe, expect, it, vi } from 'vitest'
import { createHybridResearch, uploadKnowledgeBase } from './api'

afterEach(() => vi.unstubAllGlobals())

describe('research API', () => {
  it('uploads selected files as multipart data', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ knowledge_base_id: 'kb-1', status: 'ready', document_count: 1, chunk_count: 2 }) })
    vi.stubGlobal('fetch', fetch)
    const file = new File(['note'], 'note.md', { type: 'text/markdown' })
    const result = await uploadKnowledgeBase([file])
    expect(result.knowledge_base_id).toBe('kb-1')
    expect(fetch).toHaveBeenCalledOnce()
    expect(fetch.mock.calls[0][0]).toBe('/api/knowledge-bases')
    const body = fetch.mock.calls[0][1].body as FormData
    expect(body.getAll('files')).toEqual([file])
  })

  it('sends the exact hybrid research request', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ task_id: 't-1' }) })
    vi.stubGlobal('fetch', fetch)
    await createHybridResearch('研究主题', 'kb-1')
    expect(fetch.mock.calls[0][0]).toBe('/api/research')
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ topic: '研究主题', retrieval_mode: 'hybrid', knowledge_base_id: 'kb-1' })
  })

  it.each([422, 503])('provides safe feedback for HTTP %i', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status }))
    await expect(createHybridResearch('主题', 'kb-1')).rejects.toThrow(status === 422 ? /检查输入/ : /暂不可用/)
  })

  it('provides safe feedback for network failure', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('private network detail')))
    await expect(uploadKnowledgeBase([new File(['x'], 'a.md')])).rejects.toThrow(/无法连接/)
  })
})
