(function () {
  const form = document.getElementById("pipeline-form");
  const formPanel = document.getElementById("form-panel");
  const resultsPanel = document.getElementById("results-panel");
  const pageRoot = document.getElementById("page-root");
  const mainCard = document.getElementById("main-card");
  const statusEl = document.getElementById("form-status");
  const submitBtn = document.getElementById("submit-btn");
  const newRunBtn = document.getElementById("new-run-btn");
  const resultsBanner = document.getElementById("results-banner");
  const summaryText = document.getElementById("summary-text");
  const summarySection = document.getElementById("summary-section");
  const notionSection = document.getElementById("notion-section");
  const notionLinkCards = document.getElementById("notion-link-cards");
  const calendarSection = document.getElementById("calendar-section");
  const calendarLinkCards = document.getElementById("calendar-link-cards");

  const API_BASE =
    typeof window !== "undefined" &&
    window.API_BASE !== undefined &&
    window.API_BASE !== null
      ? String(window.API_BASE).trim()
      : "";

  function setFormStatus(message, kind) {
    if (!statusEl) return;
    statusEl.textContent = message;
    statusEl.classList.remove("is-error", "is-ok", "is-wait");
    if (kind) statusEl.classList.add(kind);
  }

  function escapeHtml(s) {
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function linkCard(href, title, subtitle, variant) {
    const v = variant ? ` link-card--${variant}` : "";
    return (
      `<article class="link-card${v}">` +
      `<h3 class="link-card-title">${escapeHtml(title)}</h3>` +
      (subtitle
        ? `<p class="link-card-sub">${escapeHtml(subtitle)}</p>`
        : "") +
      `<div class="link-card-actions">` +
      `<a class="link-card-btn" href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">Open</a>` +
      `<a class="link-card-btn link-card-btn--ghost" href="${escapeHtml(href)}" target="_blank" rel="noopener noreferrer">New tab</a>` +
      `</div></article>`
    );
  }

  function showFormView() {
    if (formPanel) formPanel.classList.remove("hidden");
    if (resultsPanel) resultsPanel.classList.add("hidden");
    if (pageRoot) pageRoot.classList.remove("page--results");
    if (mainCard) mainCard.classList.remove("card--results");
    setFormStatus("", null);
  }

  function showResultsView(body) {
    if (formPanel) formPanel.classList.add("hidden");
    if (resultsPanel) resultsPanel.classList.remove("hidden");
    if (pageRoot) pageRoot.classList.add("page--results");
    if (mainCard) mainCard.classList.add("card--results");

    const ok =
      body &&
      body.status === "success" &&
      (!body.error || body.error === "");

    if (resultsBanner) {
      resultsBanner.classList.remove(
        "results-banner--ok",
        "results-banner--err"
      );
      if (ok) {
        resultsBanner.textContent = "Pipeline completed successfully.";
        resultsBanner.classList.add("results-banner--ok");
      } else {
        resultsBanner.textContent =
          body && body.status === "error"
            ? "Pipeline reported an error — see summary below."
            : "Request finished with issues — see below.";
        resultsBanner.classList.add("results-banner--err");
      }
    }

    const summary =
      (body && body.outcome && body.outcome.summary) ||
      (body && body.error) ||
      "";
    if (summaryText) {
      summaryText.innerHTML = escapeHtml(summary).replace(/\n/g, "<br />");
    }
    if (summarySection) {
      summarySection.classList.toggle("hidden", !String(summary).trim());
    }

    if (notionLinkCards) notionLinkCards.innerHTML = "";
    if (notionSection) notionSection.classList.add("hidden");

    const n = body && body.notion;
    if (n && notionLinkCards && notionSection) {
      const cards = [];
      if (n.run_page_url) {
        cards.push(
          linkCard(
            n.run_page_url,
            "This run — Notion page",
            "Tasks, Kanban DB, and notes for this pipeline run.",
            "notion"
          )
        );
      }
      if (n.hub_page_url) {
        cards.push(
          linkCard(
            n.hub_page_url,
            "Runs hub",
            "Parent workspace; all run pages live under here.",
            "notion-secondary"
          )
        );
      }
      if (n.kanban_database_id) {
        const dbUrl = `https://www.notion.so/${String(n.kanban_database_id).replace(/-/g, "")}`;
        cards.push(
          linkCard(
            dbUrl,
            "This run — Kanban database",
            "Per-run task board (when NOTION_RUN_USE_KANBAN_DB=1).",
            "notion-secondary"
          )
        );
      }
      if (cards.length) {
        notionLinkCards.innerHTML = cards.join("");
        notionSection.classList.remove("hidden");
      }
    }

    if (calendarLinkCards) calendarLinkCards.innerHTML = "";
    if (calendarSection) calendarSection.classList.add("hidden");
    const cals = body && body.calendar_event_links;
    if (Array.isArray(cals) && cals.length && calendarLinkCards && calendarSection) {
      calendarLinkCards.innerHTML = cals
        .map(function (url, i) {
          return linkCard(
            url,
            "Calendar event " + (i + 1),
            "Google Calendar — Deep Work block from this run.",
            "calendar"
          );
        })
        .join("");
      calendarSection.classList.remove("hidden");
    }
  }

  if (newRunBtn) {
    newRunBtn.addEventListener("click", showFormView);
  }

  if (!form || !statusEl || !submitBtn) return;

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    setFormStatus("", null);

    const prompt = document.getElementById("description")?.value?.trim() ?? "";
    const deadline = document.getElementById("deadline")?.value ?? "";
    const project_key =
      document.getElementById("project-key")?.value?.trim() ?? "";

    if (!prompt) {
      setFormStatus("Please enter a project description.", "is-error");
      return;
    }
    if (!deadline) {
      setFormStatus("Please choose a deadline date.", "is-error");
      return;
    }
    if (!project_key) {
      setFormStatus("Please enter a project key.", "is-error");
      return;
    }

    const base = API_BASE.replace(/\/$/, "");
    const url = base ? `${base}/trigger-pipeline` : "/trigger-pipeline";
    submitBtn.disabled = true;
    setFormStatus("Running pipeline — this can take several minutes…", "is-wait");

    try {
      const res = await fetch(url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, deadline, project_key }),
      });

      const text = await res.text();
      let body;
      try {
        body = text ? JSON.parse(text) : {};
      } catch {
        body = { raw: text, status: "error", error: "Invalid JSON response" };
      }

      showResultsView(body);

      if (!res.ok) {
        setFormStatus(`HTTP ${res.status} — see results below.`, "is-error");
      } else if (body.status === "error") {
        setFormStatus("Error status in response — see results below.", "is-error");
      } else {
        setFormStatus("", null);
      }
    } catch (err) {
      const errBody = {
        status: "error",
        error: String(err.message || err),
      };
      showResultsView(errBody);
      setFormStatus(
        "Network error — is the server running?",
        "is-error"
      );
    } finally {
      submitBtn.disabled = false;
    }
  });
})();
