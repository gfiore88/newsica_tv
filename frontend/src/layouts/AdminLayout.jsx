import { useEffect, useState, useRef } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { Radio, Calendar, Wrench, Database, Activity, RefreshCw, MonitorPlay, Video, Rss, Menu, X, ChevronRight } from 'lucide-react'
import { useDialog } from '../context/useDialog'

export default function AdminLayout() {
  const [state, setState] = useState({ status: 'OFFLINE' })
  const [chatStatus, setChatStatus] = useState({ video_id: '', is_running: false })
  const [mobileNavOpen, setMobileNavOpen] = useState(false)
  const location = useLocation()
  const { showAlert, showConfirm } = useDialog()
  const drawerRef = useRef(null)

  // Chiude il drawer quando si cambia pagina
  useEffect(() => {
    setMobileNavOpen(false)
  }, [location.pathname])

  // Blocca lo scroll del body quando il drawer è aperto
  useEffect(() => {
    document.body.style.overflow = mobileNavOpen ? 'hidden' : ''
    return () => { document.body.style.overflow = '' }
  }, [mobileNavOpen])

  useEffect(() => {
    const fetchState = async () => {
      try {
        const res = await fetch('/api/state')
        if (res.ok) setState(await res.json())
      } catch (err) { console.error('Errore stato sistema:', err) }
    }
    fetchState()
    const interval = setInterval(fetchState, 5000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    const fetchChatStatus = async () => {
      try {
        const res = await fetch('/api/chat/status')
        if (res.ok) {
          const data = await res.json()
          setChatStatus({ video_id: data.video_id || '', is_running: Boolean(data.is_running) })
        }
      } catch (err) { console.error('Errore stato chat:', err) }
    }
    fetchChatStatus()
    const interval = setInterval(fetchChatStatus, 15000)
    return () => clearInterval(interval)
  }, [])

  const restartAll = async () => {
    if (await showConfirm("Vuoi riavviare regia e stream? Questo comporterà una breve interruzione.", "Riavvio Emergenza")) {
      try {
        await fetch('/api/service/restart', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ service: 'all' })
        })
        await showAlert("Comando di riavvio inviato con successo. Attendi qualche secondo.", "Riavvio in Corso")
      } catch (e) {
        await showAlert("Errore durante l'invio del comando.", "Errore")
      }
    }
  }

  const navItems = [
    { path: '/live', icon: Radio, label: 'Live & Regia' },
    { path: '/schedule', icon: Calendar, label: 'Palinsesto' },
    { path: '/tools', icon: Wrench, label: 'Strumenti Editoriali' },
    { path: '/sources', icon: Rss, label: 'Fonti RSS' },
    { path: '/shorts', icon: Video, label: 'Libreria Shorts' },
    { path: '/database', icon: Database, label: 'Registro Storico' },
  ]

  const embedUrl = chatStatus.video_id
    ? `https://www.youtube.com/embed/${chatStatus.video_id}?autoplay=1&mute=0&enablejsapi=1`
    : null

  const currentPage = navItems.find(i => location.pathname.startsWith(i.path))

  const SidebarContent = () => (
    <>
      {/* Logo */}
      <div className="p-5 border-b border-slate-800 flex items-center gap-3">
        <img src="/logo.png" alt="NewsicaTV" className="w-9 h-9 rounded shadow-md" />
        <h1 className="text-lg font-black bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
          NewsicaTV
        </h1>
      </div>

      {/* Nav links */}
      <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
        {navItems.map(item => {
          const Icon = item.icon
          const isActive = location.pathname.startsWith(item.path)
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={`flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-200 font-semibold ${
                isActive
                  ? 'bg-gradient-to-r from-indigo-600/80 to-purple-600/80 text-white shadow-lg shadow-indigo-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/80 active:bg-slate-700'
              }`}
            >
              <Icon size={20} className={isActive ? 'text-white shrink-0' : 'text-slate-400 shrink-0'} />
              <span className="truncate">{item.label}</span>
              {isActive && <ChevronRight size={14} className="ml-auto shrink-0 opacity-60" />}
            </NavLink>
          )
        })}
      </nav>

      {/* Riavvio emergenza */}
      <div className="p-4 border-t border-slate-800">
        <button
          onClick={restartAll}
          className="w-full flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 active:bg-slate-600 text-slate-300 py-2.5 px-4 rounded-xl text-sm font-bold transition"
        >
          <RefreshCw size={16} /> Riavvio Emergenza
        </button>
      </div>
    </>
  )

  return (
    <div className="flex h-dvh bg-slate-900 text-slate-100 overflow-hidden">

      {/* ─── SIDEBAR DESKTOP (lg+) ─── */}
      <aside className="hidden lg:flex w-64 bg-slate-950 border-r border-slate-800 flex-col shrink-0">
        <SidebarContent />
      </aside>

      {/* ─── MOBILE DRAWER OVERLAY ─── */}
      {mobileNavOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/60 backdrop-blur-sm lg:hidden"
          onClick={() => setMobileNavOpen(false)}
        />
      )}

      {/* ─── MOBILE DRAWER ─── */}
      <aside
        ref={drawerRef}
        className={`fixed inset-y-0 left-0 z-50 w-72 max-w-[85vw] bg-slate-950 border-r border-slate-800 flex flex-col lg:hidden
          transform transition-transform duration-300 ease-in-out
          ${mobileNavOpen ? 'translate-x-0' : '-translate-x-full'}`}
      >
        {/* Pulsante chiudi nel drawer */}
        <button
          onClick={() => setMobileNavOpen(false)}
          className="absolute top-4 right-4 p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition z-10"
          aria-label="Chiudi menu"
        >
          <X size={20} />
        </button>
        <SidebarContent />
      </aside>

      {/* ─── MAIN CONTENT ─── */}
      <main className="flex-1 flex flex-col h-dvh overflow-hidden min-w-0">

        {/* ─── TOPBAR ─── */}
        <header className="h-14 lg:h-16 glass border-b border-slate-700/50 flex items-center justify-between px-4 lg:px-6 shrink-0 z-10 gap-3">

          {/* Left: hamburger (mobile) + titolo */}
          <div className="flex items-center gap-3 min-w-0">
            {/* Hamburger — solo mobile */}
            <button
              onClick={() => setMobileNavOpen(true)}
              className="lg:hidden flex items-center justify-center w-9 h-9 rounded-xl text-slate-400 hover:text-white hover:bg-slate-800 transition shrink-0"
              aria-label="Apri menu"
            >
              <Menu size={22} />
            </button>

            {/* Logo — solo mobile */}
            <img src="/logo.png" alt="NewsicaTV" className="w-7 h-7 rounded lg:hidden shrink-0" />

            {/* Titolo pagina */}
            <h2 className="text-sm lg:text-lg font-bold text-slate-200 truncate hidden sm:block">
              {currentPage?.label || 'Dashboard'}
            </h2>

            {/* "In onda" — solo desktop */}
            <div className="hidden lg:flex items-center gap-2 text-sm text-slate-400 min-w-0">
              <div className="h-4 w-px bg-slate-700 shrink-0" />
              <span className="text-slate-500 shrink-0">In onda:</span>
              <span className="text-slate-200 truncate max-w-xs">{state.current_title || '--'}</span>
            </div>
          </div>

          {/* Right: orario + badge status */}
          <div className="flex items-center gap-2 lg:gap-4 shrink-0">
            <div className="hidden sm:flex items-center gap-1.5">
              <Activity size={14} className="text-slate-500" />
              <span className="text-xs font-mono text-slate-400">
                {state.last_update ? new Date(state.last_update).toLocaleTimeString() : '--:--:--'}
              </span>
            </div>

            {state.status === 'ON_AIR' ? (
              <div className="px-2.5 lg:px-4 py-1 lg:py-1.5 rounded-full text-[10px] lg:text-xs font-black bg-red-600 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)] animate-pulse flex items-center gap-1.5">
                <div className="w-1.5 h-1.5 rounded-full bg-white" />
                <span>ON AIR</span>
              </div>
            ) : (
              <div className="px-2.5 lg:px-4 py-1 lg:py-1.5 rounded-full text-[10px] lg:text-xs font-bold bg-slate-700 text-slate-300 border border-slate-600">
                OFFLINE
              </div>
            )}
          </div>
        </header>

        {/* ─── PLAYER PERSISTENTE — solo desktop ─── */}
        <div className="hidden lg:block shrink-0 border-b border-slate-800 bg-slate-950/80 px-6 py-3">
          <div className="max-w-7xl mx-auto flex items-center gap-4">
            <div className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-slate-400 min-w-[170px]">
              <MonitorPlay size={14} className="text-red-400" />
              Player Persistente
            </div>
            <div className="relative h-24 w-44 overflow-hidden rounded-lg border border-slate-700 bg-black shadow-inner shrink-0">
              {embedUrl ? (
                <iframe
                  key={chatStatus.video_id}
                  className="absolute inset-0 h-full w-full"
                  src={embedUrl}
                  frameBorder="0"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                />
              ) : (
                <div className="absolute inset-0 flex items-center justify-center px-3 text-center text-[11px] text-slate-500">
                  Nessuna live YouTube rilevata
                </div>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="text-sm font-semibold text-slate-200 truncate">
                {state.current_title || 'Nessun contenuto in onda'}
              </div>
              <div className="text-xs text-slate-400 truncate">
                {chatStatus.video_id ? `Video ID: ${chatStatus.video_id}` : 'Apri la pagina Live per i controlli completi della regia'}
              </div>
            </div>
          </div>
        </div>

        {/* ─── MINI STATUS BAR MOBILE — "in onda" compatto ─── */}
        {state.current_title && (
          <div className="lg:hidden shrink-0 border-b border-slate-800 bg-slate-950/60 px-4 py-2 flex items-center gap-2 min-w-0">
            <MonitorPlay size={12} className="text-red-400 shrink-0" />
            <span className="text-[11px] text-slate-500 shrink-0">In onda:</span>
            <span className="text-[11px] font-semibold text-slate-200 truncate">{state.current_title}</span>
          </div>
        )}

        {/* ─── PAGE CONTENT ─── */}
        <div className="flex-1 overflow-y-auto overflow-x-hidden p-4 lg:p-6 bg-gradient-to-br from-slate-900 to-slate-950">
          <div className="max-w-7xl mx-auto h-full">
            <Outlet context={{ state }} />
          </div>
        </div>
      </main>
    </div>
  )
}
