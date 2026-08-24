type EventCallback = (type: string, data: any) => void;

class WebSocketClient {
  private socket: WebSocket | null = null;
  private baseUrl = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';
  private currentBbox: [number, number, number, number] | null = null;
  private listeners: EventCallback[] = [];
  private onReconnectCallbacks: Array<() => void> = [];
  private isConnected = false;
  private reconnectAttempts = 0;
  private maxReconnectDelay = 30000;
  private token: string | null = null;

  public connect(authToken?: string) {
    if (authToken) {
      this.token = authToken;
    }

    if (this.socket && (this.socket.readyState === WebSocket.CONNECTING || this.socket.readyState === WebSocket.OPEN)) {
      return;
    }

    const wsUrl = this.token ? `${this.baseUrl}?token=${encodeURIComponent(this.token)}` : this.baseUrl;

    try {
      this.socket = new WebSocket(wsUrl);

      this.socket.onopen = () => {
        console.log('WebSocket connected to ROADSentinel Real-time Layer');
        const wasReconnect = this.reconnectAttempts > 0;
        this.isConnected = true;
        this.reconnectAttempts = 0;

        // Re-subscribe to bounding box if present
        if (this.currentBbox) {
          this.subscribeBbox(this.currentBbox);
        }

        // Phase 7: Trigger reconnect reconciliation callbacks
        if (wasReconnect) {
          this.onReconnectCallbacks.forEach((cb) => cb());
        }
      };

      this.socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          this.listeners.forEach((listener) => listener(message.type, message.event || message));
        } catch (err) {
          console.error('Failed to parse WebSocket message', err);
        }
      };

      this.socket.onclose = () => {
        this.isConnected = false;
        console.warn('WebSocket connection closed. Attempting reconnect with exponential backoff...');
        this.scheduleReconnect();
      };

      this.socket.onerror = (error) => {
        console.error('WebSocket error:', error);
      };
    } catch (err) {
      console.error('Error initializing WebSocket:', err);
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect() {
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), this.maxReconnectDelay);
    this.reconnectAttempts++;
    setTimeout(() => this.connect(), delay);
  }

  public subscribeBbox(bbox: [number, number, number, number]) {
    this.currentBbox = bbox;
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      const msg = {
        type: 'subscribe',
        bbox: bbox,
      };
      this.socket.send(JSON.stringify(msg));
    }
  }

  public addListener(cb: EventCallback) {
    this.listeners.push(cb);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== cb);
    };
  }

  public onReconnect(cb: () => void) {
    this.onReconnectCallbacks.push(cb);
    return () => {
      this.onReconnectCallbacks = this.onReconnectCallbacks.filter((c) => c !== cb);
    };
  }

  public getStatus(): boolean {
    return this.isConnected;
  }
}

export const wsClient = new WebSocketClient();
