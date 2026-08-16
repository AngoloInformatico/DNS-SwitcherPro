import { FormEvent, useCallback, useEffect, useRef, useState } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import { Activity, AlertTriangle, Check, CheckCircle2, ChevronRight, CircleStop, Copy, Database, ExternalLink, Eye, EyeOff, Globe2, KeyRound, Loader2, LockKeyhole, LogOut, Network, Play, RefreshCw, RotateCcw, Save, Settings2, ShieldCheck, Terminal, Trash2, Wifi, X, Zap } from 'lucide-react'

type Mode = 'pihole' | 'standard' | 'unknown'
type Theme = 'light' | 'dark' | 'system'
type View = 'dashboard' | 'settings' | 'password'
type AuthView = 'checking' | 'login' | 'setup' | 'authenticated' | 'invalid-link'
type AuthStatus = { password_configured: boolean; authenticated: boolean }
type Settings = { router_ip: string; router_port: number; router_protocol: 'http'|'https'; router_timeout: number; apply_timeout: number; pihole_ip: string; standard_dns_ip: string; refresh_mode: 'quick'|'full'; theme: Theme; compatibility_mode: 'auto'|'http'|'browser'; ipv6_test_enabled: boolean }
type Status = { active_mode: Mode; dns_ip: string|null; router_ip: string; last_change: string|null; last_verification: string; last_operation_at: string|null; busy: boolean; checking_router: boolean; requested_mode: Exclude<Mode, 'unknown'>|null; error: string|null; warning: string|null }
type LogEntry = { type: string; timestamp: string; level: string; message: string }

const defaults: Settings = { router_ip: '192.168.1.1', router_port: 80, router_protocol: 'http', router_timeout: 10, apply_timeout: 30, pihole_ip: '192.168.1.2', standard_dns_ip: '192.168.1.1', refresh_mode: 'quick', theme: 'system', compatibility_mode: 'auto', ipv6_test_enabled: false }
const tokenFromUrl = new URLSearchParams(window.location.search).get('token')
if (tokenFromUrl) {
  window.localStorage.setItem('dns-switcher-bootstrap-token', tokenFromUrl)
  window.localStorage.removeItem('dns-switcher-session-token')
  const cleanUrl = `${window.location.pathname}${window.location.hash}`
  window.history.replaceState({}, document.title, cleanUrl)
}
const bootstrapToken = tokenFromUrl ?? window.localStorage.getItem('dns-switcher-bootstrap-token') ?? window.localStorage.getItem('dns-switcher-session-token') ?? 'development-only-token'
class ApiError extends Error { constructor(message: string, readonly status: number) { super(message) } }
const api = async <T,>(path: string, init: RequestInit = {}): Promise<T> => {
  const headers = new Headers(init.headers)
  headers.set('X-Session-Token', bootstrapToken)
  if (init.body) headers.set('Content-Type', 'application/json')
  const response = await fetch(path, { ...init, headers, credentials: 'same-origin' })
  if (!response.ok) { const body = await response.json().catch(() => ({})); throw new ApiError(body.detail ?? `Errore HTTP ${response.status}`, response.status) }
  return response.json() as Promise<T>
}

function formatTime(value?: string | null) { return value ? new Date(value).toLocaleString('it-IT', { dateStyle: 'short', timeStyle: 'medium' }) : '—' }
function modeLabel(mode: Mode) { return mode === 'pihole' ? 'DNS Pi-hole' : mode === 'standard' ? 'DNS Standard' : 'Stato sconosciuto' }
function levelClass(level: string) { return level === 'error' ? 'log-error' : level === 'warning' ? 'log-warning' : level === 'success' ? 'log-success' : level === 'command' ? 'log-command' : '' }

export default function App() {
  const [authView, setAuthView] = useState<AuthView>('checking')
  const [view, setView] = useState<View>('dashboard')
  const [settings, setSettings] = useState<Settings>(defaults)
  const [form, setForm] = useState<Settings>(defaults)
  const [status, setStatus] = useState<Status>({ active_mode: 'unknown', dns_ip: null, router_ip: defaults.router_ip, last_change: null, last_verification: 'Non ancora eseguita', last_operation_at: null, busy: false, checking_router: false, requested_mode: null, error: null, warning: null })
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [credentials, setCredentials] = useState({ username: 'admin', password_configured: false })
  const [credentialForm, setCredentialForm] = useState({ username: 'admin', password: '' })
  const [notice, setNotice] = useState<{ kind: 'success'|'error'|'info'; text: string }|null>(null)
  const [testing, setTesting] = useState<string|null>(null)
  const [saving, setSaving] = useState(false)
  const [startingMode, setStartingMode] = useState<Exclude<Mode, 'unknown'>|null>(null)
  const terminalRef = useRef<HTMLDivElement>(null)
  const initialRouterRead = useRef(false)

  const checkAuthentication = useCallback(async () => {
    try {
      const auth = await api<AuthStatus>('/api/auth/status')
      setAuthView(auth.authenticated ? 'authenticated' : auth.password_configured ? 'login' : 'setup')
    } catch (error) {
      setAuthView(error instanceof ApiError && error.status === 401 ? 'invalid-link' : 'login')
    }
  }, [])

  const load = useCallback(async () => {
    try {
      const [nextSettings, nextStatus, nextCredentials] = await Promise.all([api<Settings>('/api/settings'), api<Status>('/api/status'), api<typeof credentials>('/api/settings/credentials')])
      setSettings(nextSettings); setForm(nextSettings); setStatus(nextStatus); setCredentials(nextCredentials); setCredentialForm(v => ({ ...v, username: nextCredentials.username }))
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) setAuthView('login')
      else setNotice({ kind: 'error', text: error instanceof Error ? error.message : 'Backend non disponibile' })
    }
  }, [])

  const refreshRouterStatus = useCallback(async (showNotice = false) => {
    setStatus(current => ({ ...current, checking_router: true }))
    if (showNotice) setNotice({ kind: 'info', text: 'Lettura del DNS effettivo dal router…' })
    try {
      const next = await api<Status>('/api/status/refresh', { method: 'POST' })
      setStatus(next)
      if (showNotice && next.dns_ip) setNotice({ kind: 'success', text: `DNS configurato sul router: ${next.dns_ip}` })
    } catch (error) {
      setStatus(current => ({ ...current, checking_router: false }))
      if (showNotice) setNotice({ kind: 'error', text: error instanceof Error ? error.message : 'Lettura router non riuscita' })
    }
  }, [])

  useEffect(() => { void checkAuthentication() }, [checkAuthentication])
  useEffect(() => {
    if (authView !== 'authenticated') return
    void load().then(() => {
      if (!initialRouterRead.current) { initialRouterRead.current = true; void refreshRouterStatus() }
    })
    const timer = window.setInterval(() => void api<Status>('/api/status').then(setStatus).catch(() => undefined), 1500)
    return () => window.clearInterval(timer)
  }, [authView, load, refreshRouterStatus])
  useEffect(() => { document.documentElement.dataset.theme = settings.theme === 'system' ? (matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark') : settings.theme }, [settings.theme])
  useEffect(() => { if (terminalRef.current) terminalRef.current.scrollTop = terminalRef.current.scrollHeight }, [logs])
  useEffect(() => {
    if (authView !== 'authenticated') return
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'; const host = window.location.host
    const socket = new WebSocket(`${protocol}://${host}/ws/terminal`)
    socket.onmessage = event => { try { const entry = JSON.parse(event.data) as LogEntry; setLogs(previous => [...previous.slice(-499), entry]) } catch { /* ignore malformed event */ } }
    return () => socket.close()
  }, [authView])

  const switchMode = async (mode: Exclude<Mode, 'unknown'>) => {
    if (status.busy || status.checking_router || startingMode) return
    setStartingMode(mode)
    setStatus(current => ({ ...current, busy: true, requested_mode: mode, error: null, warning: null }))
    try { setNotice(null); await api('/api/dns/switch', { method: 'POST', body: JSON.stringify({ mode }) }); setNotice({ kind: 'info', text: 'Cambio DNS avviato. Lo stato si aggiornerà appena il router conferma.' }) }
    catch (error) { setStatus(current => ({ ...current, busy: false, requested_mode: null })); setNotice({ kind: 'error', text: error instanceof Error ? error.message : 'Impossibile avviare il cambio DNS' }) }
    finally { setStartingMode(null) }
  }
  const cancel = async () => { await api('/api/dns/cancel', { method: 'POST' }).catch(() => undefined); setNotice({ kind: 'info', text: 'Annullamento richiesto' }) }
  const verify = async () => { try { const result = await api<{ ok: boolean; message: string }>('/api/dns/verify', { method: 'POST' }); setNotice({ kind: result.ok ? 'success' : 'error', text: result.message }); await load() } catch (error) { setNotice({ kind: 'error', text: error instanceof Error ? error.message : 'Verifica fallita' }) } }
  const saveSettings = async () => { setSaving(true); setNotice({ kind: 'info', text: 'Salvataggio delle impostazioni in corso…' }); try { const next = await api<Settings>('/api/settings', { method: 'PUT', body: JSON.stringify(form) }); setSettings(next); setForm(next); setNotice({ kind: 'success', text: 'Impostazioni salvate correttamente.' }) } catch (error) { setNotice({ kind: 'error', text: error instanceof Error ? error.message : 'Salvataggio non riuscito' }) } finally { setSaving(false) } }
  const saveCredentials = async () => { setSaving(true); setNotice({ kind: 'info', text: 'Protezione delle credenziali in corso…' }); try { const next = await api<typeof credentials>('/api/settings/credentials', { method: 'PUT', body: JSON.stringify({ username: credentialForm.username, password: credentialForm.password || null }) }); setCredentials(next); setCredentialForm(v => ({ ...v, password: '' })); setNotice({ kind: 'success', text: 'Credenziali aggiornate nell’archivio protetto dell’app.' }) } catch (error) { setNotice({ kind: 'error', text: error instanceof Error ? error.message : 'Credenziali non salvate' }) } finally { setSaving(false) } }
  const testConnection = async (target: 'router'|'pihole'|'standard') => {
    setTesting(target)
    setNotice({ kind: 'info', text: `Test ${target === 'pihole' ? 'Pi-hole' : target === 'standard' ? 'DNS standard' : 'router'} in corso…` })
    const address = target === 'pihole' ? form.pihole_ip : target === 'standard' ? form.standard_dns_ip : form.router_ip
    try {
      const result = await api<{ ok: boolean; message: string }>('/api/settings/test', { method: 'POST', body: JSON.stringify({ target, address, router_protocol: form.router_protocol, router_port: form.router_port, router_timeout: form.router_timeout }) })
      setNotice({ kind: result.ok ? 'success' : 'error', text: result.message })
    } catch (error) { setNotice({ kind: 'error', text: error instanceof Error ? error.message : 'Test fallito' }) } finally { setTesting(null) }
  }
  const copyLogs = async () => { await navigator.clipboard?.writeText(logs.map(item => `[${formatTime(item.timestamp)}] ${item.message}`).join('\n')); setNotice({ kind: 'success', text: 'Log copiato negli appunti' }) }
  const saveLogs = () => { const blob = new Blob([logs.map(item => `[${formatTime(item.timestamp)}] ${item.message}`).join('\n')], { type: 'text/plain;charset=utf-8' }); const link = document.createElement('a'); link.href = URL.createObjectURL(blob); link.download = 'dns-switcher-log.txt'; link.click(); URL.revokeObjectURL(link.href) }
  const logout = async () => { await api('/api/auth/logout', { method: 'POST' }).catch(() => undefined); setLogs([]); setView('dashboard'); setAuthView('login') }
  const openPihole = () => {
    const link = document.createElement('a')
    link.href = `http://${settings.pihole_ip}/admin/`
    link.target = '_blank'
    link.rel = 'noopener noreferrer'
    link.click()
  }

  if (authView === 'checking') return <AuthLoading />
  if (authView === 'invalid-link') return <InvalidLink />
  if (authView === 'login' || authView === 'setup') return <AccessGate mode={authView} onAuthenticated={() => { initialRouterRead.current = false; setAuthView('authenticated') }} />

  const activeDns = status.dns_ip ?? (status.active_mode === 'pihole' ? settings.pihole_ip : status.active_mode === 'standard' ? settings.standard_dns_ip : '—')
  const modeTone = status.active_mode === 'pihole' ? 'violet' : status.active_mode === 'standard' ? 'blue' : 'neutral'

  return <div className="app-shell">
    <header className="topbar"><div className="brand"><img className="brand-mark" src="/icon.svg" alt=""/><div><div className="brand-name">DNS Switcher <span>Pro</span></div><div className="eyebrow">LOCAL NETWORK CONTROL · v1.1.5</div></div></div><div className="top-actions"><div className="connection-pill"><span className="pulse-dot"/> Accesso protetto</div><button className={`password-button ${view === 'password' ? 'is-active' : ''}`} onClick={() => setView(view === 'password' ? 'dashboard' : 'password')}><KeyRound size={17}/><span>{view === 'password' ? 'Dashboard' : 'Imposta Password'}</span></button><button className="pihole-button" onClick={openPihole} title={`Apri Pi-hole · ${settings.pihole_ip}`} aria-label={`Apri Pi-hole all'indirizzo ${settings.pihole_ip}`}><Database size={17}/><span>Pi-hole</span><ExternalLink size={13}/></button><button className={`settings-button ${view === 'settings' ? 'is-active' : ''}`} onClick={() => setView(view === 'settings' ? 'dashboard' : 'settings')}><Settings2 size={17}/><span>{view === 'settings' ? 'Dashboard' : 'Impostazioni'}</span></button></div></header>
    <main className="content">
      {notice && <div className={`notice notice-${notice.kind}`} role={notice.kind === 'error' ? 'alert' : 'status'} aria-live="polite"><span>{notice.kind === 'success' ? <CheckCircle2 size={17}/> : notice.kind === 'error' ? <AlertTriangle size={17}/> : <Activity size={17}/>}</span><strong>{notice.text}</strong><button aria-label="Chiudi messaggio" onClick={() => setNotice(null)}><X size={15}/></button></div>}
      <AnimatePresence mode="wait">{view === 'dashboard' ? <motion.div key="dashboard" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
        <section className="status-grid"><div className={`status-card tone-${modeTone}`}><div className="card-heading"><span>MODALITÀ ATTIVA</span><div className="status-icon"><Zap size={17}/></div></div><div className="status-value">{modeLabel(status.active_mode)}</div><div className="status-sub"><span className="status-dot"/> {status.busy ? 'Cambio in corso' : status.checking_router ? 'Verifica sul router in corso' : status.error ? 'Richiede attenzione' : status.dns_ip ? 'Rilevata sul router' : 'In attesa di rilevamento'}</div></div><div className="status-card dns-status-card"><div className="card-heading"><span>DNS CONFIGURATO SUL ROUTER</span><Globe2 size={17}/></div><div className="status-value dns-value mono">{status.checking_router && !status.dns_ip ? '…' : activeDns}</div><div className="status-sub">{status.checking_router && status.dns_ip ? 'Ultimo valore confermato · verifica in corso' : `Router · ${status.router_ip || settings.router_ip}`}</div></div><div className="status-card router-status-card"><div className="card-heading"><span>STATO ROUTER</span><CheckCircle2 size={17}/></div><div className="status-value compact">{status.checking_router ? 'Lettura in corso…' : status.error ? 'Richiede attenzione' : status.dns_ip ? 'DNS sincronizzato' : 'DNS non rilevato'}</div><div className="status-sub status-sub-between"><span>{formatTime(status.last_operation_at)}</span><button className="card-action" onClick={() => void refreshRouterStatus(true)} disabled={status.busy || status.checking_router}><RefreshCw size={13}/> Rileggi</button></div></div></section>
        {(status.warning || status.error) && <div className={`inline-alert ${status.error ? 'is-error' : ''}`}><AlertTriangle size={18}/><div><strong>{status.error ? 'Operazione non completata' : 'Nota di rete'}</strong><span>{status.error ?? status.warning}</span></div></div>}
        <section className="switch-grid"><SwitchCard mode="pihole" ip={settings.pihole_ip} active={status.active_mode === 'pihole'} disabled={status.busy || status.checking_router || startingMode !== null} loading={(status.requested_mode ?? startingMode) === 'pihole'} onClick={() => void switchMode('pihole')} /><SwitchCard mode="standard" ip={settings.standard_dns_ip} active={status.active_mode === 'standard'} disabled={status.busy || status.checking_router || startingMode !== null} loading={(status.requested_mode ?? startingMode) === 'standard'} onClick={() => void switchMode('standard')} /></section>
        <section className="terminal-panel"><div className="panel-header"><div className="panel-title"><Terminal size={18}/><div><strong>Terminale operazioni</strong><span>Eventi in tempo reale · massimo 500 righe</span></div></div><div className="terminal-actions"><button onClick={() => setLogs([])} title="Cancella"><Trash2 size={15}/></button><button onClick={() => void copyLogs()} title="Copia log"><Copy size={15}/></button><button onClick={saveLogs} title="Salva log"><Save size={15}/></button></div></div><div className="terminal" ref={terminalRef}>{logs.length === 0 ? <div className="terminal-empty"><Terminal size={25}/><span>Avvia una modalità per vedere qui ogni passaggio.</span></div> : logs.map((entry, index) => <div className={`log-line ${levelClass(entry.level)}`} key={`${entry.timestamp}-${index}`}><span className="log-time">{new Date(entry.timestamp).toLocaleTimeString('it-IT')}</span><span className="log-marker">{entry.level === 'success' ? '✓' : entry.level === 'error' ? '×' : entry.level === 'warning' ? '!' : entry.level === 'command' ? '$' : '·'}</span><span>{entry.message}</span></div>)}</div><div className="terminal-footer"><span><span className="pulse-dot"/> WebSocket connesso</span><div>{status.busy && <button className="text-button danger" onClick={() => void cancel()}><CircleStop size={14}/> Annulla</button>}<button className="text-button" onClick={() => void verify()} disabled={status.busy}><RefreshCw size={14}/> Verifica DNS</button></div></div></section>
        <section className="footer-note"><AlertTriangle size={15}/><span>Il cambio riguarda il DNS IPv4 distribuito dal DHCP. Alcuni dispositivi potrebbero continuare a usare il DNS IPv6 del router TIM.</span><button onClick={() => setView('settings')}>Apri impostazioni <ChevronRight size={14}/></button></section>
      </motion.div> : view === 'settings' ? <motion.div key="settings" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}><SettingsView form={form} setForm={setForm} credentials={credentials} credentialForm={credentialForm} setCredentialForm={setCredentialForm} saving={saving} testing={testing} onSave={saveSettings} onSaveCredentials={saveCredentials} onTest={testConnection} onReset={async () => { const next = await api<Settings>('/api/settings/reset', { method: 'POST' }); setForm(next); setSettings(next); setNotice({ kind: 'success', text: 'Valori predefiniti ripristinati' }) }} onBack={() => setView('dashboard')} /></motion.div> : <motion.div key="password" initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}><PasswordView onBack={() => setView('dashboard')} onChanged={() => { setNotice({ kind: 'success', text: 'Password di accesso aggiornata correttamente.' }); setView('dashboard') }} onLogout={logout}/></motion.div>}</AnimatePresence>
    </main><footer className="app-footer"><span>Copyright 2026 Alex Lignola · Created by Alex Lignola</span><span className="footer-secure"><LockKeyhole size={13}/> Sessione locale protetta</span></footer>
  </div>
}

function BrandBlock() { return <div className="auth-brand"><img src="/icon.svg" alt=""/><div><div className="brand-name">DNS Switcher <span>Pro</span></div><div className="eyebrow">LOCAL NETWORK CONTROL · v1.1.5</div></div></div> }

function AuthLoading() { return <div className="auth-shell"><BrandBlock/><div className="auth-loading"><Loader2 className="spin" size={24}/><span>Verifica accesso…</span></div></div> }

function InvalidLink() { return <div className="auth-shell"><BrandBlock/><section className="auth-card"><div className="auth-icon is-error"><AlertTriangle size={25}/></div><p className="eyebrow accent">COLLEGAMENTO NON VALIDO</p><h1>Token locale mancante</h1><p className="auth-copy">Apri DNS Switcher Pro dall’applicazione Windows oppure usa l’indirizzo completo mostrato dall’installazione Docker.</p></section></div> }

function AccessGate({ mode, onAuthenticated }: { mode: 'login'|'setup'; onAuthenticated: () => void }) {
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string|null>(null)
  const [submitting, setSubmitting] = useState(false)
  const setup = mode === 'setup'
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (setup && password !== confirm) { setError('Le due password non coincidono'); return }
    setSubmitting(true)
    try {
      await api<AuthStatus>(setup ? '/api/auth/setup' : '/api/auth/login', { method: 'POST', body: JSON.stringify(setup ? { new_password: password } : { password }) })
      onAuthenticated()
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Accesso non riuscito') }
    finally { setSubmitting(false) }
  }
  return <div className="auth-shell"><BrandBlock/><motion.section className="auth-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}><div className="auth-icon"><LockKeyhole size={25}/></div><p className="eyebrow accent">{setup ? 'PRIMO ACCESSO' : 'ACCESSO RISERVATO'}</p><h1>{setup ? 'Crea la password' : 'Bentornato'}</h1><p className="auth-copy">{setup ? 'Proteggi entrambe le versioni dell’app con una password personale di almeno 8 caratteri.' : 'Inserisci la password di accesso per aprire il pannello DNS.'}</p><form onSubmit={submit} className="auth-form"><label className="field-label">{setup ? 'Nuova password' : 'Password'}<div className="password-input"><input autoFocus type={showPassword ? 'text' : 'password'} value={password} onChange={event => setPassword(event.target.value)} autoComplete={setup ? 'new-password' : 'current-password'} minLength={setup ? 8 : 1} maxLength={128} required/><button type="button" onClick={() => setShowPassword(value => !value)} aria-label={showPassword ? 'Nascondi password' : 'Mostra password'}>{showPassword ? <EyeOff size={16}/> : <Eye size={16}/>}</button></div></label>{setup && <label className="field-label">Conferma password<input type={showPassword ? 'text' : 'password'} value={confirm} onChange={event => setConfirm(event.target.value)} autoComplete="new-password" minLength={8} maxLength={128} required/></label>}{error && <div className="form-error" role="alert"><AlertTriangle size={15}/>{error}</div>}<button className="auth-submit" disabled={submitting}>{submitting ? <Loader2 className="spin" size={17}/> : <LockKeyhole size={17}/>} {submitting ? 'Attendere…' : setup ? 'Crea password e accedi' : 'Accedi'}</button></form><div className="auth-security"><ShieldCheck size={15}/><span>La password è memorizzata solo come hash nel database locale.</span></div></motion.section></div>
}

function PasswordView({ onBack, onChanged, onLogout }: { onBack: () => void; onChanged: () => void; onLogout: () => void }) {
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState<string|null>(null)
  const [saving, setSaving] = useState(false)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    setError(null)
    if (newPassword !== confirmPassword) { setError('Le due nuove password non coincidono'); return }
    if (currentPassword === newPassword) { setError('La nuova password deve essere diversa da quella attuale'); return }
    setSaving(true)
    try {
      await api<AuthStatus>('/api/auth/password', { method: 'PUT', body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }) })
      onChanged()
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'Password non aggiornata') }
    finally { setSaving(false) }
  }
  return <section className="settings-page password-page"><div className="settings-heading"><div><button className="back-button" onClick={onBack}><ChevronRight size={15} className="back-chevron"/> Dashboard</button><p className="eyebrow accent">SICUREZZA</p><h1>Imposta Password</h1><p className="hero-copy">Modifica la password richiesta all’apertura dell’app Docker e dell’eseguibile Windows.</p></div><button className="ghost-button logout-button" onClick={onLogout}><LogOut size={15}/> Esci dall’app</button></div><div className="password-layout"><form className="settings-section password-card" onSubmit={submit}><div className="section-title"><span className="section-icon"><KeyRound size={17}/></span><div><h3>Password di accesso</h3><p>La modifica chiude tutte le altre sessioni già aperte.</p></div></div><label className="field-label">Password attuale<input type={showPassword ? 'text' : 'password'} value={currentPassword} onChange={event => setCurrentPassword(event.target.value)} autoComplete="current-password" required/></label><label className="field-label">Nuova password<input type={showPassword ? 'text' : 'password'} value={newPassword} onChange={event => setNewPassword(event.target.value)} autoComplete="new-password" minLength={8} maxLength={128} required/></label><label className="field-label">Conferma nuova password<input type={showPassword ? 'text' : 'password'} value={confirmPassword} onChange={event => setConfirmPassword(event.target.value)} autoComplete="new-password" minLength={8} maxLength={128} required/></label><label className="show-password-row"><input type="checkbox" checked={showPassword} onChange={event => setShowPassword(event.target.checked)}/><span>{showPassword ? <EyeOff size={15}/> : <Eye size={15}/>} Mostra password</span></label>{error && <div className="form-error" role="alert"><AlertTriangle size={15}/>{error}</div>}<button className="primary-button password-save" disabled={saving}>{saving ? <Loader2 className="spin" size={16}/> : <Save size={16}/>} {saving ? 'Aggiornamento…' : 'Aggiorna password'}</button></form><aside className="settings-section security-card"><ShieldCheck size={30}/><h3>Protezione locale</h3><p>La password non viene mai salvata in chiaro. Il backend usa PBKDF2-SHA256 con salt casuale e crea una sessione HttpOnly valida per 12 ore.</p><div><Check size={14}/> Valida per Docker e Windows</div><div><Check size={14}/> Sessioni revocate al cambio password</div><div><Check size={14}/> Nessuna password nei log</div></aside></div></section>
}

function SwitchCard({ mode, ip, active, disabled, loading, onClick }: { mode: 'pihole'|'standard'; ip: string; active: boolean; disabled: boolean; loading: boolean; onClick: () => void }) { const pihole = mode === 'pihole'; return <motion.div whileHover={disabled ? undefined : { y: -3 }} className={`switch-card ${pihole ? 'switch-pihole' : 'switch-standard'} ${active ? 'is-active' : ''}`}><div className="switch-card-top"><div className="switch-icon">{pihole ? <Database size={23}/> : <Wifi size={23}/>}</div>{active && <span className="active-badge"><Check size={12}/> ATTIVA</span>}</div><div className="switch-copy"><h2>{pihole ? 'DNS Pi-hole' : 'DNS Standard'}</h2><p>{pihole ? 'Filtraggio, privacy e controllo sulla tua rete.' : 'Risoluzione DNS del router TIM, senza filtri.'}</p><span className="ip-chip"><span className="tiny-dot"/>{ip}</span></div><button className="switch-button" onClick={onClick} disabled={disabled || active}>{loading ? <Loader2 size={17} className="spin"/> : <Play size={16} fill="currentColor"/>}{loading ? 'Attivazione…' : active ? 'Modalità attiva' : `Attiva ${pihole ? 'Pi-hole' : 'Standard'}`}<ChevronRight size={16}/></button></motion.div> }

function SettingsView({ form, setForm, credentials, credentialForm, setCredentialForm, saving, testing, onSave, onSaveCredentials, onTest, onReset, onBack }: { form: Settings; setForm: (value: Settings) => void; credentials: { username: string; password_configured: boolean }; credentialForm: { username: string; password: string }; setCredentialForm: (value: { username: string; password: string }) => void; saving: boolean; testing: string|null; onSave: () => void; onSaveCredentials: () => void; onTest: (target: 'router'|'pihole'|'standard') => void; onReset: () => void; onBack: () => void }) {
  const update = <K extends keyof Settings>(key: K, value: Settings[K]) => setForm({ ...form, [key]: value })
  return <section className="settings-page"><div className="settings-heading"><div><button className="back-button" onClick={onBack}><ChevronRight size={15} className="back-chevron"/> Dashboard</button><p className="eyebrow accent">CONFIGURAZIONE</p><h1>Impostazioni</h1><p className="hero-copy">Personalizza rete, aggiornamento dei client e accesso al router.</p></div><div className="settings-actions"><button className="ghost-button" onClick={onReset}><RotateCcw size={15}/> Ripristina default</button><button className="primary-button" onClick={onSave} disabled={saving}>{saving ? <Loader2 className="spin" size={16}/> : <Save size={16}/>} {saving ? 'Salvataggio…' : 'Salva impostazioni'}</button></div></div><div className="settings-layout"><div className="settings-column"><SettingsSection icon={<Network size={17}/>} title="Indirizzi di rete" description="Il test usa subito il valore scritto, anche prima del salvataggio."><SettingInput label="IP router DNS Standard" value={form.standard_dns_ip} onChange={v => update('standard_dns_ip', v)} action="standard" testing={testing} onTest={onTest}/><SettingInput label="IP server Pi-hole" value={form.pihole_ip} onChange={v => update('pihole_ip', v)} action="pihole" testing={testing} onTest={onTest}/><SettingInput label="Indirizzo router TIM" value={form.router_ip} onChange={v => update('router_ip', v)} action="router" testing={testing} onTest={onTest}/></SettingsSection><SettingsSection icon={<RefreshCw size={17}/>} title="Aggiornamento dei client" description="Su Windows rinnova la rete locale; nel container i dispositivi si aggiornano al rinnovo DHCP."><label className="field-label">Modalità rinnovo DHCP<select value={form.refresh_mode} onChange={e => update('refresh_mode', e.target.value as Settings['refresh_mode'])}><option value="quick">Rapido · aggiornamento cache e lease</option><option value="full">Completo · nuovo lease DHCP</option></select></label>{form.refresh_mode === 'full' && <div className="warning-box"><AlertTriangle size={16}/> Su Windows il rilascio può interrompere la connettività per alcuni secondi.</div>}</SettingsSection><SettingsSection icon={<ShieldCheck size={17}/>} title="Compatibilità router" description="Automatica riconosce anche il login JavaScript/SRP dei TIM HUB Technicolor."><div className="segmented">{(['auto','http','browser'] as const).map(mode => <button type="button" key={mode} className={form.compatibility_mode === mode ? 'selected' : ''} onClick={() => update('compatibility_mode', mode)}>{mode === 'auto' ? 'Automatica' : mode === 'http' ? 'HTTP' : 'Browser automatico'}</button>)}</div></SettingsSection></div><div className="settings-column"><SettingsSection icon={<Globe2 size={17}/>} title="Router e timeout" description="Parametri di collegamento al pannello TIM HUB."><div className="two-fields"><label className="field-label">Protocollo<select value={form.router_protocol} onChange={e => update('router_protocol', e.target.value as Settings['router_protocol'])}><option value="http">HTTP</option><option value="https">HTTPS</option></select></label><label className="field-label">Porta<input type="number" min="1" max="65535" value={form.router_port} onChange={e => update('router_port', Number(e.target.value))}/></label></div><div className="two-fields"><label className="field-label">Timeout connessione (s)<input type="number" min="1" max="120" value={form.router_timeout} onChange={e => update('router_timeout', Number(e.target.value))}/></label><label className="field-label">Timeout applicazione (s)<input type="number" min="5" max="300" value={form.apply_timeout} onChange={e => update('apply_timeout', Number(e.target.value))}/></label></div></SettingsSection><SettingsSection icon={<LockKeyhole size={17}/>} title="Credenziali router" description="La password viene conservata nell’archivio protetto del sistema o nel volume cifrato del container."><label className="field-label">Nome utente<input value={credentialForm.username} onChange={e => setCredentialForm({ ...credentialForm, username: e.target.value })} autoComplete="username"/></label><label className="field-label">Nuova password<input type="password" placeholder={credentials.password_configured ? 'Password già configurata · lascia vuoto per mantenere' : 'Inserisci la password'} value={credentialForm.password} onChange={e => setCredentialForm({ ...credentialForm, password: e.target.value })} autoComplete="new-password"/></label><div className="credential-status"><span className={credentials.password_configured ? 'check-circle' : 'empty-circle'}>{credentials.password_configured ? <Check size={13}/> : null}</span>{credentials.password_configured ? 'Password configurata e protetta' : 'Password non ancora configurata'}<button className="small-button" onClick={onSaveCredentials} disabled={saving}>{saving ? <Loader2 size={13} className="spin"/> : null} Aggiorna</button></div></SettingsSection><SettingsSection icon={<AlertTriangle size={17}/>} title="Avviso IPv6" description="Il test è informativo e non modifica la configurazione IPv6."><div className="ipv6-note">Alcuni dispositivi possono usare il DNS IPv6 locale del router e bypassare Pi-hole. Questa app cambia solo il DNS IPv4 distribuito dal DHCP.</div><label className="toggle-row"><input type="checkbox" checked={form.ipv6_test_enabled} onChange={e => update('ipv6_test_enabled', e.target.checked)}/><span className="toggle-ui"/>Abilita test IPv6 informativo</label></SettingsSection></div></div></section>
}

function SettingsSection({ icon, title, description, children }: { icon: React.ReactNode; title: string; description: string; children: React.ReactNode }) { return <div className="settings-section"><div className="section-title"><span className="section-icon">{icon}</span><div><h3>{title}</h3><p>{description}</p></div></div>{children}</div> }
function SettingInput({ label, value, onChange, action, testing, onTest }: { label: string; value: string; onChange: (value: string) => void; action: 'router'|'pihole'|'standard'; testing: string|null; onTest: (target: 'router'|'pihole'|'standard') => void }) { return <label className="field-label">{label}<div className="input-action"><input value={value} onChange={e => onChange(e.target.value)} inputMode="decimal"/><button type="button" onClick={() => onTest(action)} disabled={testing !== null}>{testing === action ? <Loader2 size={14} className="spin"/> : <Wifi size={14}/>} {testing === action ? 'Test…' : 'Testa'}</button></div></label> }
