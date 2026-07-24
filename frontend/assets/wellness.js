/* ============================================================
   JETTY WELLNESS™ — Client-Side Logic & API Integrations
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  loadBusinessProfile();
  loadDashboardData();
  initModals();
});

// Navigation Handling
function initNavigation() {
  const navButtons = document.querySelectorAll('.nav-list button[data-tab]');
  const viewPanels = document.querySelectorAll('.view-panel');

  navButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      const targetTab = btn.getAttribute('data-tab');

      navButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');

      viewPanels.forEach(panel => {
        if (panel.id === `tab-${targetTab}`) {
          panel.classList.add('active');
        } else {
          panel.classList.remove('active');
        }
      });
    });
  });
}

// Mode Switch to 3D Second Brain
function switchToSecondBrain() {
  window.location.href = '/app/brain';
}

// API Fetch Helpers
async function fetchAPI(endpoint, options = {}) {
  try {
    const res = await fetch(endpoint, {
      headers: { 'Content-Type': 'application/json' },
      ...options
    });
    if (!res.ok) throw new Error(`API Error: ${res.statusText}`);
    return await res.json();
  } catch (err) {
    console.error('Fetch Error:', err);
    return null;
  }
}

// Load Business Profile
async function loadBusinessProfile() {
  const data = await fetchAPI('/api/wellness/business');
  if (data) {
    document.querySelectorAll('.bzn-name').forEach(el => el.textContent = data.name);
    document.querySelectorAll('.bzn-owner').forEach(el => el.textContent = data.owner_name);
  }
}

// Load Dashboard Data
async function loadDashboardData() {
  await Promise.all([
    loadClients(),
    loadAppointments(),
    loadRevenue(),
    loadAutomations()
  ]);
}

// Clients CRM Module
async function loadClients() {
  const clients = await fetchAPI('/api/wellness/clients');
  const tbody = document.getElementById('clients-table-body');
  if (!tbody || !clients) return;

  tbody.innerHTML = clients.map(c => {
    const statusClass = c.member_status === 'VIP Member' ? 'badge-vip' : (c.member_status === 'Lapsed' ? 'badge-lapsed' : 'badge-active');
    const prefs = Object.entries(c.preferences || {}).map(([k, v]) => `<strong>${k}:</strong> ${v}`).join(' | ');

    return `
      <tr>
        <td><strong>${c.name}</strong></td>
        <td><span class="badge ${statusClass}">${c.member_status || 'Active'}</span></td>
        <td>${c.phone || ''}<br><small style="color:var(--text-muted)">${c.email || ''}</small></td>
        <td>${prefs || 'None logged'}</td>
        <td>${c.last_contact || 'Recently'}</td>
      </tr>
    `;
  }).join('');
}

// Appointments Module
async function loadAppointments() {
  const appointments = await fetchAPI('/api/wellness/appointments');
  const listEl = document.getElementById('today-schedule-list');
  if (!listEl || !appointments) return;

  listEl.innerHTML = appointments.map(a => `
    <div style="padding: 12px; border-bottom: 1px solid var(--border-light); display: flex; justify-content: space-between; align-items: center;">
      <div>
        <strong style="font-size: 0.95rem; color: var(--dark-forest);">${a.title}</strong>
        <div style="font-size: 0.8rem; color: var(--text-muted);">${a.client_name} • ${a.instructor}</div>
      </div>
      <span class="badge badge-active">${a.time}</span>
    </div>
  `).join('');
}

// Revenue Module
async function loadRevenue() {
  const rev = await fetchAPI('/api/wellness/revenue');
  if (!rev) return;

  const revEl = document.getElementById('rev-this-month');
  if (revEl) revEl.textContent = `$${rev.this_month.toLocaleString()}`;

  const trendEl = document.getElementById('rev-trend');
  if (trendEl) trendEl.textContent = `↑ ${rev.trend_percent}% vs last month`;

  const servicesEl = document.getElementById('rev-by-service');
  if (servicesEl && rev.by_service) {
    servicesEl.innerHTML = rev.by_service.map(s => `
      <div style="display:flex; justify-content:space-between; padding:8px 0; border-bottom:1px dashed var(--border-light);">
        <span>${s.label}</span>
        <strong>$${s.amount.toLocaleString()}</strong>
      </div>
    `).join('');
  }
}

// Automations Module
async function loadAutomations() {
  const automations = await fetchAPI('/api/wellness/automations');
  const container = document.getElementById('automations-container');
  if (!container || !automations) return;

  container.innerHTML = automations.map(a => `
    <div class="card" style="margin-bottom: 16px;">
      <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom: 8px;">
        <h4 style="font-family: var(--font-header); font-size: 1.05rem; color: var(--dark-forest);">${a.name}</h4>
        <button class="btn-secondary" onclick="toggleAutomation('${a.id}')" style="padding: 4px 12px; font-size:0.8rem;">
          ${a.status === 'active' ? '✅ Active' : '⏸ Paused'}
        </button>
      </div>
      <p style="font-size: 0.88rem; color: var(--text-dark); margin-bottom: 8px;">"${a.trigger_desc}"</p>
      <div style="font-size: 0.8rem; font-weight:600; color: var(--sage-green-dark);">${a.result_metric}</div>
    </div>
  `).join('');
}

async function toggleAutomation(id) {
  const updated = await fetchAPI(`/api/wellness/automations/${id}/toggle`, { method: 'PATCH' });
  if (updated) loadAutomations();
}

// Onboarding Modal Handling
function initModals() {
  const modal = document.getElementById('onboarding-modal');
  const hasOnboarded = localStorage.getItem('jetty_wellness_onboarded');

  if (!hasOnboarded && modal) {
    modal.style.display = 'flex';
  }

  const form = document.getElementById('onboarding-form');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const bname = document.getElementById('ob-bzn-name').value;
      const btype = document.getElementById('ob-bzn-type').value;
      const owner = document.getElementById('ob-owner-name').value;

      await fetchAPI('/api/wellness/business', {
        method: 'POST',
        body: JSON.stringify({ name: bname, business_type: btype, owner_name: owner, region: 'Utah' })
      });

      localStorage.setItem('jetty_wellness_onboarded', 'true');
      if (modal) modal.style.display = 'none';
      loadBusinessProfile();
    });
  }
}
