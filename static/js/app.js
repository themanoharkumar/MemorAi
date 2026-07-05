/**
 * MemorAI — App-wide JavaScript utilities
 * Toast notifications, API helpers, active nav links, keyboard shortcuts
 */

// ── Toast Notifications ──────────────────────────────────────────────────────

class ToastManager {
  constructor() {
    this.container = document.getElementById('toast-container');
    if (!this.container) {
      this.container = document.createElement('div');
      this.container.id = 'toast-container';
      this.container.className = 'toast-container';
      document.body.appendChild(this.container);
    }
  }

  show(message, type = 'info', duration = 3500) {
    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span style="font-size:1.1rem">${icons[type] || icons.info}</span><span>${message}</span>`;
    this.container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(8px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, duration);
  }

  success(msg) { this.show(msg, 'success'); }
  error(msg) { this.show(msg, 'error'); }
  info(msg) { this.show(msg, 'info'); }
}

window.toast = new ToastManager();

// ── Active Nav Links ─────────────────────────────────────────────────────────

function setActiveNavLinks() {
  const path = window.location.pathname;
  document.querySelectorAll('.nav-link').forEach(link => {
    const href = link.getAttribute('href');
    const isActive = href === '/' ? path === '/' : path.startsWith(href);
    link.classList.toggle('active', isActive);
  });
}

document.addEventListener('DOMContentLoaded', setActiveNavLinks);

// ── Relative Date Formatting ─────────────────────────────────────────────────

function relativeDate(dateStr) {
  if (!dateStr) return 'Never studied';
  const now = new Date(); now.setHours(0,0,0,0);
  const then = new Date(dateStr); then.setHours(0,0,0,0);
  const diffDays = Math.round((then - now) / 86400000);
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Tomorrow';
  if (diffDays === -1) return 'Yesterday';
  if (diffDays > 0) {
    if (diffDays < 7) return `in ${diffDays} days`;
    if (diffDays < 30) return `in ${Math.round(diffDays/7)} weeks`;
    if (diffDays < 365) return `in ${Math.round(diffDays/30)} months`;
    return `in ${Math.round(diffDays/365)} years`;
  } else {
    const p = Math.abs(diffDays);
    if (p < 7) return `${p} days ago`;
    if (p < 30) return `${Math.round(p/7)} weeks ago`;
    if (p < 365) return `${Math.round(p/30)} months ago`;
    return `${Math.round(p/365)} years ago`;
  }
}

window.relativeDate = relativeDate;

// ── API Helpers ──────────────────────────────────────────────────────────────

async function apiGet(url) {
  const res = await fetch(url);
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail || e.error || 'Request failed'); }
  return res.json();
}

async function apiPost(url, body) {
  const res = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail || e.error || 'Request failed'); }
  return res.json();
}

async function apiDelete(url) {
  const res = await fetch(url, { method: 'DELETE' });
  if (!res.ok) { const e = await res.json().catch(()=>({})); throw new Error(e.detail || e.error || 'Request failed'); }
  return res.json();
}

window.apiGet = apiGet;
window.apiPost = apiPost;
window.apiDelete = apiDelete;

// ── Format numbers ───────────────────────────────────────────────────────────

function formatPercent(n) { return `${Math.round(n * 100)}%`; }
function formatCardType(t) {
  return { definition: 'Definition', application: 'Application', relationship: 'Relationship', edge_case: 'Edge Case' }[t] || t;
}

window.formatPercent = formatPercent;
window.formatCardType = formatCardType;
