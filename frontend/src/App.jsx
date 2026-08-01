import React, { Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth, hasRole, hasCapability, isRestricted } from './AuthContext.jsx'
import Layout from './components/Layout.jsx'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'

// Selten genutzte / grosse Seiten erst bei Bedarf nachladen (Code-Splitting).
// Das verkuerzt den ersten Start spuerbar, gerade auf aelteren Tablets.
const ArticleForm = lazy(() => import('./pages/ArticleForm.jsx'))
const BulkArticleForm = lazy(() => import('./pages/BulkArticleForm.jsx'))
const ArticleDetail = lazy(() => import('./pages/ArticleDetail.jsx'))
const OpenIssues = lazy(() => import('./pages/OpenIssues.jsx'))
const Persons = lazy(() => import('./pages/Persons.jsx'))
const MyArticles = lazy(() => import('./pages/MyArticles.jsx'))
const MaterialScan = lazy(() => import('./pages/MaterialScan.jsx'))
const TypeSummary = lazy(() => import('./pages/TypeSummary.jsx'))
const ImportPage = lazy(() => import('./pages/ImportPage.jsx'))
const Settings = lazy(() => import('./pages/Settings.jsx'))
const Account = lazy(() => import('./pages/Account.jsx'))
const AccessSheet = lazy(() => import('./pages/AccessSheet.jsx'))
const SystemControl = lazy(() => import('./pages/SystemControl.jsx'))
const Approvals = lazy(() => import('./pages/Approvals.jsx'))
const Inventur = lazy(() => import('./pages/Inventur.jsx'))
const Auswertung = lazy(() => import('./pages/Auswertung.jsx'))

function PageLoading() {
  return <div className="p-8 text-center text-sm text-muted">lädt…</div>
}

function PrivateRoute({ children, roles, caps, bare }) {
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
  if (isRestricted(user)) return <Navigate to="/meine-artikel" replace />
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
      <Route path="/uebersicht-typen" element={<PrivateRoute><TypeSummary /></PrivateRoute>} />
      <Route path="/auswertung" element={<PrivateRoute><Auswertung /></PrivateRoute>} />
      <Route path="/zugang" element={<PrivateRoute roles={['admin']} bare><AccessSheet /></PrivateRoute>} />
      <Route path="/system" element={<PrivateRoute caps={['server_power']}><SystemControl /></PrivateRoute>} />
      <Route path="/settings" element={<PrivateRoute roles={['admin']}><Settings /></PrivateRoute>} />
      <Route path="/account" element={<PrivateRoute><Account /></PrivateRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
    </Suspense>
  )
}
