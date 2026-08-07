import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import AppShell from './components/AppShell'
import { AnimatePresence } from './components/motion'
import Documents from './screens/Documents'
import InvoicesList from './screens/InvoicesList'
import JobDetail from './screens/JobDetail'
import JobsList from './screens/JobsList'
import QuotationsList from './screens/QuotationsList'
import SearchScreen from './screens/Search'
import Today from './screens/Today'

export default function App() {
  const location = useLocation()
  return (
    <AppShell>
      <AnimatePresence mode="wait" initial={false}>
        <Routes location={location} key={location.pathname}>
          <Route path="/" element={<Navigate to="/today" replace />} />
          <Route path="/today" element={<Today />} />
          <Route path="/jobs" element={<JobsList />} />
          <Route path="/jobs/:id" element={<JobDetail />} />
          <Route path="/quotations" element={<QuotationsList />} />
          <Route path="/invoices" element={<InvoicesList />} />
          <Route path="/documents" element={<Documents />} />
          <Route path="/search" element={<SearchScreen />} />
          <Route path="*" element={<Navigate to="/today" replace />} />
        </Routes>
      </AnimatePresence>
    </AppShell>
  )
}
