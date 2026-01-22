/**
 * Main application logic
 */
document.addEventListener('DOMContentLoaded', () => {
    // State
    let projects = [];
    let currentProject = null;
    let settings = {};
    let draggedCard = null;
    let statusPollInterval = null;

    // Elements
    const projectsList = document.getElementById('projects-list');
    const terminalManager = new TerminalManager('terminal');
    const consoleManager = new ConsoleManager('console');
    const sidebar = document.getElementById('sidebar');
    const mainArea = document.querySelector('.main');
    const searchInput = document.getElementById('project-search');
    const btnCollapse = document.getElementById('btn-collapse-sidebar');
    const btnExpand = document.getElementById('btn-expand-sidebar');
    let activeTab = 'llm'; // 'llm' or 'console'

    // Restore sidebar state
    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        sidebar.classList.add('collapsed');
        mainArea.classList.add('sidebar-collapsed');
    }

    // Modals
    const modalProject = document.getElementById('modal-project');
    const modalSettings = document.getElementById('modal-settings');
    const modalEnv = document.getElementById('modal-env');

    // Initialize
    terminalManager.init();
    consoleManager.init();
    loadProjects();
    loadSettings();

    // Start status polling for all projects
    startStatusPolling();

    // Console status handler
    consoleManager.onStatusChange = (running) => {
        // Update button states when on console tab
        if (activeTab === 'console') {
            document.getElementById('btn-start').disabled = running;
            document.getElementById('btn-stop').disabled = !running;

            const status = document.getElementById('terminal-status');
            if (running) {
                status.textContent = 'Console Running';
                status.classList.add('running');
            } else {
                status.textContent = 'Console Stopped';
                status.classList.remove('running');
            }
        }
    };

    // Terminal tabs
    document.querySelectorAll('.terminal-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;
            if (tabName === activeTab) return;

            activeTab = tabName;

            // Update tab UI
            document.querySelectorAll('.terminal-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Update terminal panes
            document.querySelectorAll('.terminal-pane').forEach(p => p.classList.remove('active'));
            document.getElementById(tabName === 'llm' ? 'terminal' : 'console').classList.add('active');

            // Fit the active terminal
            if (tabName === 'llm') {
                terminalManager.fit();
                updateButtonsForLLM();
            } else {
                consoleManager.fit();
                updateButtonsForConsole();
            }
        });
    });

    function updateButtonsForLLM() {
        const running = terminalManager.isRunning;
        document.getElementById('btn-start').disabled = running;
        document.getElementById('btn-stop').disabled = !running;

        const status = document.getElementById('terminal-status');
        if (running) {
            status.textContent = 'Running';
            status.classList.add('running');
        } else {
            status.textContent = 'Stopped';
            status.classList.remove('running');
        }
    }

    function updateButtonsForConsole() {
        const running = consoleManager.isRunning;
        document.getElementById('btn-start').disabled = running;
        document.getElementById('btn-stop').disabled = !running;

        const status = document.getElementById('terminal-status');
        if (running) {
            status.textContent = 'Console Running';
            status.classList.add('running');
        } else {
            status.textContent = 'Console Stopped';
            status.classList.remove('running');
        }
    }

    // Handle terminal status changes
    terminalManager.onStatusChange = (running) => {
        // Only update UI if LLM tab is active
        if (activeTab === 'llm') {
            document.getElementById('btn-start').disabled = running;
            document.getElementById('btn-stop').disabled = !running;

            const status = document.getElementById('terminal-status');
            if (running) {
                status.textContent = 'Running';
                status.classList.add('running');
            } else {
                status.textContent = 'Stopped';
                status.classList.remove('running');
            }
        }

        // Update project card status
        if (currentProject) {
            const card = document.querySelector(`.project-card[data-id="${currentProject.id}"]`);
            if (card) {
                const statusDot = card.querySelector('.project-status');
                if (running) {
                    statusDot.classList.add('running');
                } else {
                    statusDot.classList.remove('running');
                }
            }
        }
    };

    // Handle LLM typing/idle status
    terminalManager.onLLMStatus = (projectId, status) => {
        const card = document.querySelector(`.project-card[data-id="${projectId}"]`);
        if (!card) return;

        if (status === 'typing') {
            card.classList.add('typing');
            card.classList.remove('has-response');
        } else if (status === 'idle') {
            card.classList.remove('typing');
            // Подсвечиваем зелёным только если это НЕ активный проект
            if (!currentProject || currentProject.id !== projectId) {
                card.classList.add('has-response');
            }
        }
    };

    // Load projects
    async function loadProjects() {
        try {
            projects = await API.getProjects();
            // Apply saved order
            const savedOrder = localStorage.getItem('projectsOrder');
            if (savedOrder) {
                const orderMap = JSON.parse(savedOrder);
                projects.sort((a, b) => {
                    const orderA = orderMap[a.id] ?? 999;
                    const orderB = orderMap[b.id] ?? 999;
                    return orderA - orderB;
                });
            }
            renderProjects();
        } catch (err) {
            console.error('Failed to load projects:', err);
        }
    }

    // Save projects order
    function saveProjectsOrder() {
        const orderMap = {};
        projects.forEach((p, idx) => {
            orderMap[p.id] = idx;
        });
        localStorage.setItem('projectsOrder', JSON.stringify(orderMap));
    }

    // Render projects list
    function renderProjects() {
        if (projects.length === 0) {
            projectsList.innerHTML = `
                <div class="empty-state">
                    <div class="empty-state-icon">📁</div>
                    <p>No projects yet</p>
                    <p>Click "Add Project" to get started</p>
                </div>
            `;
            return;
        }

        projectsList.innerHTML = projects.map(p => `
            <div class="project-card ${currentProject?.id === p.id ? 'active' : ''}" data-id="${p.id}" draggable="true">
                <div class="drag-handle"><span></span><span></span><span></span></div>
                <div class="project-card-header">
                    <span class="project-name">${escapeHtml(p.name)}</span>
                    <span class="project-status ${p.running ? 'running' : ''}"></span>
                </div>
                <div class="project-meta">
                    <span class="project-llm">${p.llm}</span>
                    <span class="project-mode ${p.mode}">${p.mode}</span>
                    ${p.git?.has_git ? `
                        <a href="${p.git.web_url || '#'}" target="_blank" class="project-git" title="${p.git.remote_url || 'Git repo'}" onclick="event.stopPropagation()">
                            <span class="git-icon">⎇</span>
                            ${p.git.branch ? `<span class="git-branch">${escapeHtml(p.git.branch)}</span>` : ''}
                        </a>
                    ` : ''}
                </div>
                <div class="project-actions">
                    <button class="btn btn-sm btn-icon" onclick="openFolder('${p.id}')" title="Open folder">📁</button>
                    <button class="btn btn-sm" onclick="editProject('${p.id}')">Edit</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteProject('${p.id}')">Delete</button>
                </div>
            </div>
        `).join('');

        // Add click handlers and drag-drop
        document.querySelectorAll('.project-card').forEach(card => {
            card.addEventListener('click', (e) => {
                if (e.target.tagName === 'BUTTON' || e.target.closest('.drag-handle')) return;
                selectProject(card.dataset.id);
            });

            // Drag start
            card.addEventListener('dragstart', (e) => {
                draggedCard = card;
                card.classList.add('dragging');
                e.dataTransfer.effectAllowed = 'move';
            });

            // Drag end
            card.addEventListener('dragend', () => {
                card.classList.remove('dragging');
                document.querySelectorAll('.project-card').forEach(c => c.classList.remove('drag-over'));
                draggedCard = null;
            });

            // Drag over
            card.addEventListener('dragover', (e) => {
                e.preventDefault();
                if (draggedCard && draggedCard !== card) {
                    card.classList.add('drag-over');
                }
            });

            // Drag leave
            card.addEventListener('dragleave', () => {
                card.classList.remove('drag-over');
            });

            // Drop
            card.addEventListener('drop', (e) => {
                e.preventDefault();
                card.classList.remove('drag-over');

                if (draggedCard && draggedCard !== card) {
                    const draggedId = draggedCard.dataset.id;
                    const targetId = card.dataset.id;

                    const draggedIdx = projects.findIndex(p => p.id === draggedId);
                    const targetIdx = projects.findIndex(p => p.id === targetId);

                    if (draggedIdx !== -1 && targetIdx !== -1) {
                        // Reorder projects array
                        const [removed] = projects.splice(draggedIdx, 1);
                        projects.splice(targetIdx, 0, removed);
                        saveProjectsOrder();
                        renderProjects();
                    }
                }
            });
        });

        // Apply search filter if active
        const searchTerm = searchInput.value.toLowerCase().trim();
        if (searchTerm) {
            filterProjects(searchTerm);
        }
    }

    // Filter projects by search term
    function filterProjects(searchTerm) {
        document.querySelectorAll('.project-card').forEach(card => {
            const name = card.querySelector('.project-name').textContent.toLowerCase();
            const llm = card.querySelector('.project-llm').textContent.toLowerCase();
            if (name.includes(searchTerm) || llm.includes(searchTerm)) {
                card.classList.remove('hidden');
            } else {
                card.classList.add('hidden');
            }
        });
    }

    // Select project
    async function selectProject(id) {
        const project = projects.find(p => p.id === id);
        if (!project) return;

        currentProject = project;

        // Update UI
        document.querySelectorAll('.project-card').forEach(c => c.classList.remove('active'));
        const selectedCard = document.querySelector(`.project-card[data-id="${id}"]`);
        if (selectedCard) {
            selectedCard.classList.add('active');
            selectedCard.classList.remove('has-response'); // Убираем подсветку при выборе
        }

        // Update project name with git info
        const projectNameEl = document.getElementById('current-project-name');
        if (project.git?.has_git && project.git.web_url) {
            projectNameEl.innerHTML = `
                ${escapeHtml(project.name)}
                <a href="${project.git.web_url}" target="_blank" class="header-git-link" title="${project.git.remote_url || 'Git repo'}">
                    ⎇ ${project.git.branch || 'git'}
                </a>
            `;
        } else {
            projectNameEl.textContent = project.name;
        }

        // Update mode buttons
        document.querySelectorAll('.mode-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === project.mode);
        });

        // Connect both terminals
        terminalManager.connect(id);
        consoleManager.connect(id);
    }

    // Add project button
    document.getElementById('btn-add-project').addEventListener('click', () => {
        document.getElementById('modal-project-title').textContent = 'Add Project';
        document.getElementById('project-id').value = '';
        document.getElementById('form-project').reset();
        modalProject.classList.add('active');
    });

    // Edit project
    window.editProject = async (id) => {
        const project = projects.find(p => p.id === id);
        if (!project) return;

        document.getElementById('modal-project-title').textContent = 'Edit Project';
        document.getElementById('project-id').value = project.id;
        document.getElementById('project-name').value = project.name;
        document.getElementById('project-path').value = project.path;
        document.getElementById('project-llm').value = project.llm;
        document.getElementById('project-llm-command').value = project.llm_command || '';
        document.getElementById('project-use-global-key').checked = project.use_global_api_key;

        // Show/hide custom command
        document.getElementById('custom-command-group').style.display =
            project.llm === 'custom' ? 'block' : 'none';

        modalProject.classList.add('active');
    };

    // Open project folder in Explorer
    window.openFolder = async (id) => {
        try {
            await fetch(`/api/projects/${id}/open-folder`, { method: 'POST' });
        } catch (err) {
            console.error('Failed to open folder:', err);
        }
    };

    // Delete project
    window.deleteProject = async (id) => {
        if (!confirm('Delete this project?')) return;

        try {
            await API.deleteProject(id);
            if (currentProject?.id === id) {
                currentProject = null;
                terminalManager.disconnect();
                consoleManager.disconnect();
                document.getElementById('current-project-name').textContent = 'Select a project';
            }
            loadProjects();
        } catch (err) {
            console.error('Failed to delete project:', err);
        }
    };

    // Project form submit
    document.getElementById('form-project').addEventListener('submit', async (e) => {
        e.preventDefault();

        const id = document.getElementById('project-id').value;
        const data = {
            name: document.getElementById('project-name').value,
            path: document.getElementById('project-path').value,
            llm: document.getElementById('project-llm').value,
            llm_command: document.getElementById('project-llm-command').value || null,
            use_global_api_key: document.getElementById('project-use-global-key').checked
        };

        try {
            if (id) {
                await API.updateProject(id, data);
            } else {
                await API.createProject(data);
            }
            modalProject.classList.remove('active');
            loadProjects();
        } catch (err) {
            console.error('Failed to save project:', err);
        }
    });

    // LLM select change
    document.getElementById('project-llm').addEventListener('change', (e) => {
        document.getElementById('custom-command-group').style.display =
            e.target.value === 'custom' ? 'block' : 'none';
    });

    // Mode buttons
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            if (!currentProject) return;

            const mode = btn.dataset.mode;
            try {
                await API.changeMode(currentProject.id, mode);
                currentProject.mode = mode;

                // Update UI
                document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                // Update project card
                const card = document.querySelector(`.project-card[data-id="${currentProject.id}"]`);
                if (card) {
                    const modeSpan = card.querySelector('.project-mode');
                    modeSpan.textContent = mode;
                    modeSpan.className = `project-mode ${mode}`;
                }
            } catch (err) {
                console.error('Failed to change mode:', err);
            }
        });
    });

    // Start/Stop buttons
    document.getElementById('btn-start').addEventListener('click', () => {
        if (currentProject) {
            if (activeTab === 'llm') {
                terminalManager.start();
            } else {
                consoleManager.start();
            }
        }
    });

    document.getElementById('btn-stop').addEventListener('click', () => {
        if (currentProject) {
            if (activeTab === 'llm') {
                terminalManager.stop();
            } else {
                consoleManager.stop();
            }
        }
    });

    // Settings
    document.getElementById('btn-settings').addEventListener('click', () => {
        loadSettings();
        modalSettings.classList.add('active');
    });

    async function loadSettings() {
        try {
            settings = await API.getSettings();
            document.getElementById('settings-base-path').value = settings.base_projects_path || '';
            document.getElementById('settings-default-llm').value = settings.default_llm || 'claude';
            document.getElementById('settings-default-mode').value = settings.default_mode || 'development';
        } catch (err) {
            console.error('Failed to load settings:', err);
        }
    }

    // Settings tabs
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            document.querySelectorAll('.tab-content').forEach(c => {
                c.style.display = 'none';
                c.classList.remove('active');
            });

            const tabContent = document.getElementById(`tab-${tab.dataset.tab}`);
            tabContent.style.display = 'block';
            tabContent.classList.add('active');
        });
    });

    // Save settings
    document.getElementById('btn-save-settings').addEventListener('click', async () => {
        try {
            // Save general settings
            await API.updateSettings({
                base_projects_path: document.getElementById('settings-base-path').value,
                default_llm: document.getElementById('settings-default-llm').value,
                default_mode: document.getElementById('settings-default-mode').value
            });

            // Save API keys if changed
            const anthropicKey = document.getElementById('api-key-anthropic').value;
            const openaiKey = document.getElementById('api-key-openai').value;
            const googleKey = document.getElementById('api-key-google').value;

            if (anthropicKey || openaiKey || googleKey) {
                const apiKeys = {};
                if (anthropicKey) apiKeys.anthropic = anthropicKey;
                if (openaiKey) apiKeys.openai = openaiKey;
                if (googleKey) apiKeys.google = googleKey;
                await API.updateApiKeys(apiKeys);
            }

            modalSettings.classList.remove('active');
        } catch (err) {
            console.error('Failed to save settings:', err);
        }
    });

    // .env editor
    document.getElementById('btn-env').addEventListener('click', async () => {
        if (!currentProject) return;

        try {
            const env = await API.getEnv(currentProject.id);
            document.getElementById('env-project-name').textContent = currentProject.name;
            document.getElementById('env-path').textContent = env.path || `${currentProject.path}/.env`;
            document.getElementById('env-content').value = env.content || '';
            modalEnv.classList.add('active');
        } catch (err) {
            console.error('Failed to load .env:', err);
        }
    });

    document.getElementById('btn-save-env').addEventListener('click', async () => {
        if (!currentProject) return;

        try {
            const content = document.getElementById('env-content').value;
            await API.updateEnv(currentProject.id, content);
            modalEnv.classList.remove('active');
        } catch (err) {
            console.error('Failed to save .env:', err);
        }
    });

    // Modal close handlers
    document.getElementById('modal-project-close').addEventListener('click', () => {
        modalProject.classList.remove('active');
    });
    document.getElementById('btn-cancel-project').addEventListener('click', () => {
        modalProject.classList.remove('active');
    });
    document.getElementById('modal-settings-close').addEventListener('click', () => {
        modalSettings.classList.remove('active');
    });
    document.getElementById('modal-env-close').addEventListener('click', () => {
        modalEnv.classList.remove('active');
    });
    document.getElementById('btn-cancel-env').addEventListener('click', () => {
        modalEnv.classList.remove('active');
    });

    // Close modal on backdrop click
    [modalProject, modalSettings, modalEnv].forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.remove('active');
            }
        });
    });

    // Search projects
    searchInput.addEventListener('input', (e) => {
        const searchTerm = e.target.value.toLowerCase().trim();
        filterProjects(searchTerm);
    });

    // Clear search on Escape
    searchInput.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            searchInput.value = '';
            filterProjects('');
        }
    });

    // ==================== ZEUSOVICH TERMINAL ====================
    const zeusovichPanel = document.getElementById('zeusovich-panel');
    const btnZeusovich = document.getElementById('btn-zeusovich');
    const btnZeusovichStart = document.getElementById('btn-zeusovich-start');
    const btnZeusovichStop = document.getElementById('btn-zeusovich-stop');
    const btnZeusovichRestart = document.getElementById('btn-zeusovich-restart');
    const zeusovichClose = document.getElementById('zeusovich-close');
    const zeusovichWarning = document.getElementById('zeusovich-warning');
    const zeusovichWarningText = document.getElementById('zeusovich-warning-text');

    // Initialize Zeusovich terminal
    const zeusovichManager = new ZeusovichManager('zeusovich-terminal');

    // Status change handler
    const baseOnStatusChange = zeusovichManager.onStatusChange.bind(zeusovichManager);
    zeusovichManager.onStatusChange = (running) => {
        baseOnStatusChange(running);
        btnZeusovichStart.disabled = running;
        btnZeusovichStop.disabled = !running;

        // Hide warning and restart button when stopped
        if (!running) {
            zeusovichWarning.style.display = 'none';
            btnZeusovichRestart.style.display = 'none';
        }
    };

    // New projects change handler
    zeusovichManager.onNewProjectsChange = (newProjects) => {
        if (newProjects.length > 0) {
            const names = newProjects.map(p => p.name).join(', ');
            zeusovichWarningText.textContent = `New projects added: ${names}. Restart to access.`;
            zeusovichWarning.style.display = 'flex';
            btnZeusovichRestart.style.display = 'inline-block';
        } else {
            zeusovichWarning.style.display = 'none';
            btnZeusovichRestart.style.display = 'none';
        }
    };

    // Open Zeusovich panel
    btnZeusovich.addEventListener('click', () => {
        zeusovichPanel.classList.add('active');
        // Initialize terminal on first open
        if (!zeusovichManager.terminal) {
            zeusovichManager.init();
        }
        setTimeout(() => {
            zeusovichManager.fit();
            zeusovichManager.focus();
        }, 100);
    });

    // Close Zeusovich panel
    zeusovichClose.addEventListener('click', () => {
        zeusovichPanel.classList.remove('active');
    });

    // Start/Stop/Restart buttons
    btnZeusovichStart.addEventListener('click', () => {
        zeusovichManager.start();
    });

    btnZeusovichStop.addEventListener('click', () => {
        zeusovichManager.stop();
    });

    btnZeusovichRestart.addEventListener('click', () => {
        zeusovichManager.stop();
        setTimeout(() => {
            zeusovichManager.start();
        }, 500);
    });

    // Close on Escape
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && zeusovichPanel.classList.contains('active')) {
            zeusovichPanel.classList.remove('active');
        }
    });

    // ==================== END ZEUSOVICH ====================

    // Sidebar collapse/expand
    btnCollapse.addEventListener('click', () => {
        sidebar.classList.add('collapsed');
        mainArea.classList.add('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', 'true');
        // Resize terminals after transition
        setTimeout(() => {
            terminalManager.fit();
            consoleManager.fit();
        }, 300);
    });

    btnExpand.addEventListener('click', () => {
        sidebar.classList.remove('collapsed');
        mainArea.classList.remove('sidebar-collapsed');
        localStorage.setItem('sidebarCollapsed', 'false');
        // Resize terminals after transition
        setTimeout(() => {
            terminalManager.fit();
            consoleManager.fit();
        }, 300);
    });

    // ==================== STATUS POLLING ====================

    function startStatusPolling() {
        // Poll every 2 seconds
        statusPollInterval = setInterval(updateProjectStatuses, 2000);
        // Also run immediately
        updateProjectStatuses();
    }

    async function updateProjectStatuses() {
        try {
            const response = await fetch('/api/projects/running/list');
            const data = await response.json();
            const runningIds = new Set(data.running || []);

            // Update all project cards
            document.querySelectorAll('.project-card').forEach(card => {
                const projectId = card.dataset.id;
                const statusDot = card.querySelector('.project-status');
                if (!statusDot) return;

                const isRunning = runningIds.has(projectId);

                if (isRunning) {
                    statusDot.classList.add('running');
                } else {
                    statusDot.classList.remove('running');
                }
            });

            // Also update projects array
            projects.forEach(p => {
                p.running = runningIds.has(p.id);
            });

        } catch (err) {
            // Silent fail - polling will retry
        }
    }

    // Clean up on page unload
    window.addEventListener('beforeunload', () => {
        if (statusPollInterval) {
            clearInterval(statusPollInterval);
        }
    });

    // ==================== END STATUS POLLING ====================

    // Utility
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
});
