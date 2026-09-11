type MessageHandler = (data: unknown) => void

interface WSMessage {
  type: string
  action?: string
  room?: string
  [key: string]: unknown
}

class WebSocketService {
  private ws: WebSocket | null = null
  private url: string
  private token: string | null = null
  private handlers: Map<string, Set<MessageHandler>> = new Map()
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 2000

  constructor() {
    this.url = `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/api/v1/system/ws`
  }

  connect(token: string): Promise<void> {
    this.token = token
    return new Promise((resolve, reject) => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        resolve()
        return
      }

      this.ws = new WebSocket(`${this.url}?token=${encodeURIComponent(token)}`)

      this.ws.onopen = () => {
        console.log('[WS] Connected')
        this.reconnectAttempts = 0
        this.emit('open', {})
        resolve()
      }

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          this.emit(data.type, data)
        } catch (e) {
          console.warn('[WS] Invalid message', event.data)
        }
      }

      this.ws.onclose = () => {
        console.log('[WS] Disconnected')
        this.emit('close', {})
        this.attemptReconnect()
      }

      this.ws.onerror = (err) => {
        console.error('[WS] Error', err)
        this.emit('error', err)
        reject(err)
      }
    })
  }

  private attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.log('[WS] Max reconnect attempts reached')
      return
    }
    this.reconnectAttempts++
    setTimeout(() => {
      if (this.token) {
        this.connect(this.token).catch(() => {})
      }
    }, this.reconnectDelay * this.reconnectAttempts)
  }

  disconnect() {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  send(data: WSMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    }
  }

  joinRoom(room: string) {
    this.send({ type: 'action', action: 'join', room })
  }

  leaveRoom(room: string) {
    this.send({ type: 'action', action: 'leave', room })
  }

  ping() {
    this.send({ type: 'action', action: 'ping' })
  }

  on(type: string, handler: MessageHandler) {
    if (!this.handlers.has(type)) {
      this.handlers.set(type, new Set())
    }
    this.handlers.get(type)!.add(handler)
  }

  off(type: string, handler: MessageHandler) {
    this.handlers.get(type)?.delete(handler)
  }

  private emit(type: string, data: unknown) {
    this.handlers.get(type)?.forEach((h) => {
      try {
        h(data)
      } catch (e) {
        console.error('[WS] Handler error', e)
      }
    })
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

export const ws = new WebSocketService()

// React hook for easy usage
import { useEffect, useRef, useState } from 'react'

export function useWebSocket() {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(ws)

  useEffect(() => {
    const token = localStorage.getItem('inventar_token')
    if (!token) return

    wsRef.current.connect(token).then(() => {
      setConnected(true)
    }).catch(() => {
      setConnected(false)
    })

    wsRef.current.on('open', () => setConnected(true))
    wsRef.current.on('close', () => setConnected(false))
    wsRef.current.on('error', () => setConnected(false))

    return () => {
      wsRef.current.off('open', () => setConnected(true))
      wsRef.current.off('close', () => setConnected(false))
      wsRef.current.off('error', () => setConnected(false))
    }
  }, [])

  return {
    connected,
    send: wsRef.current.send.bind(wsRef.current),
    joinRoom: wsRef.current.joinRoom.bind(wsRef.current),
    leaveRoom: wsRef.current.leaveRoom.bind(wsRef.current),
    on: wsRef.current.on.bind(wsRef.current),
    off: wsRef.current.off.bind(wsRef.current),
  }
}

export function useInventoryWebSocket(campaignId: number | null) {
  const { on, off, joinRoom, leaveRoom } = useWebSocket()
  const [updates, setUpdates] = useState<Array<{ type: string; data: unknown }>>([])

  useEffect(() => {
    if (!campaignId) return

    const room = `inventory:${campaignId}`
    joinRoom(room)

    const handler = (data: unknown) => {
      setUpdates((prev) => [...prev.slice(-49), data as { type: string; data: unknown }])
    }

    on('inventory_update', handler)

    return () => {
      leaveRoom(room)
      off('inventory_update', handler)
    }
  }, [campaignId])

  return updates
}

export function useNotifications() {
  const { on, off } = useWebSocket()
  const [notifications, setNotifications] = useState<Array<{ type: string; data: unknown }>>([])

  useEffect(() => {
    const handler = (data: unknown) => {
      setNotifications((prev) => [...prev.slice(-49), data as { type: string; data: unknown }])
    }

    on('notification', handler)

    return () => off('notification', handler)
  }, [])

  return notifications
}