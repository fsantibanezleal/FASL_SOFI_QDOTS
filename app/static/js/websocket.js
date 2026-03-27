/**
 * WebSocket manager for real-time progress updates.
 *
 * Connects to the SOFI server WebSocket endpoint and dispatches
 * progress events to registered callbacks.
 */

class SOFIWebSocket {
    constructor() {
        this.ws = null;
        this.callbacks = [];
        this.connected = false;
        this.reconnectInterval = 3000;
        this._reconnectTimer = null;
    }

    /**
     * Connect to the WebSocket server.
     */
    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const url = `${protocol}//${window.location.host}/ws`;

        try {
            this.ws = new WebSocket(url);
        } catch (e) {
            console.warn('WebSocket connection failed:', e);
            this._scheduleReconnect();
            return;
        }

        this.ws.onopen = () => {
            this.connected = true;
            console.log('WebSocket connected');
            this._dispatch({ type: 'connection', connected: true });
            if (this._reconnectTimer) {
                clearTimeout(this._reconnectTimer);
                this._reconnectTimer = null;
            }
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this._dispatch(data);
            } catch (e) {
                console.warn('Failed to parse WebSocket message:', e);
            }
        };

        this.ws.onclose = () => {
            this.connected = false;
            console.log('WebSocket disconnected');
            this._dispatch({ type: 'connection', connected: false });
            this._scheduleReconnect();
        };

        this.ws.onerror = (error) => {
            console.warn('WebSocket error:', error);
        };
    }

    /**
     * Register a callback for WebSocket messages.
     * @param {Function} callback - Function receiving message objects.
     */
    onMessage(callback) {
        this.callbacks.push(callback);
    }

    /**
     * Send a ping to keep the connection alive.
     */
    ping() {
        if (this.ws && this.connected) {
            this.ws.send('ping');
        }
    }

    /**
     * Dispatch a message to all registered callbacks.
     */
    _dispatch(data) {
        for (const cb of this.callbacks) {
            try {
                cb(data);
            } catch (e) {
                console.error('WebSocket callback error:', e);
            }
        }
    }

    /**
     * Schedule a reconnection attempt.
     */
    _scheduleReconnect() {
        if (this._reconnectTimer) return;
        this._reconnectTimer = setTimeout(() => {
            this._reconnectTimer = null;
            console.log('Attempting WebSocket reconnect...');
            this.connect();
        }, this.reconnectInterval);
    }

    /**
     * Disconnect and clean up.
     */
    disconnect() {
        if (this._reconnectTimer) {
            clearTimeout(this._reconnectTimer);
            this._reconnectTimer = null;
        }
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.connected = false;
    }
}

// Export singleton
window.sofiWS = new SOFIWebSocket();
