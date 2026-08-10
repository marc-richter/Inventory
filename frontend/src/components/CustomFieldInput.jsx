import React from 'react'

// Eingabe für ein frei definiertes Zusatzfeld je nach Typ.
export default function CustomFieldInput({ field, value, onChange }) {
  const cls = 'w-full border border-line rounded-lg px-2 py-1.5 text-sm'
  const label = (
    <span className="text-xs text-gray-500">{field.label}{field.required ? ' *' : ''}</span>
  )
  if (field.field_type === 'select') {
    return (
      <label className="block">{label}
        <select className={cls} value={value} onChange={(e) => onChange(e.target.value)}>
          <option value="">–</option>
          {(field.options || []).map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      </label>
    )
  }
  if (field.field_type === 'bool') {
    return (
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={value === 'true' || value === true}
          onChange={(e) => onChange(e.target.checked ? 'true' : 'false')} />
        {field.label}{field.required ? ' *' : ''}
      </label>
    )
  }
  const type = field.field_type === 'number' ? 'number' : field.field_type === 'date' ? 'date' : 'text'
  return (
    <label className="block">{label}
      <input type={type} className={cls} value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  )
}
