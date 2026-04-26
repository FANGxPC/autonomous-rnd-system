(function () {
  // Elements
  const form = document.getElementById("pipeline-form");
  const resultsPanel = document.getElementById("results-panel");
  const statusEl = document.getElementById("form-status");
  const waitNoteEl = document.getElementById("pipeline-wait-note");
  const submitBtn = document.getElementById("submit-btn");
  const newRunBtn = document.getElementById("new-run-btn");
  const resultsBanner = document.getElementById("results-banner");
  const summaryText = document.getElementById("summary-text");
  const notionSection = document.getElementById("notion-section");
  const notionLinkCards = document.getElementById("notion-link-cards");
  const calendarSection = document.getElementById("calendar-section");
  const calendarLinkCards = document.getElementById("calendar-link-cards");
  const terminalLog = document.getElementById("terminal-log");
  const activeProjectKeyInput = document.getElementById("active-project-key");
  const activeViewName = document.getElementById("active-view-name");
  const executionStatus = document.getElementById("execution-status");

  // Workflow Nodes
  const nodes = {
    receive: document.getElementById("wf-receive"),
    parse: document.getElementById("wf-parse"),
    orchestrate: document.getElementById("wf-orchestrate"),
    research: document.getElementById("wf-research"),
    architect: document.getElementById("wf-architect"),
    synthesize: document.getElementById("wf-synthesize")
  };

  const API_BASE =
    typeof window !== "undefined" &&
    window.API_BASE !== undefined &&
    window.API_BASE !== null
      ? String(window.API_BASE).trim()
      : "";

  // --- Utilities ---
  function getISTTime() {
    return new Intl.DateTimeFormat('en-IN', {
      timeZone: 'Asia/Kolkata',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    }).format(new Date());
  }

  function updateLiveClock() {
    const clockEl = document.getElementById("ist-clock");
    if (clockEl) {
      clockEl.textContent = `${getISTTime()} IST`;
    }
  }
  setInterval(updateLiveClock, 1000);

  function addLog(message, author = "sys") {
    if (!terminalLog) return;
    const entry = document.createElement("div");
    entry.className = "log-entry";
    const time = getISTTime();
    entry.innerHTML = `<span class="log-time">${time}</span> <span class="log-tag tag-${author}">[${author.toUpperCase()}]</span> <span class="log-msg">${message}</span>`;
    terminalLog.appendChild(entry);
    terminalLog.scrollTop = terminalLog.scrollHeight;
  }

  function drawWorkflowLinks() {
    const svg = document.querySelector(".workflow-svg");
    if (!svg) return;

    const getCenter = (el) => {
      const rect = el.getBoundingClientRect();
      const svgRect = svg.getBoundingClientRect();
      return {
        x: rect.left - svgRect.left + rect.width / 2,
        y: rect.top - svgRect.top + rect.height / 2,
        right: rect.right - svgRect.left,
        left: rect.left - svgRect.left
      };
    };

    const drawCurve = (start, end, id) => {
      const path = document.getElementById(id);
      if (!path) return;
      const midX = (start.x + end.x) / 2;
      const d = `M ${start.right} ${start.y} C ${midX} ${start.y}, ${midX} ${end.y}, ${end.left} ${end.y}`;
      path.setAttribute("d", d);
    };

    // Connections
    drawCurve(getCenter(nodes.receive), getCenter(nodes.orchestrate), "link-1");
    drawCurve(getCenter(nodes.parse), getCenter(nodes.orchestrate), "link-2");
    drawCurve(getCenter(nodes.orchestrate), getCenter(nodes.research), "link-3");
    drawCurve(getCenter(nodes.orchestrate), getCenter(nodes.architect), "link-4");
  }

  async function animateWorkflow() {
    const reset = () => {
      Object.values(nodes).forEach(n => n.classList.remove("active", "completed"));
      document.querySelectorAll(".wf-link").forEach(l => l.classList.remove("active"));
    };

    reset();
    if (executionStatus) executionStatus.textContent = "RUNNING";

    const step = async (nodeId, linkId, duration = 1500, logMsg = "", logAuthor = "sys") => {
      const node = nodes[nodeId];
      if (node) node.classList.add("active");
      if (linkId) document.getElementById(linkId)?.classList.add("active");
      
      if (logMsg) {
        addLog(logMsg, logAuthor);
      }
      
      await new Promise(r => setTimeout(r, duration));
      
      if (node) {
        node.classList.remove("active");
        node.classList.add("completed");
      }
    };

    await step("receive", "link-1", 1000, "Intercepting incoming mission parameters...", "sys");
    await step("parse", "link-2", 1000, "NLP Engine parsing intent and extracting scope.", "sys");
    await step("orchestrate", "link-3", 1500, "Allocating tasks to specialized agent network.", "orchestrator");
    await step("research", null, 2000, "Scraping technical docs and competitive data...", "research");
    await step("architect", "link-4", 2000, "Drafting system architecture and verifying constraints...", "tech_lead");
    await step("synthesize", null, 1500, "Synthesizing final artifacts for deployment.", "sys");

    if (executionStatus) executionStatus.textContent = "COMPLETED";
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  // --- Initializers ---
  window.addEventListener("resize", drawWorkflowLinks);
  setTimeout(drawWorkflowLinks, 500);

  const deadlineEl = document.getElementById("deadline");
  if (deadlineEl) {
    const d = new Date();
    const min = d.toISOString().split('T')[0];
    deadlineEl.setAttribute("min", min);
    d.setDate(d.getDate() + 14);
    deadlineEl.value = d.toISOString().split('T')[0];
  }

  // --- Event Listeners ---
  if (form) {
    form.addEventListener("submit", async function (e) {
      e.preventDefault();
      const prompt = document.getElementById("description")?.value?.trim();
      const deadline = document.getElementById("deadline")?.value;
      const project_key = document.getElementById("project-key")?.value?.trim();

      if (!prompt || !deadline || !project_key) {
        if (statusEl) statusEl.textContent = "Parameters required.";
        return;
      }

      if (activeProjectKeyInput) activeProjectKeyInput.value = project_key;
      submitBtn.disabled = true;
      if (waitNoteEl) waitNoteEl.classList.remove("hidden");
      
      addLog(`Initiating R&D sequence: ${project_key}`, "sys");
      animateWorkflow();

      try {
        const res = await fetch(`${API_BASE}/trigger-pipeline`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ prompt, deadline, project_key }),
        });
        const body = await res.json();
        showResultsView(body);
      } catch (err) {
        showResultsView({ status: "error", error: String(err) });
      } finally {
        submitBtn.disabled = false;
        if (waitNoteEl) waitNoteEl.classList.add("hidden");
      }
    });
  }

  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  if (chatForm && chatInput) {
    chatForm.addEventListener("submit", async function(e) {
      e.preventDefault();
      const message = chatInput.value.trim();
      if (!message) return;
      
      chatInput.value = "";
      addLog(`User: ${message}`, "sys");
      addLog("Sending prompt to /refine endpoint...", "orchestrator");
      
      // Mock network delay
      await new Promise(r => setTimeout(r, 1000));
      
      addLog("Refining artifacts based on user feedback.", "tech_lead");
    });
  }

  function showResultsView(body) {
    if (resultsPanel) resultsPanel.classList.remove("hidden");
    if (resultsBanner) {
      resultsBanner.textContent = body.status === "success" ? "Sequence Success" : "Sequence Failed";
      resultsBanner.className = `results-banner results-banner--${body.status === "success" ? "ok" : "err"}`;
    }
    if (summaryText) summaryText.textContent = body.outcome?.summary || body.error || "";
    
    const notionCards = document.getElementById("notion-link-cards");
    if (notionCards && body.notion?.run_page_url) {
      notionCards.innerHTML = `<a href="${body.notion.run_page_url}" target="_blank" class="link-card"><h3 class="link-card-title">Notion Workspace</h3></a>`;
      document.getElementById("notion-section").classList.remove("hidden");
    }
  }

  // Tab switching
  document.querySelectorAll(".nav-item").forEach(btn => {
    btn.addEventListener("click", () => {
      const tab = btn.getAttribute("data-tab");
      document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      document.querySelectorAll(".view-layer").forEach(v => v.classList.add("hidden"));
      document.getElementById(`${tab}-view`).classList.remove("hidden");
      if (activeViewName) {
        activeViewName.textContent = 
          tab === "run-pipeline" ? "Control" : 
          tab === "war-room" ? "Team War-Room" : "Workspace";
      }
      if (tab === "code-explorer") renderFileTree();
      if (tab === "war-room") renderWarRoom();
      if (tab === "run-pipeline") setTimeout(drawWorkflowLinks, 100);
    });
  });

  // --- Mock Data ---
  const MOCK_TEAM_TASKS = [
    { agent: "Tech Lead", title: "System Architecture Design", status: "In Progress", priority: "High" },
    { agent: "Tech Lead", title: "API Endpoint Mapping", status: "Done", priority: "Medium" },
    { agent: "Research Agent", title: "Market Competitor Analysis", status: "Pending", priority: "High" },
    { agent: "Research Agent", title: "Vector DB Benchmarking", status: "In Progress", priority: "Medium" },
    { agent: "Scrum Master", title: "Sprint Planning: Wave 1", status: "Done", priority: "High" },
    { agent: "Scrum Master", title: "Daily Sync Orchestration", status: "In Progress", priority: "Low" }
  ];

  const MOCK_FILES = [
    { name: "src", type: "folder", children: [
      { name: "main.py", type: "file", content: "# Main Entry Point\nprint('System Online')" },
      { name: "agents.py", type: "file", content: "class Agent:\n    pass" }
    ]},
    { name: "docs", type: "folder", children: [
      { name: "README.md", type: "file", content: "# Project Workspace\nThis is the generated project documentation." }
    ]},
    { name: "config.json", type: "file", content: "{\n  \"version\": \"1.0.0\"\n}" }
  ];

  function renderWarRoom() {
    const grid = document.getElementById("war-room-grid");
    if (!grid) return;
    
    // Group tasks by agent
    const grouped = MOCK_TEAM_TASKS.reduce((acc, task) => {
      if (!acc[task.agent]) acc[task.agent] = [];
      acc[task.agent].push(task);
      return acc;
    }, {});

    grid.innerHTML = "";
    
    Object.entries(grouped).forEach(([agent, tasks]) => {
      const column = document.createElement("div");
      column.className = "war-room-column glass-panel";
      
      const header = document.createElement("div");
      header.className = "column-header";
      header.innerHTML = `<h3>${agent}</h3><span class="task-count">${tasks.length} Tasks</span>`;
      column.appendChild(header);

      const taskList = document.createElement("div");
      taskList.className = "task-list";
      
      tasks.forEach(task => {
        const card = document.createElement("div");
        card.className = "task-card";
        card.innerHTML = `
          <div class="task-priority priority-${task.priority.toLowerCase()}">${task.priority}</div>
          <div class="task-title">${task.title}</div>
          <div class="task-status">${task.status}</div>
        `;
        taskList.appendChild(card);
      });
      
      column.appendChild(taskList);
      grid.appendChild(column);
    });
  }

  function renderFileTree() {
    const tree = document.getElementById("file-tree");
    if (!tree) return;
    tree.innerHTML = "";

    function buildNode(item, container, path = "") {
      const el = document.createElement("div");
      el.className = `tree-node ${item.type}`;
      const currentPath = path ? `${path}/${item.name}` : item.name;
      
      if (item.type === "folder") {
        el.innerHTML = `<span class="toggle">📂</span> <span class="node-name">${item.name}</span>`;
        const childrenContainer = document.createElement("div");
        childrenContainer.className = "node-children";
        item.children.forEach(child => buildNode(child, childrenContainer, currentPath));
        el.appendChild(childrenContainer);
      } else {
        el.innerHTML = `<span class="icon">📄</span> <span class="node-name">${item.name}</span>`;
        el.addEventListener("click", () => {
          document.getElementById("active-filename").textContent = item.name;
          document.getElementById("file-path").textContent = `/workspace/${currentPath}`;
          document.getElementById("code-viewer").textContent = item.content;
        });
      }
      container.appendChild(el);
    }

    MOCK_FILES.forEach(file => buildNode(file, tree));
  }

  // Theme Toggle
  const themeToggle = document.getElementById("theme-toggle");
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      document.body.classList.toggle("light-theme");
      const isLight = document.body.classList.contains("light-theme");
      themeToggle.textContent = isLight ? "🌙" : "☀️";
    });
  }

})();
