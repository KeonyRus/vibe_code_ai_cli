/**
 * Zeusovich Terminal Manager - Global CLI with access to all projects
 */
class ZeusovichManager {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.terminal = null;
        this.fitAddon = null;
        this.ws = null;
        this.isRunning = false;
        this.newProjects = [];
        this._checkInterval = null;
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
                cursor: '#f7768e',
                cursorAccent: '#1a1b26',
                selection: 'rgba(247, 118, 142, 0.3)',
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
                const selection = this.terminal.getSelection();
                if (selection) {
                    navigator.clipboard.writeText(selection);
                    return false;
                }
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
                });
                return false;
            }

            // Ctrl+A - select all
            if (e.ctrlKey && e.key === 'a' && e.type === 'keydown') {
                this.terminal.selectAll();
                return false;
            }

            return true;
        });

        // Welcome message
        this.terminal.writeln('\x1b[1;35m⚡ Zeusovich - Global CLI ⚡\x1b[0m');
        this.terminal.writeln('\x1b[90mClaude Code с доступом ко всем проектам\x1b[0m');
        this.terminal.writeln('');
        this.terminal.writeln('Press \x1b[1;32m▶ Start\x1b[0m to launch...');
        this.terminal.writeln('');

        // Connect WebSocket
        this.connect();
    }

    fit() {
        if (this.fitAddon && this.container.offsetWidth > 0 && this.container.offsetHeight > 0) {
            try {
                this.fitAddon.fit();
                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({
                        type: 'resize',
                        cols: this.terminal.cols,
                        rows: this.terminal.rows
                    }));
                }
            } catch (e) {
                // Ignore fit errors when panel is hidden
            }
        }
    }

    connect() {
        if (this.ws) {
            this.ws.close();
        }

        const wsUrl = `ws://${window.location.host}/api/zeusovich/terminal`;
        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            setTimeout(() => this.fit(), 100);
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
            this.isRunning = false;
            this.onStatusChange(false);
        };

        this.ws.onerror = (error) => {
            console.error('Zeusovich WebSocket error:', error);
        };
    }

    start() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.terminal.clear();
            this.terminal.writeln('\x1b[1;35m⚡ Starting Zeusovich...\x1b[0m');
            this.terminal.writeln('\x1b[90mLaunching Claude Code in projects directory\x1b[0m');
            this.terminal.writeln('');
            this.ws.send(JSON.stringify({ type: 'start' }));
        }
    }

    stop() {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ type: 'stop' }));
            this.terminal.writeln('');
            this.terminal.writeln('\x1b[1;31mZeusovich stopped\x1b[0m');
        }
    }

    onStatusChange(running) {
        // To be overridden
        if (running) {
            this._startNewProjectsCheck();
        } else {
            this._stopNewProjectsCheck();
            this.newProjects = [];
            this.onNewProjectsChange([]);
        }
    }

    onNewProjectsChange(projects) {
        // To be overridden - called when new projects are detected
    }

    async checkNewProjects() {
        try {
            const status = await API.getZeusovichStatus();
            if (status.new_projects && status.new_projects.length > 0) {
                this.newProjects = status.new_projects;
                this.onNewProjectsChange(status.new_projects);
            }
        } catch (e) {
            console.error('Failed to check zeusovich status:', e);
        }
    }

    _startNewProjectsCheck() {
        // Check every 5 seconds
        this._checkInterval = setInterval(() => this.checkNewProjects(), 5000);
    }

    _stopNewProjectsCheck() {
        if (this._checkInterval) {
            clearInterval(this._checkInterval);
            this._checkInterval = null;
        }
    }

    focus() {
        if (this.terminal) {
            this.terminal.focus();
        }
    }
}
