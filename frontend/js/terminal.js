/**
 * Terminal manager using xterm.js
 */
class TerminalManager {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.terminal = null;
        this.fitAddon = null;
        this.ws = null;
        this.projectId = null;
        this.isRunning = false;
        this.connectionId = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 3;
        this.reconnectDelay = 1000;
        this.lastSelection = '';  // Сохраняем выделение для Ctrl+C
    }

    init() {
        // Create terminal
        this.terminal = new Terminal({
            cursorBlink: true,
            cursorStyle: 'bar',
            fontSize: 14,
            fontFamily: "'Cascadia Code', 'Fira Code', Consolas, monospace",
            theme: {
                background: '#1a1b26',
                foreground: '#c0caf5',
                cursor: '#c0caf5',
                cursorAccent: '#1a1b26',
                selection: 'rgba(122, 162, 247, 0.3)',
                black: '#414868',
                red: '#f7768e',
                green: '#9ece6a',
                yellow: '#e0af68',
                blue: '#7aa2f7',
                magenta: '#bb9af7',
                cyan: '#7dcfff',
                white: '#c0caf5',
                brightBlack: '#565f89',
                brightRed: '#f7768e',
                brightGreen: '#9ece6a',
                brightYellow: '#e0af68',
                brightBlue: '#7aa2f7',
                brightMagenta: '#bb9af7',
                brightCyan: '#7dcfff',
                brightWhite: '#c0caf5'
            }
        });

        // Addons
        this.fitAddon = new FitAddon.FitAddon();
        this.terminal.loadAddon(this.fitAddon);

        const webLinksAddon = new WebLinksAddon.WebLinksAddon();
        this.terminal.loadAddon(webLinksAddon);

        // Open terminal
        this.terminal.open(this.container);
        this.fit();

        // Сохраняем выделение при изменении (для Ctrl+C)
        this.terminal.onSelectionChange(() => {
            this.lastSelection = this.terminal.getSelection();
        });

        // Handle resize
        window.addEventListener('resize', () => this.fit());

        // Handle input
        this.terminal.onData(data => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'input',
                    data: data
                }));
            }
        });

        // Handle Ctrl+C (copy) and Ctrl+V (paste)
        this.terminal.attachCustomKeyEventHandler((e) => {
            // Ctrl+C - copy if there's selection, otherwise send to terminal
            if (e.ctrlKey && e.key === 'c' && e.type === 'keydown') {
                // Используем сохранённое выделение (Ctrl сбрасывает его до события)
                if (this.lastSelection) {
                    navigator.clipboard.writeText(this.lastSelection).then(() => {
                        this.terminal.clearSelection();
                        this.lastSelection = '';
                    });
                    return false; // Prevent default
                }
                // No selection - let it pass through as Ctrl+C to terminal
                return true;
            }

            // Ctrl+V - paste
            if (e.ctrlKey && e.key === 'v' && e.type === 'keydown') {
                navigator.clipboard.readText().then(text => {
                    if (text && this.ws && this.ws.readyState === WebSocket.OPEN) {
                        this.ws.send(JSON.stringify({
                            type: 'input',
                            data: text
                        }));
                    }
                }).catch(() => {});  // Игнорируем ошибки доступа к clipboard
                return false; // Prevent default
            }

            // Ctrl+A - select all
            if (e.ctrlKey && e.key === 'a' && e.type === 'keydown') {
                this.terminal.selectAll();
                return false;
            }

            return true;
        });

        // Welcome message
        this.terminal.writeln('\x1b[1;34m=== Airganizator ===\x1b[0m');
        this.terminal.writeln('Select a project from the sidebar to start.');
        this.terminal.writeln('');
    }

    fit() {
        if (this.fitAddon) {
            this.fitAddon.fit();
            // Send resize to server
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({
                    type: 'resize',
                    cols: this.terminal.cols,
                    rows: this.terminal.rows
                }));
            }
        }
    }

    connect(projectId) {
        // Disconnect previous
        this.disconnect();

        this.projectId = projectId;
        this.hasHistory = false;
        this.reconnectAttempts = 0;

        // Generate unique connection ID to prevent race conditions
        this.connectionId = Date.now() + Math.random();
        const currentConnectionId = this.connectionId;

        // Clear terminal
        this.terminal.clear();

        // Connect WebSocket
        const wsUrl = `ws://${window.location.host}/api/terminal/${projectId}`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            // Ignore if connection changed
            if (this.connectionId !== currentConnectionId) return;
            this.reconnectAttempts = 0;
            this.fit();
        };

        this.ws.onmessage = (event) => {
            // Ignore messages from old connections
            if (this.connectionId !== currentConnectionId) return;

            const msg = JSON.parse(event.data);

            if (msg.type === 'output') {
                this.terminal.write(msg.data);
            } else if (msg.type === 'history') {
                // Очищаем и показываем историю
                this.terminal.clear();
                // Фильтруем служебные escape-последовательности
                const cleaned = msg.data
                    .replace(/\x1b\[\?1;2c/g, '')  // Device attributes response
                    .replace(/\x1b\[[\?0-9;]*[a-zA-Z]/g, (match) => {
                        // Сохраняем цвета и форматирование, убираем служебные
                        if (/\x1b\[[0-9;]*m/.test(match)) return match; // colors
                        if (/\x1b\[[0-9]*[ABCD]/.test(match)) return match; // cursor movement
                        if (/\x1b\[[0-9]*[JK]/.test(match)) return match; // clear
                        return '';
                    });
                this.terminal.write(cleaned);
                this.hasHistory = true;
            } else if (msg.type === 'status') {
                this.isRunning = msg.running;
                this.onStatusChange(msg.running);
            } else if (msg.type === 'llm_status') {
                // LLM typing/idle status
                this.onLLMStatus(this.projectId, msg.status);
            }
        };

        this.ws.onclose = (event) => {
            // Ignore if connection changed
            if (this.connectionId !== currentConnectionId) return;

            this.isRunning = false;
            this.onStatusChange(false);

            // Don't reconnect if closed normally or max attempts reached
            if (event.code === 1000 || this.reconnectAttempts >= this.maxReconnectAttempts) {
                this.terminal.writeln('');
                this.terminal.writeln('\x1b[1;31mDisconnected\x1b[0m');
                this.reconnectAttempts = 0;
                return;
            }

            // Auto-reconnect with backoff
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * this.reconnectAttempts;
            this.terminal.writeln('');
            this.terminal.writeln(`\x1b[1;33mConnection lost. Reconnecting in ${delay/1000}s...\x1b[0m`);

            setTimeout(() => {
                // Only reconnect if still on same project
                if (this.projectId === projectId && this.connectionId === currentConnectionId) {
                    this.connect(projectId);
                }
            }, delay);
        };

        this.ws.onerror = (error) => {
            // Ignore if connection changed
            if (this.connectionId !== currentConnectionId) return;
            this.terminal.writeln(`\x1b[1;31mWebSocket error\x1b[0m`);
            console.error('WebSocket error:', error);
        };
    }

    disconnect() {
        // Prevent auto-reconnect
        this.reconnectAttempts = this.maxReconnectAttempts;
        this.connectionId = null;

        if (this.ws) {
            this.ws.close(1000);  // Normal closure code
            this.ws = null;
        }
        this.projectId = null;
        this.isRunning = false;
    }

    start() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.terminal.clear();
            this.terminal.writeln('\x1b[1;33mStarting process...\x1b[0m');
            this.terminal.writeln('');
            this.ws.send(JSON.stringify({ type: 'start' }));
        }
    }

    stop() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'stop' }));
            this.terminal.writeln('');
            this.terminal.writeln('\x1b[1;31mProcess stopped\x1b[0m');
        }
    }

    // Override this to handle status changes
    onStatusChange(running) {
        // To be overridden by app.js
    }

    // Override this to handle LLM typing/idle status
    onLLMStatus(projectId, status) {
        // To be overridden by app.js
    }

    focus() {
        if (this.terminal) {
            this.terminal.focus();
        }
    }

    clear() {
        if (this.terminal) {
            this.terminal.clear();
        }
    }
}
