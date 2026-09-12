"use strict";

// Progressive enhancement only: never store answers or credentials in browser
// storage, and never convert date-only campaign buckets into browser dates.
(() => {
  document.querySelectorAll("time[data-local-instant]").forEach((node) => {
    const date = new Date(node.dateTime);
    if (!Number.isFinite(date.getTime()) || typeof Intl === "undefined") return;
    node.textContent = new Intl.DateTimeFormat("en-US", {
      year: "numeric", month: "short", day: "numeric",
      hour: "numeric", minute: "2-digit", timeZoneName: "short"
    }).format(date);
  });

  const summary = document.querySelector("[data-error-summary]");
  if (summary) {
    summary.focus();
    summary.querySelectorAll('a[href^="#"]').forEach((link) => {
      link.addEventListener("click", (event) => {
        const target = document.getElementById(link.hash.slice(1));
        if (target) { event.preventDefault(); target.focus(); }
      });
    });
  }
  document.querySelectorAll("input, select, textarea").forEach((field) => {
    field.addEventListener("blur", () => {
      if (field.willValidate) {
        field.setAttribute("aria-invalid", String(!field.validity.valid));
      }
    });
  });

  // Optional modules remain ordinary accessible fieldsets without JavaScript.
  // Hidden fields are disabled, not silently copied into submitted data. The
  // server independently rejects stray data for every disabled module.
  document.querySelectorAll("[data-campaign-form]").forEach((form) => {
    form.querySelectorAll("[data-campaign-module]").forEach((group) => {
      const toggle = document.getElementById(group.dataset.campaignModule);
      if (!toggle) return;
      let initialized = toggle.checked || !form.hasAttribute("data-new-campaign");
      function update() {
        group.hidden = !toggle.checked;
        group.disabled = !toggle.checked;
        if (toggle.checked && !initialized) {
          const ministries = group.querySelector('select[name="ministry_duids"]');
          if (ministries) Array.from(ministries.options).forEach((item) => {
            item.selected = true;
          });
          initialized = true;
        }
      }
      toggle.addEventListener("change", update);
      update();
    });
  });

  // The visual editor starts with server-sanitized markup only. Raw source
  // edits never go through innerHTML: they must round-trip through the preview
  // sanitizer before returning to visual editing. Paste/drop are plain text.
  document.querySelectorAll("[data-content-form]").forEach((form) => {
    const visual = form.querySelector("[data-visual-content]");
    const editor = form.querySelector("[data-content-editor]");
    const source = form.querySelector('textarea[name="html"]');
    if (!visual || !editor || !source) return;
    visual.hidden = false;
    form.querySelector("[data-html-source]").open = false;
    const sync = () => { source.value = editor.innerHTML; };
    editor.addEventListener("input", sync);
    source.addEventListener("input", () => { visual.hidden = true; });
    const selectedRange = () => {
      const selection = window.getSelection();
      if (!selection || !selection.rangeCount) return null;
      const range = selection.getRangeAt(0);
      return editor.contains(range.commonAncestorContainer) ? range : null;
    };
    form.querySelectorAll("[data-content-tag]").forEach((button) => {
      let saved = null;
      button.addEventListener("pointerdown", (event) => {
        saved = selectedRange();
        event.preventDefault(); // Keep the selected text when clicking a tool.
      });
      button.addEventListener("click", () => {
        const tag = button.dataset.contentTag;
        if (!["strong", "em", "p", "h2", "ul"].includes(tag)) return;
        const range = saved || selectedRange();
        saved = null;
        if (!range || !editor.contains(range.commonAncestorContainer)) return;
        const node = document.createElement(tag);
        const target = tag === "ul" ? node.appendChild(document.createElement("li")) : node;
        target.appendChild(range.extractContents());
        if (!target.hasChildNodes()) target.appendChild(document.createElement("br"));
        range.insertNode(node);
        const selection = window.getSelection();
        range.selectNodeContents(target);
        selection.removeAllRanges();
        selection.addRange(range);
        editor.focus();
        sync();
      });
    });
    editor.addEventListener("paste", (event) => {
      event.preventDefault();
      const range = selectedRange();
      if (!range || !event.clipboardData) return;
      range.deleteContents();
      const text = document.createTextNode(event.clipboardData.getData("text/plain"));
      range.insertNode(text);
      range.setStartAfter(text);
      range.collapse(true);
      sync();
    });
    editor.addEventListener("drop", (event) => { event.preventDefault(); });
    editor.addEventListener("click", (event) => {
      if (event.target.closest("a")) event.preventDefault();
    });
  });

  // Presence is observational: these requests never count as user activity.
  // Timers skip hidden tabs and never overlap requests or catch up missed ticks.
  const presenceIndicator = document.querySelector("[data-presence-indicator]");
  let presencePending = false;
  async function refreshPresence() {
    if (document.hidden || presencePending || !presenceIndicator) return;
    presencePending = true;
    const unavailable = document.querySelector("[data-presence-unavailable]");
    try {
      const response = await fetch("/admin/presence?format=count", {
        credentials: "same-origin", cache: "no-store"
      });
      if (!response.ok) throw new Error("Presence unavailable");
      const result = await response.json();
      if (!Number.isSafeInteger(result.count) || result.count < 0) throw new Error("Invalid count");
      presenceIndicator.querySelector("[data-presence-count]").textContent = result.count.toLocaleString("en-US");
      if (unavailable) unavailable.hidden = true;
    } catch {
      if (unavailable) unavailable.hidden = false;
    } finally { presencePending = false; }
  }
  if (presenceIndicator) {
    refreshPresence();
    window.setInterval(refreshPresence, 30000);
  }

  const backgroundIndicator = document.querySelector("[data-background-indicator]");
  let backgroundPending = false;
  async function refreshBackground() {
    if (document.hidden || backgroundPending || !backgroundIndicator) return;
    backgroundPending = true;
    const unavailable = document.querySelector("[data-background-unavailable]");
    try {
      const response = await fetch("/admin/background/tasks?size=1", {
        credentials: "same-origin", cache: "no-store"
      });
      if (!response.ok) throw new Error("Background work unavailable");
      const result = await response.json();
      const values = ["queued", "running", "retry_wait", "abandoned", "active"].map(
        (key) => result.counts[key]);
      if (values.some((value) => !Number.isSafeInteger(value) || value < 0)) throw new Error("Invalid counts");
      const total = values.slice(0, 4).reduce((sum, value) => sum + value, 0);
      if (!Number.isSafeInteger(total)) throw new Error("Invalid total");
      backgroundIndicator.querySelector("[data-background-total]").textContent = total.toLocaleString("en-US");
      backgroundIndicator.querySelector("[data-background-running]").textContent = values[4].toLocaleString("en-US");
      if (unavailable) unavailable.hidden = true;
    } catch {
      if (unavailable) unavailable.hidden = false;
    } finally { backgroundPending = false; }
  }
  if (backgroundIndicator) window.setInterval(refreshBackground, 30000);

  const session = document.querySelector("[data-family-session], [data-admin-session]");
  if (!session) return;
  const warning = document.getElementById("session-warning");
  const expired = document.getElementById("session-expired");
  const csrf = document.querySelector('input[name="csrfmiddlewaretoken"]');
  const offset = Date.parse(session.dataset.serverNow) - Date.now();
  let deadline = Date.parse(session.dataset.idleDeadline);
  const absolute = Date.parse(session.dataset.absoluteDeadline);
  let dirty = false;
  let pending = false;
  let lastAttempt = Date.now();
  if (![offset, deadline, absolute].every(Number.isFinite)) return;

  let familyPresencePending = false;
  async function familyPresence() {
    if (!session.hasAttribute("data-family-session") || document.hidden ||
        familyPresencePending || !csrf ||
        Date.now() + offset >= Math.min(deadline, absolute)) return;
    familyPresencePending = true;
    try {
      await fetch("/family/presence", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: {"X-CSRFToken": csrf.value, "Content-Type": "application/x-www-form-urlencoded"},
        body: new URLSearchParams({section: session.dataset.presenceSection || "welcome"})
      });
    } catch {
      // Presence failure neither renews the session nor replays any form values.
    } finally { familyPresencePending = false; }
  }
  if (session.hasAttribute("data-family-session")) {
    familyPresence();
    window.setInterval(familyPresence, 30000);
  }

  // Polling, focus and visibility do not imply activity. The empty server-side
  // keepalive is explicitly an untrusted claim, capped there too at five minutes.
  ["input", "keydown", "pointerdown"].forEach((event) => {
    document.addEventListener(event, () => { dirty = true; }, {passive: true});
  });
  async function tick() {
    const now = Date.now() + offset;
    const remaining = Math.min(deadline, absolute) - now;
    warning.hidden = remaining > 300000 || remaining <= 0;
    expired.hidden = remaining > 0;
    if (!session.hasAttribute("data-family-session") || remaining <= 0 ||
        !dirty || pending || document.hidden || !csrf ||
        Date.now() - lastAttempt < 300000) return;
    pending = true;
    dirty = false;
    lastAttempt = Date.now();
    try {
      const response = await fetch("/family/keepalive", {
        method: "POST", credentials: "same-origin", cache: "no-store",
        headers: {"X-CSRFToken": csrf.value, "Accept": "application/json"}
      });
      if (response.ok) {
        const result = await response.json();
        const next = Date.parse(result.idle_deadline);
        if (!Number.isFinite(next)) throw new Error("Invalid activity response");
        deadline = Math.min(next, absolute);
      } else {
        dirty = true;
      }
    } catch {
      // Retry the unconsumed claim at the next allowed five-minute interval.
      // Failure never extends the local deadline or bypasses server admission.
      dirty = true;
    } finally { pending = false; }
  }
  tick();
  window.setInterval(tick, 15000);
})();
