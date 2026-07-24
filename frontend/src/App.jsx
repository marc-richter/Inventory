import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth, hasRole, hasCapability } from './AuthContext.jsx'
import Layout from './components/Layout.jsx'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'
import ArticleForm from './pages/ArticleForm.jsx'
import BulkArticleForm from './pages/BulkArticleForm.jsx'
import ArticleDetail from './pages/ArticleDetail.jsx'
import OpenIssues from './pages/OpenIssues.jsx'
import Persons from './pages/Persons.jsx'
import MyArticles from './pages/MyArticles.jsx'
import MaterialScan from './pages/MaterialScan.jsx'
import ImportPage from './pages/ImportPage.jsx'
import Settings from './pages/Settings.jsx'
import Account from './pages/Account.jsx'

function PrivateRoute({ children, roles, caps }) {
  const { user } = useAuth()
  if (!user) return <Navigate to="/login" replace />
  if (roles && !hasRole(user, ...roles)) return <Navigate to="/" replace />
  if (caps && !hasCapability(user, ...caps)) return <Navigate to="/" replace />
  return <Layout>{children}</Layout>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
      <Route path="/articles/new" element={<PrivateRoute caps={['articles']}><ArticleForm /></PrivateRoute>} />
      <Route path="/articles/bulk" element={<PrivateRoute caps={['articles']}><BulkArticleForm /></PrivateRoute>} />
      <Route path="/articles/:id" element={<PrivateRoute><ArticleDetail /></PrivateRoute>} />
      <Route path="/offen" element={<PrivateRoute><OpenIssues /></PrivateRoute>} />
      <Route path="/personen" element={<PrivateRoute caps={['persons']}><Persons /></PrivateRoute>} />
      <Route path="/import" element={<PrivateRoute caps={['export']}><ImportPage /></PrivateRoute>} />
      <Route path="/meine-artikel" element={<PrivateRoute><MyArticles /></PrivateRoute>} />
      <Route path="/scan" element={<PrivateRoute caps={['issues']}><MaterialScan /></PrivateRoute>} />
      <Route path="/settings" element={<PrivateRoute roles={['admin']}><Settings /></PrivateRoute>} />
      <Route path="/account" element={<PrivateRoute><Account /></PrivateRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
