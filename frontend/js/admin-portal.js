(() => {
  const app = window.RIDEHUB_PORTAL || {};
  if (app.role !== 'ADMIN') return;

  const content = document.querySelector('#portal-content');
  const nav = document.querySelector('#portal-nav');
  const csrf = app.csrf || '';
  let activeView = 'overview';
  const pages = [
    ['OPERATIONS', [['overview', '◉', 'Platform overview'], ['reviews', '◈', 'Review queues'], ['users', '◉', 'Account governance'], ['earnings', '₹', 'Earnings & payments']]],
    ['GOVERNANCE', [['audit', '◌', 'Audit & security log']]],
  ];
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
  const api = async (url, options = {}) => {
    const response = await fetch(url, { credentials: 'same-origin', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf, ...(options.headers || {}) }, ...options });
    const data = await response.json().catch(() => ({}));
    if (!response.ok || !data.ok) throw new Error(data.message || 'Request could not be completed.');
    return data;
  };
  const empty = text => `<div class="empty-state"><div><div class="empty-icon">◌</div><h2>No records</h2><p>${esc(text)}</p></div></div>`;
  const message = (id, text, bad = false) => { const target = document.querySelector(`#${id}`); if (target) target.innerHTML = `<div class="inline-message ${bad ? 'error' : ''}">${esc(text)}</div>`; };

  function renderNav() {
    nav.innerHTML = pages.map(([group, links]) => `<div class="nav-group">${group}</div>${links.map(([id, icon, label]) => `<button class="nav-item ${activeView === id ? 'active' : ''}" data-admin-view="${id}"><span class="nav-icon">${icon}</span>${label}</button>`).join('')}`).join('');
  }

  function shell(title, detail) {
    document.querySelector('#crumb-label').textContent = title;
    content.innerHTML = `<div class="hero-line"><div><p class="eyebrow">ADMIN CONTROL PANEL</p><h1>${esc(title)}</h1><p>${esc(detail)}</p></div><span class="development-pill">PROTECTED OPERATIONS</span></div>`;
  }

  async function overview() {
    activeView = 'overview'; renderNav(); shell('Platform overview', 'Moderate marketplace access and inspect live operational queues.');
    content.insertAdjacentHTML('beforeend', '<div class="loading-block">Loading control centre…</div>');
    try {
      const { summary: s } = await api('/api/admin/summary/');
      content.querySelector('.loading-block').outerHTML = `<div class="dashboard-grid">
        <article class="card stat-card"><span class="stat-icon">◉</span><h3>${s.customers}</h3><p>Customers</p></article>
        <article class="card stat-card"><span class="stat-icon">▥</span><h3>${s.pending_shops}</h3><p>Shop reviews</p></article>
        <article class="card stat-card"><span class="stat-icon">◈</span><h3>${s.pending_vehicles}</h3><p>Vehicle reviews</p></article>
        <article class="card stat-card"><span class="stat-icon">▣</span><h3>${s.active_bookings}</h3><p>Active bookings</p></article>
        <article class="card stat-card"><span class="stat-icon">₹</span><h3>₹${Number(s.gross_earnings || 0).toLocaleString('en-IN')}</h3><p>Gross earnings</p></article>
        <article class="card wide-card"><div class="module-list">
          <button class="module-row" data-admin-view="reviews"><span class="mini-icon">◈</span><span><strong>Review queues</strong><small>Approve or reject shopkeeper and vehicle submissions.</small></span><span class="status-tag">OPEN</span></button>
          <button class="module-row" data-admin-view="users"><span class="mini-icon">◉</span><span><strong>Account governance</strong><small>Approve, revoke or permanently ban platform accounts.</small></span><span class="status-tag">OPEN</span></button>
          <button class="module-row" data-admin-view="earnings"><span class="mini-icon">₹</span><span><strong>Earnings & payments</strong><small>Inspect verified Razorpay receipts and marketplace totals.</small></span><span class="status-tag">OPEN</span></button>
          <button class="module-row" data-admin-view="audit"><span class="mini-icon">◌</span><span><strong>Audit trail</strong><small>Review recorded administrative actions.</small></span><span class="status-tag">OPEN</span></button>
        </div></article></div>`;
    } catch (error) { content.innerHTML = empty(error.message); }
  }

  async function reviews() {
    activeView = 'reviews'; renderNav(); shell('Review queues', 'Approve or reject marketplace submissions. Every action is audited.');
    content.insertAdjacentHTML('beforeend', '<article class="card"><div class="loading-block">Loading review queues…</div></article>');
    try {
      const data = await api('/api/admin/review-queues/');
      content.querySelector('.card').innerHTML = `<div id="admin-message"></div><h2>Pending shopkeepers</h2>${data.shopkeepers.length ? `<div class="table-wrap"><table class="user-table"><thead><tr><th>Shop</th><th>Contact</th><th>Fleet</th><th>Action</th></tr></thead><tbody>${data.shopkeepers.map(item => `<tr><td><strong>${esc(item.shop_name)}</strong><small>${esc(item.address)}</small></td><td>${esc(item.email)}<small>${esc(item.phone)}</small></td><td>${item.vehicle_count}</td><td><button class="row-action" data-admin-action-url="/api/admin/shopkeepers/${item.id}/action/" data-action="approve">Approve</button> <button class="row-action danger" data-admin-action-url="/api/admin/shopkeepers/${item.id}/action/" data-action="reject">Reject</button></td></tr>`).join('')}</tbody></table></div>` : empty('No shopkeeper requests pending.')}<h2 style="margin-top:24px">Pending vehicles</h2>${data.vehicles.length ? `<div class="table-wrap"><table class="user-table"><thead><tr><th>Vehicle</th><th>Shop</th><th>Rate</th><th>Action</th></tr></thead><tbody>${data.vehicles.map(item => `<tr><td><strong>${esc(item.name)}</strong><small>${esc(item.registration_number)}</small></td><td>${esc(item.shop)}</td><td>₹${esc(item.daily_rate)}</td><td><button class="row-action" data-admin-action-url="/api/admin/vehicles/${item.id}/action/" data-action="approve">Approve</button> <button class="row-action danger" data-admin-action-url="/api/admin/vehicles/${item.id}/action/" data-action="reject">Reject</button></td></tr>`).join('')}</tbody></table></div>` : empty('No vehicle submissions pending.')}`;
    } catch (error) { content.querySelector('.card').innerHTML = empty(error.message); }
  }

  async function users() {
    activeView = 'users'; renderNav(); shell('Account governance', 'Approve shopkeepers once, revoke access when required, or permanently ban unsafe accounts.');
    content.insertAdjacentHTML('beforeend', '<article class="card"><div class="loading-block">Loading customers…</div></article>');
    try {
      const data = await api('/api/admin/review-queues/');
      content.querySelector('.card').innerHTML = data.users.length ? `<div id="admin-message"></div><div class="table-wrap"><table class="user-table"><thead><tr><th>Account</th><th>Contact</th><th>Status</th><th>Action</th></tr></thead><tbody>${data.users.map(item => { const banned = item.permanently_banned; const action = item.active ? 'revoke' : (banned ? '' : 'restore'); const banUrl = item.action_url; return `<tr><td><strong>${esc(item.name)}</strong><small>${esc(item.role)}</small></td><td>${esc(item.email)}<small>${esc(item.phone)}</small></td><td><span class="payment-state ${item.active ? 'PAID' : 'CANCELLED'}">${banned ? 'PERMANENTLY BANNED' : (item.active ? 'ACTIVE' : 'REVOKED')}</span></td><td>${action ? `<button class="row-action ${item.active ? 'danger' : ''}" data-admin-action-url="${item.action_url}" data-action="${action}">${item.active ? 'Revoke' : 'Restore'}</button>` : ''}${!banned ? ` <button class="row-action danger" data-admin-action-url="${banUrl}" data-action="permanent_ban">Permanent ban</button>` : ''}</td></tr>`; }).join('')}</tbody></table></div>` : empty('No platform accounts found.');
    } catch (error) { content.querySelector('.card').innerHTML = empty(error.message); }
  }

  async function earnings() {
    activeView = 'earnings'; renderNav(); shell('Earnings & payments', 'Read-only financial visibility for verified RideHub receipts.');
    content.insertAdjacentHTML('beforeend', '<article class="card"><div class="loading-block">Loading payment ledger…</div></article>');
    try {
      const data = await api('/api/admin/earnings/');
      content.querySelector('.card').innerHTML = `<div class="dashboard-grid"><article class="card stat-card"><span class="stat-icon">₹</span><h3>₹${Number(data.total || 0).toLocaleString('en-IN')}</h3><p>Verified gross earnings</p></article><article class="card stat-card"><span class="stat-icon">▣</span><h3>${data.count}</h3><p>Paid transactions</p></article></div>${data.payments.length ? `<div class="table-wrap"><table class="user-table"><thead><tr><th>Receipt</th><th>Customer</th><th>Vehicle / shop</th><th>Amount</th><th>Time</th></tr></thead><tbody>${data.payments.map(item => `<tr><td>#${esc(item.id)}</td><td>${esc(item.customer)}</td><td><strong>${esc(item.vehicle)}</strong><small>${esc(item.shop)}</small></td><td>₹${Number(item.amount).toLocaleString('en-IN')}</td><td>${new Intl.DateTimeFormat('en-IN',{dateStyle:'medium',timeStyle:'short'}).format(new Date(item.created_at))}</td></tr>`).join('')}</tbody></table></div>` : empty('No verified payments yet.')}`;
    } catch (error) { content.querySelector('.card').innerHTML = empty(error.message); }
  }

  async function audit() {
    activeView = 'audit'; renderNav(); shell('Audit & security log', 'Recent administrative actions retained for operational accountability.');
    content.insertAdjacentHTML('beforeend', '<article class="card"><div class="loading-block">Loading audit events…</div></article>');
    try {
      const data = await api('/api/admin/audit/');
      content.querySelector('.card').innerHTML = data.events.length ? `<div class="table-wrap"><table class="user-table"><thead><tr><th>Action</th><th>Target</th><th>Actor</th><th>Time</th></tr></thead><tbody>${data.events.map(item => `<tr><td><strong>${esc(item.action)}</strong></td><td>${esc(item.entity_type)} #${esc(item.entity_id)}</td><td>${esc(item.actor)}</td><td>${new Intl.DateTimeFormat('en-IN', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(item.created_at))}</td></tr>`).join('')}</tbody></table></div>` : empty('No audit records yet.');
    } catch (error) { content.querySelector('.card').innerHTML = empty(error.message); }
  }

  async function performAction(button) {
    if (!confirm(`${button.dataset.action} this item?`)) return;
    try {
      const result = await api(button.dataset.adminActionUrl, { method: 'POST', body: JSON.stringify({ action: button.dataset.action }) });
      message('admin-message', result.message); setTimeout(() => ({ reviews, users }[activeView]()), 500);
    } catch (error) { message('admin-message', error.message, true); }
  }

  document.addEventListener('click', event => {
    const view = event.target.closest('[data-admin-view]')?.dataset.adminView;
    if (view) { event.preventDefault(); ({ overview, reviews, users, earnings, audit }[view] || overview)(); return; }
    const button = event.target.closest('[data-admin-action-url]');
    if (button) performAction(button);
  });
  document.querySelector('#mobile-menu').addEventListener('click', () => document.querySelector('#portal-sidebar').classList.toggle('open'));
  document.querySelector('#profile-shortcut').addEventListener('click', audit);
  document.querySelector('#logout-button').addEventListener('click', async () => { try { await api('/api/auth/logout/', { method: 'POST', body: '{}' }); } finally { window.location.assign('/auth/'); } });
  overview();
})();
