import {
  Bell,
  Briefcase,
  CalendarDays,
  FileStack,
  HelpCircle,
  LayoutGrid,
  ReceiptText,
  ScrollText,
  Search,
} from 'lucide-react'
import type { FormEvent, ReactNode } from 'react'
import { useState } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'

// Attendance, Cashbook, Compliance, Expenses and Parties are gone — no
// endpoints back them.
const NAV = [
  { to: '/today', icon: CalendarDays, label: 'Today' },
  { to: '/jobs', icon: Briefcase, label: 'Jobs' },
  { to: '/quotations', icon: ScrollText, label: 'Quotations' },
  { to: '/invoices', icon: ReceiptText, label: 'Invoices' },
  { to: '/documents', icon: FileStack, label: 'Documents' },
  { to: '/search', icon: Search, label: 'Search' },
]

function SideNav() {
  return (
    <nav className="bg-paper text-body-md h-screen w-64 fixed left-0 top-0 rule-r hidden md:flex flex-col py-4 z-40">
      <div className="px-6 pb-6 rule-b flex items-center gap-3">
        <div className="w-9 h-9 rounded bg-action flex items-center justify-center">
          <LayoutGrid size={18} className="text-white" />
        </div>
        <div>
          <div className="text-headline-md text-action font-bold tracking-tight">OneEntry</div>
          <div className="text-label-caps text-ink-muted">Small Business ERP</div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto py-2">
        <ul className="flex flex-col gap-1 px-2">
          {NAV.map(({ to, icon: IconCmp, label }) => (
            <li key={to} className="relative">
              <NavLink
                to={to}
                className={({ isActive }) =>
                  `relative flex items-center gap-3 px-3 py-2 rounded transition-colors ${
                    isActive ? 'text-ink font-semibold' : 'text-ink-muted hover:bg-white'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    {isActive && (
                      <motion.div
                        layoutId="nav-active"
                        className="absolute inset-0 bg-carbon rounded"
                        transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                      />
                    )}
                    <span className="relative flex items-center gap-3">
                      <IconCmp size={18} strokeWidth={isActive ? 2.5 : 2} />
                      {label}
                    </span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-auto rule-t pt-3 px-6">
        <div className="text-label-caps text-ink-muted">Quantum Arena 2026</div>
        <div className="text-body-md text-ink-muted mt-1">Enter a job once.</div>
      </div>
    </nav>
  )
}

function TopBar() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!q.trim()) return
    navigate(`/search?q=${encodeURIComponent(q.trim())}`)
    setQ('')
  }

  return (
    <header className="bg-paper w-full h-16 rule-b flex justify-between items-center px-6 sticky top-0 z-50">
      <form className="flex items-center gap-4 flex-1" onSubmit={submit}>
        <div className="flex items-center max-w-md w-full gap-2">
          <Search size={18} className="text-ink-muted shrink-0" />
          <input
            className="bg-transparent border-none outline-none text-body-md text-ink placeholder:text-ink-muted w-full p-0"
            placeholder="Ask anything — “unpaid invoices”, “that painting job”…"
            value={q}
            onChange={(event) => setQ(event.target.value)}
          />
        </div>
      </form>
      <div className="flex items-center gap-4">
        <Bell size={18} className="text-ink-muted" />
        <HelpCircle size={18} className="text-ink-muted" />
        <div className="w-8 h-8 rounded-full bg-ledger flex items-center justify-center text-label-caps text-ink">
          SC
        </div>
      </div>
    </header>
  )
}

export default function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden">
      <SideNav />
      <div className="flex-1 flex flex-col md:ml-64 w-full h-screen overflow-hidden">
        <TopBar />
        <main className="flex-1 overflow-y-auto bg-paper p-6 lg:p-10">{children}</main>
      </div>
    </div>
  )
}
