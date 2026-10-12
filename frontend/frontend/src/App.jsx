// src/App.jsx

import { useEffect, useState } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import {
  Bot, Plus, Send, UserRound, FileText, LoaderCircle,
  MessageSquare, PanelRight, X, Copy, Download, Sparkles, LogOut,
} from 'lucide-react'
import './App.css'

const api = axios.create({ baseURL: '' })
const USER_KEY = 'lenny_user'
const CHATS_KEY = 'lenny_chats'

function readStorage(key, fallback) {
  try {
    const value = localStorage.getItem(key)
    return value ? JSON.parse(value) : fallback
  } catch {
    return fallback
  }
}

function getErrorMessage(error, fallback) {
  return error.response?.data?.detail ||
    error.response?.data?.message ||
    error.message ||
    fallback
}

function SourceList({ sources }) {
  if (!sources?.length) return null

  return (
    <div className="source-list">
      <p className="source-heading"><FileText size={14} /> Sources</p>
      <div className="source-items">
        {sources.map((item, index) => {
          const source = typeof item === 'string'
            ? item
            : item.source || item.filename || `Transcript ${index + 1}`
          const chunk = typeof item === 'object' && item.chunk_index !== undefined
            ? ` · chunk ${item.chunk_index}`
            : ''

          return (
            <span className="source-chip" key={`${source}-${index}`}>
              {source}{chunk}
            </span>
          )
        })}
      </div>
    </div>
  )
}

function MessageBubble({ message }) {
  const isAssistant = message.role === 'assistant'

  return (
    <div className={`message-row ${isAssistant ? 'assistant-row' : 'user-row'}`}>
      <div className={`message-avatar ${isAssistant ? 'bot-avatar' : 'user-avatar'}`}>
        {isAssistant ? <Bot size={17} /> : <UserRound size={17} />}
      </div>
      <div className="message-content">
        <div className="message-author">{isAssistant ? 'Lenny Assistant' : 'You'}</div>
        <div className={`message-bubble ${isAssistant ? 'assistant-bubble' : 'user-bubble'}`}>
          {isAssistant ? <ReactMarkdown>{message.content || ''}</ReactMarkdown> : <p>{message.content}</p>}
        </div>
        {isAssistant && message.model && (
          <p className="message-model">Generated with {message.model}</p>
        )}
        {isAssistant && <SourceList sources={message.sources} />}
      </div>
    </div>
  )
}

export default function App() {
  const [user, setUser] = useState(() => readStorage(USER_KEY, null))
  const [chats, setChats] = useState(() => readStorage(CHATS_KEY, []))
  const [activeChat, setActiveChat] = useState(null)
  const [messages, setMessages] = useState([])

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [authMode, setAuthMode] = useState('login')
  const [input, setInput] = useState('')
  const [selectedProvider, setSelectedProvider] = useState('ollama')

  const [initializing, setInitializing] = useState(true)
  const [loading, setLoading] = useState(false)
  const [authLoading, setAuthLoading] = useState(false)
  const [error, setError] = useState('')

  const [showArtifact, setShowArtifact] = useState(false)
  const [essayTopic, setEssayTopic] = useState(
    'How early-stage startups can find product-market fit',
  )
  const [essay, setEssay] = useState(null)
  const [essayLoading, setEssayLoading] = useState(false)
  const [essayError, setEssayError] = useState('')

  useEffect(() => {
    localStorage.setItem(CHATS_KEY, JSON.stringify(chats))
  }, [chats])

  useEffect(() => {
    if (!user) {
      setInitializing(false)
      return
    }

    if (chats.length > 0) {
      setActiveChat((current) => {
        if (current && chats.some((chat) => chat.id === current.id)) {
          return chats.find((chat) => chat.id === current.id)
        }
        return chats[0]
      })
    } else {
      setActiveChat(null)
    }
    setInitializing(false)
  }, [user, chats.length])

  useEffect(() => {
    if (!activeChat?.id) {
      setMessages([])
      return
    }

    let cancelled = false

    async function loadMessages() {
      setError('')
      try {
        const response = await api.get(`/api/chats/${activeChat.id}/messages`)
        if (!cancelled) {
          setMessages(response.data.map((message) => ({
            ...message,
            sources: message.sources || [],
          })))
        }
      } catch (err) {
        if (!cancelled) {
          setError(getErrorMessage(err, 'Could not load this conversation.'))
        }
      }
    }

    loadMessages()
    return () => { cancelled = true }
  }, [activeChat?.id])

  async function handleAuth(event) {
    event.preventDefault()
    const cleanedEmail = email.trim().toLowerCase()

    if (!cleanedEmail || !password) {
      setError('Enter your email address and password.')
      return
    }

    setAuthLoading(true)
    setError('')

    const endpoint = authMode === 'register'
      ? '/api/users/register'
      : '/api/users/login'

    try {
      const response = await api.post(endpoint, {
        email: cleanedEmail,
        password,
      })
      const authenticatedUser = response.data.user

      if (!authenticatedUser?.id) {
        throw new Error('The API response did not include a user ID.')
      }

      setUser(authenticatedUser)
      localStorage.setItem(USER_KEY, JSON.stringify(authenticatedUser))
      setPassword('')

      if (authMode === 'register') {
        setChats([])
        localStorage.setItem(CHATS_KEY, JSON.stringify([]))
        setActiveChat(null)
        setMessages([])
      } else {
        setActiveChat(null)
        setMessages([])
      }
    } catch (err) {
      setError(getErrorMessage(err, 'Authentication failed. Please try again.'))
    } finally {
      setAuthLoading(false)
    }
  }

  async function createChat() {
    if (!user?.id) {
      setError('Log in before starting a chat.')
      return
    }

    setError('')
    try {
      const response = await api.post('/api/chats/', {
        user_id: user.id,
        title: 'New conversation',
      })
      const newChat = response.data
      setChats((current) => [newChat, ...current])
      setActiveChat(newChat)
      setMessages([])
      setInput('')
    } catch (err) {
      setError(getErrorMessage(err, 'Could not create a new conversation.'))
    }
  }

  async function sendMessage(event) {
    event?.preventDefault()
    const question = input.trim()
    if (!question || loading) return

    if (!activeChat?.id) {
      setError('Start a new conversation before sending a message.')
      return
    }

    const optimisticMessage = {
      id: `temporary-${Date.now()}`,
      role: 'user',
      content: question,
    }

    setMessages((current) => [...current, optimisticMessage])
    setInput('')
    setLoading(true)
    setError('')

    try {
      const response = await api.post(
        `/api/chats/${activeChat.id}/messages`,
        { content: question, provider: selectedProvider },
      )
      const result = response.data

      setMessages((current) => {
        const withoutTemporary = current.filter(
          (message) => message.id !== optimisticMessage.id,
        )
        return [
          ...withoutTemporary,
          result.user_message,
          {
            ...result.assistant_message,
            sources: result.sources || [],
            model: result.model || selectedProvider,
          },
        ]
      })

      setChats((current) => current.map((chat) =>
        chat.id === activeChat.id &&
        (!chat.title || chat.title === 'New conversation')
          ? { ...chat, title: question.slice(0, 38) }
          : chat,
      ))
    } catch (err) {
      setMessages((current) => current.filter(
        (message) => message.id !== optimisticMessage.id,
      ))
      setInput(question)
      setError(getErrorMessage(err, 'Could not send your message.'))
    } finally {
      setLoading(false)
    }
  }

  function startNewChat() {
    setError('')
    createChat()
  }

  function signOut() {
    localStorage.removeItem(USER_KEY)
    localStorage.removeItem(CHATS_KEY)
    setUser(null)
    setChats([])
    setActiveChat(null)
    setMessages([])
    setEmail('')
    setPassword('')
    setAuthMode('login')
    setInput('')
    setError('')
    setShowArtifact(false)
    setEssay(null)
    setEssayError('')
  }

  async function generateEssay(event) {
    event.preventDefault()
    if (!essayTopic.trim() || essayLoading) return

    setEssayLoading(true)
    setEssayError('')
    setEssay(null)

    try {
      const response = await api.post('/api/essays/generate', {
        topic: essayTopic.trim(),
        provider: selectedProvider,
      })
      setEssay(response.data)
    } catch (err) {
      console.error('Essay generation failed:', err)
      setEssayError(getErrorMessage(err, 'Could not generate the essay.'))
    } finally {
      setEssayLoading(false)
    }
  }

  async function copyEssay() {
    if (!essay?.content) return
    try {
      await navigator.clipboard.writeText(essay.content)
      setEssayError('')
    } catch (err) {
      console.error('Copy failed:', err)
      setEssayError('Could not copy the essay. Check browser clipboard permissions.')
    }
  }

  function downloadEssay() {
    if (!essay?.content) return
    const blob = new Blob([essay.content], {
      type: 'text/markdown;charset=utf-8',
    })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'ship-30-for-30-essay.md'
    document.body.appendChild(link)
    link.click()
    link.remove()
    URL.revokeObjectURL(url)
  }

  if (initializing) {
    return (
      <div className="loading-screen">
        <LoaderCircle className="spinner" size={28} />
        <p>Loading Lenny Growth Assistant...</p>
      </div>
    )
  }

  if (!user) {
    return (
      <main className="auth-page">
        <form className="auth-card" onSubmit={handleAuth}>
          <div className="brand-mark"><Bot size={25} /></div>
          <p className="eyebrow">LENNY GROWTH ASSISTANT</p>
          <h1>{authMode === 'login' ? 'Welcome back.' : 'Create your account.'}</h1>
          <p className="auth-description">
            {authMode === 'login'
              ? 'Log in to continue exploring product and growth insights.'
              : 'Create an account to start using your growth assistant.'}
          </p>

          <label htmlFor="email">Email address</label>
          <input
            id="email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            required
          />

          <label htmlFor="password">Password</label>
          <input
            id="password"
            type="password"
            autoComplete={authMode === 'login' ? 'current-password' : 'new-password'}
            placeholder={authMode === 'register' ? 'At least 8 characters' : 'Enter your password'}
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            minLength={8}
            maxLength={128}
            required
          />

          {error && <p className="error-message">{error}</p>}

          <button className="primary-button" type="submit" disabled={authLoading}>
            {authLoading
              ? 'Please wait...'
              : authMode === 'login' ? 'Log in' : 'Create account'}
          </button>

          <p className="auth-switch">
            {authMode === 'login' ? "Don't have an account?" : 'Already have an account?'}{' '}
            <button
              type="button"
              onClick={() => {
                setAuthMode((mode) => mode === 'login' ? 'register' : 'login')
                setError('')
              }}
            >
              {authMode === 'login' ? 'Sign up' : 'Log in'}
            </button>
          </p>

          <p className="auth-note">
            Passwords are verified by the backend and should never be stored in plain text.
          </p>
        </form>
      </main>
    )
  }

  return (
    <main className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-brand">
          <div className="brand-mark small-brand"><Bot size={20} /></div>
          <div><h1>Lenny AI</h1><p>Growth Assistant</p></div>
        </div>

        <button className="new-chat-button" onClick={startNewChat} disabled={loading}>
          <Plus size={17} /> New conversation
        </button>

        <div className="sidebar-section-title">YOUR CONVERSATIONS</div>
        <div className="chat-history">
          {chats.length === 0 ? (
            <p className="empty-history">No conversations yet. Start a new one.</p>
          ) : (
            chats.map((chat) => (
              <button
                key={chat.id}
                className={`history-item ${activeChat?.id === chat.id ? 'active' : ''}`}
                onClick={() => {
                  setActiveChat(chat)
                  setError('')
                }}
              >
                <MessageSquare size={16} />
                <span>{chat.title || 'New conversation'}</span>
              </button>
            ))
          )}
        </div>

        <div className="sidebar-bottom">
          <div className="user-card">
            <div className="user-avatar"><UserRound size={17} /></div>
            <div className="user-details">
              <strong>{user.email || 'User'}</strong>
              <span>Personal workspace</span>
            </div>
          </div>
          <button className="sign-out-button" onClick={signOut}>
            <LogOut size={15} /> Sign out
          </button>
        </div>
      </aside>

      <div className="workspace">
        <section className="chat-panel">
          <header className="chat-header">
            <div className="chat-heading">
              <h2>{activeChat?.title || 'New conversation'}</h2>
              <p>Answers grounded in Lenny's podcast transcripts</p>
            </div>

            <div className="header-actions">
              <label className="provider-control">
                <span>Model</span>
                <select
                  value={selectedProvider}
                  onChange={(event) => setSelectedProvider(event.target.value)}
                  disabled={loading || essayLoading}
                  aria-label="Choose language model"
                >
                  <option value="ollama">Local · Ollama</option>
                  <option value="openrouter">Cloud · OpenRouter</option>
                </select>
              </label>
              <button
                className="essay-open-button"
                onClick={() => setShowArtifact((current) => !current)}
              >
                <PanelRight size={15} />
                {showArtifact ? 'Hide essay' : 'Create essay'}
              </button>
            </div>
          </header>

          <div className="messages-area">
            {!activeChat ? (
              <div className="welcome-state">
                <div className="welcome-icon"><Sparkles size={25} /></div>
                <h2>What are you trying to grow?</h2>
                <p>Ask about product strategy, user research, retention, onboarding, pricing, or startup growth.</p>
                <button className="primary-button" onClick={startNewChat}>
                  <Plus size={16} /> Start a conversation
                </button>
              </div>
            ) : messages.length === 0 && !loading ? (
              <div className="welcome-state">
                <div className="welcome-icon"><Bot size={26} /></div>
                <h2>Let's solve a growth problem.</h2>
                <p>Ask a question. The assistant will search relevant transcript passages and include source references when available.</p>
                <div className="suggestion-list">
                  {[
                    'How can an early-stage startup find product-market fit?',
                    'What are practical ways to improve user retention?',
                    'How should a startup improve onboarding?',
                  ].map((suggestion) => (
                    <button key={suggestion} onClick={() => setInput(suggestion)}>
                      {suggestion}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              <div className="message-list">
                {messages.map((message, index) => (
                  <MessageBubble
                    key={message.id ?? `${message.role}-${index}`}
                    message={message}
                  />
                ))}
                {loading && (
                  <div className="thinking-indicator">
                    <LoaderCircle size={17} className="spinner" />
                    <span>Searching transcripts and preparing an answer...</span>
                  </div>
                )}
              </div>
            )}
          </div>

          {error && (
            <div className="inline-error">
              <span>{error}</span>
              <button onClick={() => setError('')} aria-label="Dismiss error">
                <X size={15} />
              </button>
            </div>
          )}

          <form className="composer" onSubmit={sendMessage}>
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={activeChat ? 'Ask Lenny about product and growth...' : 'Start a new conversation to ask a question...'}
              rows={2}
              maxLength={10000}
              disabled={!activeChat || loading}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                  event.preventDefault()
                  sendMessage()
                }
              }}
            />
            <div className="composer-footer">
              <span>Enter to send · Shift + Enter for a new line</span>
              <button
                className="send-button"
                type="submit"
                disabled={!activeChat || !input.trim() || loading}
                aria-label="Send message"
              >
                {loading ? <LoaderCircle size={17} className="spinner" /> : <Send size={17} />}
              </button>
            </div>
          </form>

          
        </section>

        {showArtifact && (
          <aside className="artifact-panel">
            <header className="artifact-header">
              <div>
                <div className="artifact-title-row"><FileText size={18} /><h2>Artifact Viewer</h2></div>
                <p>Ship 30 for 30 essay</p>
              </div>
              <button className="icon-button" onClick={() => setShowArtifact(false)} aria-label="Close Artifact Viewer">
                <X size={18} />
              </button>
            </header>

            <form className="essay-form" onSubmit={generateEssay}>
              <label htmlFor="essay-topic">Essay topic</label>
              <input
                id="essay-topic"
                value={essayTopic}
                onChange={(event) => setEssayTopic(event.target.value)}
                maxLength={300}
                minLength={3}
                required
              />
              <button className="primary-button" type="submit" disabled={essayLoading || !essayTopic.trim()}>
                {essayLoading ? (
                  <><LoaderCircle size={16} className="spinner" /> Generating essay...</>
                ) : (
                  <><Sparkles size={16} /> Generate essay</>
                )}
              </button>
            </form>

            {essayError && <p className="error-message">{essayError}</p>}

            {essayLoading && (
              <p className="artifact-status">
                <LoaderCircle size={16} className="spinner" />
                Writing from retrieved podcast transcripts. This may take a little while.
              </p>
            )}

            {!essay && !essayLoading && (
              <div className="artifact-empty">
                <FileText size={27} />
                <h3>Your essay will appear here</h3>
                <p>Generate a Markdown essay grounded in the transcript knowledge base. You can review, copy, or download it.</p>
              </div>
            )}

            {essay && (
              <>
                <div className="artifact-actions">
                  <button type="button" onClick={copyEssay}><Copy size={14} /> Copy Markdown</button>
                  <button type="button" onClick={downloadEssay}><Download size={14} /> Download .md</button>
                </div>
                <article className="essay-document">
                  <h1>{essay.title}</h1>
                  <ReactMarkdown>{essay.content}</ReactMarkdown>
                </article>
                <div className="artifact-sources">
                  <h3>Retrieved transcript files</h3>
                  <SourceList sources={essay.sources || []} />
                  <p className="model-used">Generated with: {essay.model || selectedProvider}</p>
                </div>
              </>
            )}
          </aside>
        )}
      </div>
    </main>
  )
}
