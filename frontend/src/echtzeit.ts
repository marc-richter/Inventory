/**
 * Echtzeitanbindung der Oberflaeche.
 *
 * Bisher hat jede offene Seite im Abstand weniger Sekunden von sich aus
 * nachgefragt, ob sich etwas geaendert hat ("Polling"). Bei mehreren offenen
 * Fenstern bedeutete das dauerhaft Last auf dem Server - auf einem Raspberry Pi
 * deutlich spuerbar - und Aenderungen erschienen trotzdem erst verzoegert.
 *
 * Statt dessen haelt der Browser jetzt EINE Verbindung offen. Der Server meldet
 * darueber nur, DASS sich in einem Bereich etwas geaendert hat (z.B. "artikel");
 * die Seite laedt daraufhin ganz normal ueber die uebliche Schnittstelle nach.
 * Ueber die Verbindung gehen also weder Namen noch Inhalte noch wer etwas getan
 * hat - und beim Nachladen greifen wie immer die eigenen Berechtigungen.
 *
 * Klappt die Verbindung nicht (aeltere Gegenstelle, Firewall, Proxy ohne
 * WebSocket-Unterstuetzung), faellt die Oberflaeche automatisch auf das
 * bisherige regelmaessige Nachfragen zurueck - es geht also nichts verloren.
 */

import { useEffect, useRef, useState } from 'react'

type Ruecklauf = (nachricht: Aenderung) => void

export interface Aenderung {
  typ: string
  bereich: string
  anzahl?: number
  ids?: number[]
}

const ADRESSE = () =>
  `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/system/ws`

const HERZSCHLAG_MS = 25000       // haelt Proxys davon ab, die Leitung zu kappen
const WARTE_MIN_MS = 2000
const WARTE_MAX_MS = 60000

class Echtzeit {
  private verbindung: WebSocket | null = null
  private hoerer = new Map<string, Set<Ruecklauf>>()
  private statusHoerer = new Set<(verbunden: boolean) => void>()
  private versuche = 0
  private herzschlag: ReturnType<typeof setInterval> | null = null
  private nachschlag: ReturnType<typeof setTimeout> | null = null
  private gewollt = false
  private _verbunden = false

  get verbunden(): boolean {
    return this._verbunden
  }

  /** Baut die Verbindung auf. Mehrfachaufrufe sind harmlos. */
  start(): void {
    this.gewollt = true
    if (this.verbindung && (this.verbindung.readyState === WebSocket.OPEN
      || this.verbindung.readyState === WebSocket.CONNECTING)) return
    const token = localStorage.getItem('inventar_token')
    if (!token) return

    let ws: WebSocket
    try {
      ws = new WebSocket(ADRESSE())
    } catch {
      this.spaeterErneut()
      return
    }
    this.verbindung = ws

    ws.onopen = () => {
      // Der Sitzungsschluessel wird bewusst NICHT an die Adresse gehaengt -
      // Adressen landen in Protokollen und im Verlauf. Er geht als erste
      // Nachricht ueber die bereits stehende Verbindung.
      try {
        ws.send(JSON.stringify({ typ: 'anmeldung', token }))
      } catch { /* Verbindung schon wieder zu */ }
    }

    ws.onmessage = (ereignis) => {
      let daten: Aenderung
      try {
        daten = JSON.parse(ereignis.data)
      } catch {
        return
      }
      if (daten.typ === 'bereit') {
        this.versuche = 0
        this.setzeStatus(true)
        return
      }
      if (daten.typ === 'aenderung' && daten.bereich) {
        this.melde(daten.bereich, daten)
        this.melde('*', daten)
      }
    }

    ws.onclose = () => {
      this.setzeStatus(false)
      this.verbindung = null
      if (this.gewollt) this.spaeterErneut()
    }

    ws.onerror = () => {
      // Der Abbruch kommt gleich als onclose - hier nichts weiter tun, damit in
      // der Entwicklerkonsole kein Fehler ohne Folgen stehen bleibt.
    }

    if (this.herzschlag) clearInterval(this.herzschlag)
    this.herzschlag = setInterval(() => {
      if (this.verbindung?.readyState === WebSocket.OPEN) {
        try { this.verbindung.send(JSON.stringify({ typ: 'ping' })) } catch { /* egal */ }
      }
    }, HERZSCHLAG_MS)
  }

  /** Trennt die Verbindung, z.B. beim Abmelden. */
  stop(): void {
    this.gewollt = false
    if (this.nachschlag) { clearTimeout(this.nachschlag); this.nachschlag = null }
    if (this.herzschlag) { clearInterval(this.herzschlag); this.herzschlag = null }
    try { this.verbindung?.close() } catch { /* egal */ }
    this.verbindung = null
    this.setzeStatus(false)
  }

  private spaeterErneut(): void {
    if (!this.gewollt || this.nachschlag) return
    // Wartezeit verdoppeln, damit ein Server ohne WebSocket-Unterstuetzung nicht
    // dauerhaft mit Verbindungsversuchen belegt wird.
    const warte = Math.min(WARTE_MIN_MS * 2 ** this.versuche, WARTE_MAX_MS)
    this.versuche += 1
    this.nachschlag = setTimeout(() => {
      this.nachschlag = null
      this.start()
    }, warte)
  }

  private setzeStatus(verbunden: boolean): void {
    if (this._verbunden === verbunden) return
    this._verbunden = verbunden
    this.statusHoerer.forEach((h) => { try { h(verbunden) } catch { /* egal */ } })
  }

  private melde(bereich: string, daten: Aenderung): void {
    this.hoerer.get(bereich)?.forEach((h) => { try { h(daten) } catch { /* egal */ } })
  }

  /** Meldet sich fuer Aenderungen eines Bereichs an; liefert die Abmeldung zurueck. */
  an(bereich: string, ruecklauf: Ruecklauf): () => void {
    if (!this.hoerer.has(bereich)) this.hoerer.set(bereich, new Set())
    this.hoerer.get(bereich)!.add(ruecklauf)
    return () => { this.hoerer.get(bereich)?.delete(ruecklauf) }
  }

  anStatus(ruecklauf: (verbunden: boolean) => void): () => void {
    this.statusHoerer.add(ruecklauf)
    return () => { this.statusHoerer.delete(ruecklauf) }
  }
}

export const echtzeit = new Echtzeit()

/** True, solange die Echtzeitverbindung steht. */
export function useEchtzeitStatus(): boolean {
  const [verbunden, setVerbunden] = useState(echtzeit.verbunden)
  useEffect(() => echtzeit.anStatus(setVerbunden), [])
  return verbunden
}

/**
 * Ruft `neuLaden` auf, sobald sich im angegebenen Bereich etwas geaendert hat.
 *
 * Zusaetzlich laeuft ein Sicherheitsnetz: steht die Echtzeitverbindung, wird nur
 * noch selten (standardmaessig alle 60 Sekunden) von selbst nachgeladen; steht
 * sie nicht, greift der bisherige kurze Takt. Waehrend das Fenster im
 * Hintergrund ist, passiert nichts - beim Zurueckkehren einmal sofort.
 */
export function useAktualisierung(
  bereich: string,
  neuLaden: () => void,
  optionen: { aktiv?: boolean; taktOhneVerbindung?: number; taktMitVerbindung?: number } = {},
): boolean {
  const { aktiv = true, taktOhneVerbindung = 10000, taktMitVerbindung = 60000 } = optionen
  const verbunden = useEchtzeitStatus()
  const ruecklauf = useRef(neuLaden)
  ruecklauf.current = neuLaden

  useEffect(() => {
    if (!aktiv) return undefined
    const ausloesen = () => { if (!document.hidden) ruecklauf.current() }

    const abmelden = echtzeit.an(bereich, ausloesen)
    const takt = setInterval(ausloesen, verbunden ? taktMitVerbindung : taktOhneVerbindung)
    const beiSichtbar = () => { if (!document.hidden) ruecklauf.current() }
    document.addEventListener('visibilitychange', beiSichtbar)

    return () => {
      abmelden()
      clearInterval(takt)
      document.removeEventListener('visibilitychange', beiSichtbar)
    }
  }, [bereich, aktiv, verbunden, taktMitVerbindung, taktOhneVerbindung])

  return verbunden
}
