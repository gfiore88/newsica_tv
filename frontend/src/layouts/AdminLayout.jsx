import React, { useEffect, useState } from 'react'
import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { Radio, Calendar, Wrench, Database, Activity, RefreshCw } from 'lucide-react'

export default function AdminLayout() {
  const [state, setState] = useState({ status: 'OFFLINE' })
  const location = useLocation()

  useEffect(() => {
    const fetchState = async () => {
      try {
        const res = await fetch('/api/state')
        if (res.ok) {
          const data = await res.json()
          setState(data)
        }
      } catch (err) {}
    }
    fetchState()
    const interval = setInterval(fetchState, 5000)
    return () => clearInterval(interval)
  }, [])

  const restartAll = async () => {
    if (confirm("Vuoi riavviare regia e stream?")) {
      await fetch('/api/service/restart', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ service: 'all' })
      })
      alert("Comando di riavvio inviato.")
    }
  }

  const navItems = [
    { path: '/live', icon: Radio, label: 'Live & Regia' },
    { path: '/schedule', icon: Calendar, label: 'Palinsesto' },
    { path: '/tools', icon: Wrench, label: 'Strumenti Editoriali' },
    { path: '/database', icon: Database, label: 'Registro Storico' },
  ]

  return (
    <div className="flex h-screen bg-slate-900 text-slate-100 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-950 border-r border-slate-800 flex flex-col">
        <div className="p-6 border-b border-slate-800 flex items-center gap-3">
          <img src="/logo.png" alt="NewsicaTV" className="w-10 h-10 rounded shadow-md" />
          <h1 className="text-xl font-black bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">NewsicaTV</h1>
        </div>
        <nav className="flex-1 p-4 space-y-2">
          {navItems.map(item => {
            const Icon = item.icon
            const isActive = location.pathname.startsWith(item.path)
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 font-semibold ${
                  isActive
                    ? 'bg-gradient-to-r from-indigo-600/80 to-purple-600/80 text-white shadow-lg shadow-indigo-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                }`}
              >
                <Icon size={20} className={isActive ? 'text-white' : 'text-slate-400'} />
                {item.label}
              </NavLink>
            )
          })}
        </nav>
        <div className="p-4 border-t border-slate-800">
          <button onClick={restartAll} className="w-full flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-300 py-2 px-4 rounded-lg text-sm font-bold transition">
            <RefreshCw size={16} /> Riavvio Emergenza
          </button>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col h-screen overflow-hidden">
        {/* Topbar */}
        <header className="h-16 glass border-b border-slate-700/50 flex items-center justify-between px-6 shrink-0 z-10">
          <div className="flex items-center gap-4">
            <h2 className="text-lg font-bold text-slate-200 capitalize">
              {navItems.find(i => location.pathname.startsWith(i.path))?.label || 'Dashboard'}
            </h2>
            <div className="h-4 w-px bg-slate-700"></div>
            <div className="text-sm font-medium text-slate-400 truncate max-w-md">
              <span className="text-slate-500 mr-2">In onda:</span>
              <span className="text-slate-200">{state.current_title || '--'}</span>
            </div>
          </div>
          <div className="flex items-center gap-6">
            <div className="flex items-center gap-2">
              <Activity size={16} className="text-slate-500" />
              <span className="text-xs font-mono text-slate-400">
                {state.last_update ? new Date(state.last_update).toLocaleTimeString() : '--:--:--'}
              </span>
            </div>
            {state.status === 'ON_AIR' ? (
              <div className="px-4 py-1.5 rounded-full text-xs font-black bg-red-600 text-white shadow-[0_0_15px_rgba(239,68,68,0.5)] animate-pulse flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-white"></div> ON AIR
              </div>
            ) : (
              <div className="px-4 py-1.5 rounded-full text-xs font-bold bg-slate-700 text-slate-300 border border-slate-600">
                OFFLINE
              </div>
            )}
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-y-auto p-6 bg-gradient-to-br from-slate-900 to-slate-950">
          <div className="max-w-7xl mx-auto h-full">
            <Outlet context={{ state }} />
          </div>
        </div>
      </main>
    </div>
  )
}
