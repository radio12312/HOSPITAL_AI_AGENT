import { AlertTriangle, Bot, RotateCw, SendHorizontal, Trash2, User } from 'lucide-react'
import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { queryAgent } from '../api/agent'
import { AgentRunView } from '../components/AgentRunView'
import { Button } from '../components/Button'
import { useAuth } from '../context/authContext'
import { useElapsed } from '../hooks/useElapsed'
import type { AgentQueryResponse, Role } from '../types'
import { SUGGESTED_QUESTIONS } from '../utils/constants'
import { getErrorMessage } from '../utils/errors'
import { inputClass } from '../utils/styles'

type ChatMessage =
  | { id: number; kind: 'user'; text: string }
  | { id: number; kind: 'assistant'; run: AgentQueryResponse }
  | { id: number; kind: 'error'; text: string; query: string }

const ROLE_SCOPE: Record<Role, string> = {
  admin: 'You can reach all five agents: scheduling, resource, staff, emergency and analytics.',
  doctor: 'Your questions are routed to the scheduling and analytics agents.',
  staff_coordinator: 'Your questions are routed to the staff and analytics agents.',
}

function TypingIndicator({ seconds }: { seconds: number }) {
  return (
    <div className="flex items-start gap-3" role="status" aria-live="polite">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-700 text-white">
        <Bot size={16} aria-hidden="true" />
      </span>
      <div className="rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm">
        <div className="flex items-center gap-1" aria-hidden="true">
          <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.3s]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400 [animation-delay:-0.15s]" />
          <span className="h-2 w-2 animate-bounce rounded-full bg-slate-400" />
        </div>
        <p className="mt-1.5 text-xs text-slate-500">
          Agents are working on it… {seconds}s <span className="sr-only">elapsed</span>
        </p>
      </div>
    </div>
  )
}

export function AssistantPage() {
  const { user } = useAuth()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [pending, setPending] = useState(false)
  const nextId = useRef(1)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const elapsed = useElapsed(pending)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages, pending])

  // Return focus to the input once a reply arrives (the textarea is disabled while pending).
  const hasMessages = messages.length > 0
  useEffect(() => {
    if (!pending && hasMessages) inputRef.current?.focus()
  }, [pending, hasMessages])

  async function ask(question: string) {
    const q = question.trim()
    if (!q || pending) return
    setInput('')
    setMessages((m) => [...m, { id: nextId.current++, kind: 'user', text: q }])
    setPending(true)
    try {
      const run = await queryAgent({ query: q })
      setMessages((m) => [...m, { id: nextId.current++, kind: 'assistant', run }])
    } catch (err) {
      setMessages((m) => [...m, { id: nextId.current++, kind: 'error', text: getErrorMessage(err), query: q }])
    } finally {
      setPending(false)
    }
  }

  function retry(msgId: number, query: string) {
    setMessages((m) => m.filter((x) => x.id !== msgId && !(x.kind === 'user' && x.id === msgId - 1)))
    void ask(query)
  }

  function replaceRun(msgId: number, run: AgentQueryResponse) {
    setMessages((m) => m.map((x) => (x.id === msgId && x.kind === 'assistant' ? { ...x, run } : x)))
  }

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    void ask(input)
  }

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      void ask(input)
    }
  }

  return (
    <div className="flex min-h-[calc(100vh-12rem)] flex-col rounded-xl border border-slate-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Ask the hospital agents</h2>
          {user && <p className="mt-0.5 text-xs text-slate-500">{ROLE_SCOPE[user.role]}</p>}
        </div>
        {messages.length > 0 && (
          <Button variant="ghost" size="sm" icon={Trash2} disabled={pending} onClick={() => setMessages([])}>
            Clear chat
          </Button>
        )}
      </div>

      <div className="flex-1 space-y-6 overflow-y-auto bg-slate-50/50 px-4 py-6 sm:px-6" aria-live="polite" aria-relevant="additions">
        {messages.length === 0 && !pending && (
          <div className="flex flex-col items-center py-8 text-center">
            <span className="mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-teal-50 text-teal-700">
              <Bot size={24} aria-hidden="true" />
            </span>
            <p className="text-sm font-medium text-slate-900">How can I help with hospital operations today?</p>
            <p className="mt-1 max-w-md text-sm text-slate-500">
              Ask about beds, staffing, demand or delays. Answers can take 5–20 seconds while agents analyse live data.
            </p>
          </div>
        )}

        {messages.map((msg) => {
          if (msg.kind === 'user') {
            return (
              <div key={msg.id} className="flex items-start justify-end gap-3">
                <div className="max-w-[85%] rounded-2xl rounded-tr-sm bg-teal-700 px-4 py-2.5 text-sm whitespace-pre-wrap text-white shadow-sm">
                  {msg.text}
                </div>
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-slate-200 text-slate-600">
                  <User size={16} aria-hidden="true" />
                  <span className="sr-only">You</span>
                </span>
              </div>
            )
          }
          if (msg.kind === 'error') {
            return (
              <div key={msg.id} className="flex items-start gap-3">
                <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-red-100 text-red-600">
                  <AlertTriangle size={16} aria-hidden="true" />
                </span>
                <div role="alert" className="max-w-[85%] rounded-2xl rounded-tl-sm border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
                  <p>The assistant could not answer: {msg.text}</p>
                  <Button
                    variant="secondary"
                    size="sm"
                    icon={RotateCw}
                    className="mt-2"
                    disabled={pending}
                    onClick={() => retry(msg.id, msg.query)}
                  >
                    Retry
                  </Button>
                </div>
              </div>
            )
          }
          return (
            <div key={msg.id} className="flex items-start gap-3">
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-teal-700 text-white">
                <Bot size={16} aria-hidden="true" />
                <span className="sr-only">Assistant</span>
              </span>
              <div className="min-w-0 max-w-[90%] flex-1 rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-4 shadow-sm">
                <AgentRunView run={msg.run} onRunUpdate={(run) => replaceRun(msg.id, run)} />
              </div>
            </div>
          )
        })}

        {pending && <TypingIndicator seconds={elapsed} />}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-slate-100 p-4">
        <div className="mb-3 flex flex-wrap gap-2" aria-label="Suggested questions">
          {SUGGESTED_QUESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              disabled={pending}
              onClick={() => void ask(q)}
              className="cursor-pointer rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-700 transition-colors hover:border-teal-700 hover:bg-teal-50 hover:text-teal-800 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {q}
            </button>
          ))}
        </div>
        <form onSubmit={handleSubmit} className="flex items-end gap-2">
          <label htmlFor="assistant-input" className="sr-only">
            Ask a question
          </label>
          <textarea
            id="assistant-input"
            ref={inputRef}
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about beds, staff, demand… (Enter to send, Shift+Enter for a new line)"
            className={`${inputClass} max-h-40 min-h-10 resize-y`}
            disabled={pending}
          />
          <Button type="submit" icon={SendHorizontal} loading={pending} disabled={!input.trim()} aria-label="Send question">
            <span className="hidden sm:inline">Send</span>
          </Button>
        </form>
      </div>
    </div>
  )
}
