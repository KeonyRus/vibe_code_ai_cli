/**
 * Console manager using xterm.js - plain shell terminal
 */
class ConsoleManager {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.terminal = null;
        this.fitAddon = null;
        this.ws = null;
        this.projectId = null;
        this.isRunning = false;
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
                cursor: '#7dcfff',
                cursorAccent: '#1a1b26',
                selection: 'rgba(125, 207, 255, 0.3)',
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

        // Welcome message
        this.terminal.writeln('\x1b[1;36m=== Console ===\x1b[0m');
        this.terminal.writeln('Select a project to open PowerShell console.');
        this.terminal.writeln('');
    }

    fit() {
        if (this.fitAddon && this.container.offsetWidth > 0) {
            this.fitAddon.fit();
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

        // Clear terminal
        this.terminal.clear();
        this.terminal.writeln('\x1b[1;36mConnecting to console...\x1b[0m');

        // Connect WebSocket
        const wsUrl = `ws://${window.location.host}/api/terminal/console/${projectId}`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            this.fit();
        };

        this.ws.onmessage = (event) => {
            const msg = JSON.parse(event.data);

            if (msg.type === 'output') {
                this.terminal.write(msg.data);
            } else if (msg.type === 'history') {
                this.terminal.clear();
                const cleaned = msg.data
                    .replace(/\x1b\[\?1;2c/g, '')
                    .replace(/\x1b\[[\?0-9;]*[a-zA-Z]/g, (match) => {
                        if (/\x1b\[[0-9;]*m/.test(match)) return match;
                        if (/\x1b\[[0-9]*[ABCD]/.test(match)) return match;
                        if (/\x1b\[[0-9]*[JK]/.test(match)) return match;
                        return '';
                    });
                this.terminal.write(cleaned);
            } else if (msg.type === 'status') {
                this.isRunning = msg.running;
                this.onStatusChange(msg.running);
            }
        };

        this.ws.onclose = () => {
            this.terminal.writeln('');
            this.terminal.writeln('\x1b[1;31mConsole disconnected\x1b[0m');
            this.isRunning = false;
            this.onStatusChange(false);
        };

        this.ws.onerror = (error) => {
            this.terminal.writeln(`\x1b[1;31mWebSocket error\x1b[0m`);
            console.error('Console WebSocket error:', error);
        };
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.projectId = null;
        this.isRunning = false;
    }

    start() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.terminal.clear();
            this.terminal.writeln('\x1b[1;36mStarting PowerShell...\x1b[0m');
            this.terminal.writeln('');
            this.ws.send(JSON.stringify({ type: 'start' }));
        }
    }

    stop() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'stop' }));
            this.terminal.writeln('');
            this.terminal.writeln('\x1b[1;31mConsole stopped\x1b[0m');
        }
    }

    onStatusChange(running) {
        // To be overridden
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
