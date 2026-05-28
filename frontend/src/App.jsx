import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import AdminLayout from './layouts/AdminLayout'
import LiveMonitor from './pages/LiveMonitor'
import Schedule from './pages/Schedule'
import Tools from './pages/Tools'
import ShortsLibrary from './pages/ShortsLibrary'
import Database from './pages/Database'
import Sources from './pages/Sources'
import { DialogProvider } from './context/DialogContext'

function App() {
  return (
    <DialogProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AdminLayout />}>
            <Route index element={<Navigate to="/live" replace />} />
            <Route path="live" element={<LiveMonitor />} />
            <Route path="schedule" element={<Schedule />} />
            <Route path="tools" element={<Tools />} />
            <Route path="sources" element={<Sources />} />
            <Route path="shorts" element={<ShortsLibrary />} />
            <Route path="database" element={<Database />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </DialogProvider>
  )
}

export default App
