import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api.js'
import { useAuth } from '../AuthContext.jsx'
import DamageReportButton from '../components/DamageReportButton.jsx'

export default function MyArticles() {
  const { user } = useAuth()
  const [issues, setIssues] = useState(null)
  const [error, setError] = useState('')

  const load = () => api.get('/issues/mine').then(setIssues).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-bold">Meine Artikel</h1>
      <p className="text-sm text-gray-500">
        Artikel, die aktuell an dich ({user?.full_name || user?.username}) ausgegeben sind.
      </p>

      {error && <p className="text-sm text-red-600">{error}</p>}

      {!user?.person_id ? (
        <div className="bg-white rounded-xl p-4 text-sm text-gray-500">
          Dein Benutzerkonto ist noch keiner Person zugeordnet. Bitte einen Administrator bitten,
          dein Konto unter "Einstellungen → Benutzer" mit deinem Personendatensatz zu verknüpfen,
          damit hier deine ausgegebenen Artikel angezeigt werden können.
        </div>
      ) : !issues ? (
        <p className="text-sm text-gray-500">Lade...</p>
      ) : (
        <div className="bg-white rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-100 text-left">
              <tr>
                <th className="p-2">Artikelnr.</th>
                <th className="p-2 hidden md:table-cell">Typ</th>
                <th className="p-2 hidden md:table-cell">Größe</th>
                <th className="p-2">Ausgegeben am</th>
                <th className="p-2"></th>
              </tr>
            </thead>
            <tbody>
              {issues.map((i) => (
                <tr key={i.id} className="border-t hover:bg-gray-50">
                  <td className="p-2">
                    <Link className="text-drk-red font-medium" to={`/articles/${i.article_id}`}>{i.artikelnummer}</Link>
                  </td>
                  <td className="p-2 hidden md:table-cell">{i.type_name || '–'}</td>
                  <td className="p-2 hidden md:table-cell">{i.size || '–'}</td>
                  <td className="p-2">{new Date(i.issue_date).toLocaleDateString('de-DE')}</td>
                  <td className="p-2 text-right">
                    <DamageReportButton articleId={i.article_id} onDone={load}
                      className="text-red-600 text-xs underline" />
                  </td>
                </tr>
              ))}
              {issues.length === 0 && (
                <tr><td colSpan={5} className="p-4 text-center text-gray-400">Aktuell keine Artikel ausgegeben</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
