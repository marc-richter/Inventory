import React, { useRef, useEffect } from 'react'

// Einfaches Unterschriftsfeld: mit Maus/Finger zeichnen; liefert die Unterschrift
// als PNG-DataURL über onChange (beim Loslassen) bzw. leeren String beim Löschen.
export default function SignaturePad({ onChange, label }) {
  const ref = useRef(null)
  const drawing = useRef(false)
  const last = useRef(null)

  useEffect(() => {
    const ctx = ref.current.getContext('2d')
    ctx.lineWidth = 2.2
    ctx.lineCap = 'round'
    ctx.strokeStyle = '#111827'
  }, [])

  function pos(e) {
    const c = ref.current
    const rect = c.getBoundingClientRect()
    const t = e.touches ? e.touches[0] : e
    return { x: (t.clientX - rect.left) * (c.width / rect.width), y: (t.clientY - rect.top) * (c.height / rect.height) }
  }
  function start(e) { e.preventDefault(); drawing.current = true; last.current = pos(e) }
  function move(e) {
    if (!drawing.current) return
    e.preventDefault()
    const ctx = ref.current.getContext('2d')
    const p = pos(e)
    ctx.beginPath(); ctx.moveTo(last.current.x, last.current.y); ctx.lineTo(p.x, p.y); ctx.stroke()
    last.current = p
  }
  function end() {
    if (!drawing.current) return
    drawing.current = false
    onChange && onChange(ref.current.toDataURL('image/png'))
  }
  function clear() {
    const c = ref.current
    c.getContext('2d').clearRect(0, 0, c.width, c.height)
    onChange && onChange('')
  }

  return (
    <div>
      {label && <div className="text-xs text-muted mb-1">{label}</div>}
      <canvas ref={ref} width={500} height={140}
        className="border border-line rounded-lg w-full bg-white"
        style={{ touchAction: 'none' }}
        onMouseDown={start} onMouseMove={move} onMouseUp={end} onMouseLeave={end}
        onTouchStart={start} onTouchMove={move} onTouchEnd={end} />
      <button type="button" onClick={clear} className="text-xs text-muted mt-1">löschen</button>
    </div>
  )
}
