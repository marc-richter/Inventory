import React, { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth, hasRole, hasCapability, isRestricted } from './AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import MobileTileMenu from './components/MobileTileMenu'

// Handy/Tablet erkennen (Kachel-Startmenü statt Übersichts-Liste).
function useIsMobile(): boolean {
  const [m, setM] = React.useState(() => (typeof window !== 'undefined' ? window.matchMedia('(max-width: 767px)').matches : false))
  React.useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')
    const on = () => setM(mq.matches)
    mq.addEventListener('change', on)
    return () => mq.removeEventListener('change', on)
  }, [])
  return m
}

// Selten genutzte / grosse Seiten erst bei Bedarf nachladen (Code-Splitting).
// Das verkuerzt den ersten Start spuerbar, gerade auf aelteren Tablets.
const ArticleForm = lazy(() => import('./pages/ArticleForm'))
const BulkArticleForm = lazy(() => import('./pages/BulkArticleForm'))
const ArticleDetail = lazy(() => import('./pages/ArticleDetail'))
const OpenIssues = lazy(() => import('./pages/OpenIssues'))
const Persons = lazy(() => import('./pages/Persons'))
const MyArticles = lazy(() => import('./pages/MyArticles'))
const MaterialScan = lazy(() => import('./pages/MaterialScan'))
const Bereitstellungen = lazy(() => import('./pages/Bereitstellungen'))
const Schluesselbuende = lazy(() => import('./pages/Schluesselbuende'))
const MeineGeraete = lazy(() => import('./pages/MeineGeraete'))
const TypeSummary = lazy(() => import('./pages/TypeSummary'))
const ImportPage = lazy(() => import('./pages/ImportPage'))
const Settings = lazy(() => import('./pages/Settings'))
const Account = lazy(() => import('./pages/Account'))
const AccessSheet = lazy(() => import('./pages/AccessSheet'))
const SystemControl = lazy(() => import('./pages/SystemControl'))
const Approvals = lazy(() => import('./pages/Approvals'))
const Inventur = lazy(() => import('./pages/Inventur'))
const Auswertung = lazy(() => import('./pages/Auswertung'))
const Anfragen = lazy(() => import('./pages/Anfragen'))
const KeyIssueList = lazy(() => import('./pages/KeyIssueList'))
const Pruefungen = lazy(() => import('./pages/Pruefungen'))
const Meldungen = lazy(() => import('./pages/Meldungen'))
const LagerortInventur = lazy(() => import('./pages/LagerortInventur'))

function PageLoading() {
  return <div className="p-8 text-center text-sm text-muted">lädt…</div>
}

function PrivateRoute({ children, roles, caps, bare }: { children: React.ReactNode; roles?: string[]; caps?: string[]; bare?: boolean }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (roles && !hasRole(user, ...roles)) return <Navigate to="/" replace />
  if (caps && !hasCapability(user, ...caps)) return <Navigate to="/" replace />
  // bare = ohne App-Kopfzeile (z.B. druckbares Zugangsblatt)
  return bare ? children : <Layout>{children}</Layout>
}

/** Startseite: reine Leser (lesend/eigen) sehen direkt "Meine Artikel" statt der
 *  Gesamt-Uebersicht. */
function Home() {
  const { user } = useAuth()
  const isMobile = useIsMobile()
  if (isRestricted(user)) return <Navigate to="/meine-artikel" replace />
  if (isMobile) return <MobileTileMenu />
  return <Dashboard />
}

export default function App() {
  return (
    <Suspense fallback={<PageLoading />}>
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<PrivateRoute><Home /></PrivateRoute>} />
      <Route path="/articles/new" element={<PrivateRoute caps={['articles']}><ArticleForm /></PrivateRoute>} />
      <Route path="/articles/bulk" element={<PrivateRoute caps={['articles']}><BulkArticleForm /></PrivateRoute>} />
      <Route path="/articles/:id" element={<PrivateRoute><ArticleDetail /></PrivateRoute>} />
      <Route path="/offen" element={<PrivateRoute><OpenIssues /></PrivateRoute>} />
      <Route path="/personen" element={<PrivateRoute caps={['persons']}><Persons /></PrivateRoute>} />
      <Route path="/genehmigungen" element={<PrivateRoute caps={['articles']}><Approvals /></PrivateRoute>} />
      <Route path="/inventur" element={<PrivateRoute caps={['inventory', 'articles', 'issues']}><Inventur /></PrivateRoute>} />
      <Route path="/import" element={<PrivateRoute caps={['export']}><ImportPage /></PrivateRoute>} />
      <Route path="/meine-artikel" element={<PrivateRoute><MyArticles /></PrivateRoute>} />
      <Route path="/scan" element={<PrivateRoute caps={['issues']}><MaterialScan /></PrivateRoute>} />
      <Route path="/bereitstellungen" element={<PrivateRoute caps={['issues']}><Bereitstellungen /></PrivateRoute>} />
      <Route path="/uebersicht" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
      <Route path="/uebersicht-typen" element={<PrivateRoute><TypeSummary /></PrivateRoute>} />
      <Route path="/auswertung" element={<PrivateRoute><Auswertung /></PrivateRoute>} />
      <Route path="/anfragen" element={<PrivateRoute><Anfragen /></PrivateRoute>} />
      <Route path="/schluessel-ausgabe" element={<PrivateRoute caps={['issues']}><KeyIssueList /></PrivateRoute>} />
      <Route path="/schluesselbuende" element={<PrivateRoute caps={['issues']}><Schluesselbuende /></PrivateRoute>} />
      <Route path="/meine-geraete" element={<PrivateRoute><MeineGeraete /></PrivateRoute>} />
      <Route path="/pruefungen" element={<PrivateRoute caps={['articles']}><Pruefungen /></PrivateRoute>} />
      <Route path="/meldungen" element={<PrivateRoute><Meldungen /></PrivateRoute>} />
      <Route path="/lagerort-inventur" element={<PrivateRoute caps={['inventory']}><LagerortInventur /></PrivateRoute>} />
      <Route path="/zugang" element={<PrivateRoute roles={['admin']} bare><AccessSheet /></PrivateRoute>} />
      <Route path="/system" element={<PrivateRoute caps={['server_power']}><SystemControl /></PrivateRoute>} />
      <Route path="/settings" element={<PrivateRoute roles={['admin']}><Settings /></PrivateRoute>} />
      <Route path="/account" element={<PrivateRoute><Account /></PrivateRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </Suspense>
  )
}