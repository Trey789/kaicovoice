import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'
import vm from 'node:vm'

const html = readFileSync(new URL('../start-project.html', import.meta.url), 'utf8')
function form({ search = '', stored } = {}) {
  const storage = new Map(stored ? [['kv-start-project-v1', JSON.stringify(stored)]] : [])
  const element = { addEventListener() {}, value: '' }
  const context = vm.createContext({ URLSearchParams, Date, location: { search },
    document: { getElementById: () => element }, window: { addEventListener() {} },
    localStorage: { getItem: k => storage.get(k) ?? null, setItem: (k, v) => storage.set(k, v), removeItem: k => storage.delete(k) },
  })
  const script = html.match(/<script>([\s\S]*?)<\/script>/)[1]
  vm.runInContext(script.replace('\n  load();', '\n  globalThis.fixtureForm = { payload, state, load, save }; return;\n  load();'), context)
  return { api: context.fixtureForm, context, storage }
}

test('website answers remain structured and the CRM summary stays compatible', () => {
  const { api } = form()
  Object.assign(api.state.a, { name: 'Fixture', business: 'Fictional Plumbing', phone: '9185550123', email: 'fixture@example.test', trade: 'Plumbing', areas: 'Tulsa', services: 'Drain cleaning', pages: ['Home', 'Contact'] })
  api.state.id = 'fixture-submission-0001'
  const payload = JSON.parse(JSON.stringify(api.payload()))
  assert.equal(payload.website_project.schema, 'kaico.website-project/1')
  assert.deepEqual(payload.website_project.answers.pages, ['Home', 'Contact'])
  assert.equal(payload.website_project.answers.areas, 'Tulsa')
  assert.match(payload.problem, /Drain cleaning/)
  assert.equal(payload.source, 'website_project_form')
})

test('invitation is sent in the request body and does not reuse an unrelated public draft', () => {
  const { api } = form({ search: '?invite=fixture-private-invitation-0001', stored: { step: 2, a: { business: 'Different client' }, id: 'old' } })
  assert.equal(api.payload().website_invitation, 'fixture-private-invitation-0001')
  api.load()
  assert.equal(api.state.a.business, undefined)
})

test('expired device drafts are removed', () => {
  const { api, storage } = form({ stored: { step: 1, a: { business: 'Expired client' }, savedAt: Date.now() - 31 * 86400000 } })
  api.load()
  assert.equal(storage.has('kv-start-project-v1'), false)
})
