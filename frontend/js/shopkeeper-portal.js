(() => {
  if ((window.RIDEHUB_PORTAL || {}).role !== 'SHOPKEEPER') return;

  const app = window.RIDEHUB_PORTAL;
  const content = document.querySelector('#portal-content');
  const nav = document.querySelector('#portal-nav');
  const csrf = app.csrf || '';
  let shopStatus = '';
  const allowedViews = ['overview', 'shop', 'vehicles', 'addvehicle', 'reservations', 'fares'];
  const esc = value => String(value ?? '').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
  const money = value => new Intl.NumberFormat('en-IN', {style:'currency', currency:'INR', maximumFractionDigits:0}).format(Number(value || 0));
  const date = value => new Intl.DateTimeFormat('en-IN', {dateStyle:'medium'}).format(new Date(`${value}T00:00:00`));
  const empty = text => `<div class="empty-state"><div><div class="empty-icon">◌</div><h2>Nothing here yet</h2><p>${esc(text)}</p></div></div>`;
  const message = (id, text, error = false) => { const target = document.querySelector(`#${id}`); if (target) target.innerHTML = `<div class="inline-message ${error ? 'error' : ''}">${esc(text)}</div>`; };

  async function api(url, options = {}) {
    const response = await fetch(url, {credentials:'same-origin', ...options, headers:{'X-CSRFToken':csrf, ...(options.headers || {})}});
    const raw = await response.text();
    let data = {};
    try { data = raw ? JSON.parse(raw) : {}; } catch (_) { data = {}; }
    if (!response.ok || data.ok === false) {
      if (response.status === 503) throw new Error(data.message || 'The database is not ready. Run the RideHub migrations and try again.');
      if (response.status >= 500) throw new Error(data.message || `The server returned an error (${response.status}). Check the Django server log; an unapplied database migration may be the cause.`);
      throw new Error(data.message || `Request failed (${response.status}).`);
    }
    return data;
  }

  function renderNav(active = 'overview') {
    const verified = shopStatus === 'VERIFIED';
    nav.innerHTML = `<div class="nav-group">OPERATIONS</div>
      <button class="nav-item ${active === 'overview' ? 'active' : ''}" data-shop-view="overview"><span class="nav-icon">◉</span>Business overview</button>
      <button class="nav-item ${active === 'shop' ? 'active' : ''}" data-shop-view="shop"><span class="nav-icon">⌖</span>Shop profile</button>
      ${verified ? `<button class="nav-item ${active === 'vehicles' ? 'active' : ''}" data-shop-view="vehicles"><span class="nav-icon">▤</span>Manage fleet</button>
      <button class="nav-item ${active === 'addvehicle' ? 'active' : ''}" data-shop-view="addvehicle"><span class="nav-icon">＋</span>Add vehicle</button>
      <button class="nav-item ${active === 'reservations' ? 'active' : ''}" data-shop-view="reservations"><span class="nav-icon">▣</span>Reservation centre</button>
      <button class="nav-item ${active === 'fares' ? 'active' : ''}" data-shop-view="fares"><span class="nav-icon">₹</span>Fare & pricing</button>` : ''}`;
  }

  function shell(title, detail, body, active) {
    document.querySelector('#crumb-label').textContent = title;
    renderNav(active);
    content.innerHTML = `<div class="hero-line"><div><p class="eyebrow">SHOPKEEPER PORTAL</p><h1>${esc(title)}</h1><p>${esc(detail)}</p></div><span class="development-pill">LIVE OPERATIONS</span></div>${body}`;
  }

  function go(view, navigate = true) {
    const target = allowedViews.includes(view) ? view : 'overview';
    if (navigate && target !== (app.section || 'overview')) {
      window.location.assign(target === 'overview' ? '/shopkeeper/' : `/shopkeeper/${target}/`);
      return;
    }
    ({overview, vehicles, reservations, addvehicle: addVehicle, shop: shopProfile, fares}[target] || overview)();
  }

  async function overview() {
    shell('Business overview', 'A clear view of listings, customer requests and payment-safe actions.', '<div class="loading-block">Loading workspace…</div>', 'overview');
    try {
      const data = await api('/api/shopkeeper/summary/'); const s = data.summary; shopStatus = data.profile.verification_status; renderNav('overview');
      const locationNotice = data.profile.latitude && data.profile.longitude ? '' : `<div class="notice-bar warning">Add your shop's manual address and current GPS location after registration so nearby customers can find you. <button class="row-action" data-shop-view="shop">Complete location</button></div>`;
      const pendingNotice = shopStatus === 'VERIFIED' ? locationNotice : `<div class="notice-bar warning">${shopStatus === 'PENDING' ? 'Your account is awaiting one-time admin verification. You can edit your shop profile now; fleet tools unlock after approval.' : 'Update your shop profile and wait for the one-time admin account review before publishing vehicles.'}</div>${locationNotice}`;
      content.querySelector('.loading-block').outerHTML = `<div class="notice-bar">${esc(data.profile.shop_name)} · ${esc(data.profile.verification_status)} · ${esc(data.profile.shop_address)}</div>${pendingNotice}
        <div class="dashboard-grid">
          <article class="card stat-card"><span class="stat-icon">▤</span><h3>${s.total_vehicles}</h3><p>Fleet listings</p><small>${s.approved_vehicles} live</small></article>
          <article class="card stat-card"><span class="stat-icon">◷</span><h3>${s.available_vehicles}</h3><p>Searchable vehicles</p><small>Live marketplace</small></article>
          <article class="card stat-card"><span class="stat-icon">▣</span><h3>${s.pending_reservations}</h3><p>Pending bookings</p><small>Needs your review</small></article>
          <article class="card stat-card"><span class="stat-icon">₹</span><h3>${money(s.gross_earnings)}</h3><p>Gross earnings</p><small>${s.paid_bookings} paid bookings</small></article>
          <article class="card wide-card"><div class="card-head"><div><h2>Run the operation</h2><p>Verified shops can manage their own fleet without waiting for admin on every change.</p></div><button class="ghost-button" data-shop-view="shop">Edit shop details →</button></div>${shopStatus === 'VERIFIED' ? `<div class="module-list"><button class="module-row" data-shop-view="vehicles"><span class="mini-icon">▤</span><span><strong>Manage fleet</strong><small>Publish, pause or remove your own vehicle listings.</small></span><span class="status-tag">OPEN</span></button><button class="module-row" data-shop-view="reservations"><span class="mini-icon">▣</span><span><strong>Reservation centre</strong><small>Confirm only paid customer requests.</small></span><span class="status-tag">OPEN</span></button><button class="module-row" data-shop-view="fares"><span class="mini-icon">₹</span><span><strong>Track earnings</strong><small>Review payment activity and settlement signals.</small></span><span class="status-tag">OPEN</span></button></div>` : '<div class="empty-state compact"><div><h2>Workspace unlocks after verification</h2><p>Complete your shop profile and submit it for the one-time admin account review.</p></div></div>'}</article>
          <article class="card side-card"><div class="card-head"><div><h2>Shop health</h2><p>What customers can see today.</p></div></div><div class="feature-grid"><div class="feature-option"><b>Verification</b><span>${esc(data.profile.verification_status)}</span></div><div class="feature-option"><b>Location</b><span>${data.profile.latitude && data.profile.longitude ? 'Map saved' : 'Add map location'}</span></div><div class="feature-option"><b>Availability</b><span>${s.available_vehicles} live listings</span></div></div></article>
        </div>`;
    } catch (error) { content.innerHTML = empty(error.message); }
  }

  async function vehicles() {
    if (shopStatus && shopStatus !== 'VERIFIED') return overview();
    shell('Manage fleet', 'Control your live inventory, availability and removals.', '<article class="card"><div class="loading-block">Loading fleet…</div></article>', 'vehicles');
    try {
      const data = await api('/api/shopkeeper/vehicles/');
      content.querySelector('.card').innerHTML = `<div class="card-head"><div><h2>Your fleet</h2><p>New listings publish instantly after your shop account is verified. Admin can still moderate exceptions.</p></div><button class="ghost-button" data-shop-view="addvehicle">Add vehicle</button></div><div id="fleet-message"></div>${data.vehicles.length ? `<div class="table-wrap"><table class="user-table"><thead><tr><th>Vehicle</th><th>Inventory</th><th>Rate</th><th>Status</th><th>Action</th></tr></thead><tbody>${data.vehicles.map(v => `<tr><td><strong>${esc(v.name)}</strong><small>${esc(v.type)} · ${v.seating_capacity} seats · ${esc(v.fuel_type || 'fuel n/a')}</small></td><td><strong>${v.available_quantity}/${v.quantity} available</strong><small>Live quantity</small><div class="inventory-editor"><input type="number" min="1" max="999" value="${v.quantity}" data-inventory-input="${v.id}" aria-label="Fleet quantity for ${esc(v.name)}"><button class="row-action" data-save-inventory="${v.id}">Save</button></div></td><td>${money(v.daily_rate)} / day</td><td><span class="payment-state ${esc(v.listing_status)}">${esc(v.listing_status)}</span></td><td>${v.listing_status === 'APPROVED' ? `<button class="row-action ${v.is_available ? 'danger' : ''}" data-availability="${v.id}" data-available="${!v.is_available}">${v.is_available ? 'Pause' : 'Publish'}</button>` : ''} <button class="row-action danger" data-remove-vehicle="${v.id}">Remove</button></td></tr>`).join('')}</tbody></table></div>` : empty('No vehicles submitted yet. Add your first vehicle to publish it to customers.')}`;
    } catch (error) { content.querySelector('.card').innerHTML = empty(error.message); }
  }

  function addVehicle() {
    if (shopStatus && shopStatus !== 'VERIFIED') return overview();
    shell('Add vehicle', 'Add complete specifications so customers can compare the ride confidently.', `<article class="card"><form class="user-form" id="add-vehicle-form" enctype="multipart/form-data">
      <label class="user-field">Vehicle type<select name="vehicle_type" required><option value="car">Car</option><option value="bike">Bike</option><option value="scooter">Scooter</option><option value="commercial">Commercial</option></select></label><label class="user-field">Body style<select name="body_style"><option value="hatchback">Hatchback</option><option value="sedan">Sedan</option><option value="suv">SUV</option><option value="xuv">XUV</option><option value="standard">Standard</option></select></label><label class="user-field">Brand<input name="brand" maxlength="80" placeholder="Hyundai, TVS, Maruti" required></label><label class="user-field">Model<input name="model_name" maxlength="120" placeholder="i10, Jupiter, Swift" required></label><label class="user-field">Registration number<input name="registration_number" maxlength="20" placeholder="UK07AB1234" style="text-transform:uppercase" required></label><label class="user-field">Manufacturing year<input type="number" name="manufacturing_year" min="1900" max="2100" required></label><label class="user-field">Fuel type<select name="fuel_type"><option value="petrol">Petrol</option><option value="diesel">Diesel</option><option value="electric">Electric</option><option value="cng">CNG</option><option value="hybrid">Hybrid</option></select></label><label class="user-field">Fuel capacity (L)<input type="number" name="fuel_capacity" min="0" max="999" step="0.1" placeholder="e.g. 37"></label><label class="user-field">Daily rate (₹)<input type="number" name="daily_rate" min="0" max="99999999" step="0.01" required></label><label class="user-field">Fleet quantity<input type="number" name="quantity" min="1" max="999" value="1" required></label><label class="user-field">Seats<input type="number" name="seating_capacity" min="1" max="100" value="2" required></label><label class="user-field">Photo<input type="file" name="image" accept="image/*"></label><label class="user-field form-wide">Description<textarea name="description" maxlength="1000" placeholder="Condition, features, documents available…"></textarea></label><button class="form-action" type="submit">Publish vehicle</button></form><div id="vehicle-create-message"></div></article>`, 'addvehicle');
  }

  async function shopProfile() {
    shell('Shop profile', 'Edit the public business information and map location customers see.', '<article class="card"><div class="loading-block">Loading shop profile…</div></article>', 'shop');
    try {
      const data = await api('/api/shopkeeper/summary/'); const p = data.profile; shopStatus = p.verification_status; renderNav('shop');
      content.querySelector('.card').innerHTML = `<div class="notice-bar">After registration, save both your manual shop address and your current GPS location. Customers will see the verified location when searching nearby.</div><form class="user-form" id="shop-profile-form"><label class="user-field">Shop name<input name="shop_name" maxlength="120" value="${esc(p.shop_name)}" required></label><label class="user-field">Business email<input value="${esc(p.email)}" disabled></label><label class="user-field form-wide">Manual shop address<input name="shop_address" maxlength="255" value="${esc(p.shop_address)}" required></label><label class="user-field form-wide">Shop description<textarea name="shop_description" minlength="20" maxlength="1000" required>${esc(p.shop_description || '')}</textarea></label><label class="user-field">Current latitude<input name="latitude" value="${esc(p.latitude)}" inputmode="decimal" placeholder="Use current location or enter manually"></label><label class="user-field">Current longitude<input name="longitude" value="${esc(p.longitude)}" inputmode="decimal" placeholder="Use current location or enter manually"></label><button class="ghost-button" type="button" data-use-shop-location>◎ Capture current location</button><button class="form-action" type="submit">Save shop & location</button></form><div id="shop-profile-message"></div><div class="notice-bar" style="margin-top:16px">Verification: ${esc(p.verification_status)}. You can update business details anytime; account access is controlled by the admin governance team.</div>`;
    } catch (error) { content.querySelector('.card').innerHTML = empty(error.message); }
  }

  async function reservations() {
    if (shopStatus && shopStatus !== 'VERIFIED') return overview();
    shell('Reservation centre', 'Only successful online payments appear here for review.', '<article class="card"><div class="loading-block">Loading paid reservations…</div></article>', 'reservations');
    try {
      const data = await api('/api/shopkeeper/reservations/');
      content.querySelector('.card').innerHTML = data.reservations.length ? `<div id="reservation-message"></div><div class="table-wrap"><table class="user-table"><thead><tr><th>Customer & ride</th><th>Dates</th><th>Amount</th><th>Payment</th><th>Action</th></tr></thead><tbody>${data.reservations.map(b => `<tr><td><strong>${esc(b.customer)} · ${esc(b.vehicle)}</strong><small>${esc(b.customer_email)} · ${esc(b.customer_phone)}</small></td><td>${date(b.pickup_date)}<small>to ${date(b.return_date)}</small></td><td>${money(b.total_amount)}</td><td><span class="payment-state ${esc(b.payment_status)}">${esc(b.payment_status)}</span><small>${esc(b.status)}</small></td><td>${b.status === 'PENDING' ? `<button class="row-action" data-reservation="${b.id}" data-reservation-action="CONFIRM">Confirm</button>` : 'Processed'}</td></tr>`).join('')}</tbody></table></div>` : empty('No successful online reservations yet.');
    } catch (error) { content.querySelector('.card').innerHTML = empty(error.message); }
  }

  async function fares() {
    if (shopStatus && shopStatus !== 'VERIFIED') return overview();
    shell('Fare & pricing', 'Set the daily rate for your live vehicle listings.', '<article class="card"><div class="loading-block">Loading approved fleet…</div></article>', 'fares');
    try {
      const data = await api('/api/shopkeeper/vehicles/'); const fleet = data.vehicles.filter(v => v.listing_status === 'APPROVED');
      content.querySelector('.card').innerHTML = fleet.length ? `<div id="fare-message"></div><div class="table-wrap"><table class="user-table"><thead><tr><th>Vehicle</th><th>Current daily fare</th><th>New daily fare</th><th>Action</th></tr></thead><tbody>${fleet.map(v => `<tr><td><strong>${esc(v.name)}</strong><small>${esc(v.registration_number)}</small></td><td>${money(v.daily_rate)}</td><td><input class="fare-input" type="number" min="0" step="0.01" value="${esc(v.daily_rate)}" data-fare-input="${v.id}"></td><td><button class="row-action" data-save-fare="${v.id}">Save fare</button></td></tr>`).join('')}</tbody></table></div>` : empty('No approved vehicles are available for pricing yet.');
    } catch (error) { content.querySelector('.card').innerHTML = empty(error.message); }
  }

  async function reservationAction(id, action) { if (!confirm(`${action === 'CONFIRM' ? 'Confirm' : 'Decline'} this reservation?`)) return; try { const data = await api(`/api/shopkeeper/reservations/${id}/action/`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action})}); message('reservation-message', data.message); setTimeout(reservations, 500); } catch (error) { message('reservation-message', error.message, true); } }
  async function availability(id, available) { try { const data = await api(`/api/shopkeeper/vehicles/${id}/availability/`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({is_available:available})}); message('fleet-message', data.message); setTimeout(vehicles, 500); } catch (error) { message('fleet-message', error.message, true); } }
  async function removeVehicle(id) { if (!confirm('Remove this vehicle from the marketplace? Booking history will remain protected.')) return; try { const data = await api(`/api/shopkeeper/vehicles/${id}/remove/`, {method:'POST'}); message('fleet-message', data.message); setTimeout(vehicles, 500); } catch (error) { message('fleet-message', error.message, true); } }
  async function saveFare(id) { const input = document.querySelector(`[data-fare-input="${id}"]`); try { const data = await api(`/api/shopkeeper/vehicles/${id}/rate/`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({daily_rate:input?.value})}); message('fare-message', data.message); setTimeout(fares, 500); } catch (error) { message('fare-message', error.message, true); } }
  async function saveInventory(id) { const input = document.querySelector(`[data-inventory-input="${id}"]`); try { const data = await api(`/api/shopkeeper/vehicles/${id}/inventory/`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({quantity:input?.value})}); message('fleet-message', data.message); setTimeout(vehicles, 500); } catch (error) { message('fleet-message', error.message, true); } }
  function useShopLocation() { if (!navigator.geolocation) return message('shop-profile-message', 'Location access is unavailable in this browser.', true); navigator.geolocation.getCurrentPosition(position => { document.querySelector('[name="latitude"]').value = position.coords.latitude.toFixed(6); document.querySelector('[name="longitude"]').value = position.coords.longitude.toFixed(6); message('shop-profile-message', 'Current location added. Save the profile to continue.'); }, () => message('shop-profile-message', 'Location permission was not granted. Enter coordinates manually.', true), {enableHighAccuracy:true, timeout:10000, maximumAge:300000}); }

  document.addEventListener('click', event => {
    const view = event.target.closest('[data-shop-view]')?.dataset.shopView;
    if (view) { event.preventDefault(); go(view); return; }
    const reservation = event.target.closest('[data-reservation]'); if (reservation) reservationAction(reservation.dataset.reservation, reservation.dataset.reservationAction);
    const vehicle = event.target.closest('[data-availability]'); if (vehicle) availability(vehicle.dataset.availability, vehicle.dataset.available === 'true');
    const remove = event.target.closest('[data-remove-vehicle]'); if (remove) removeVehicle(remove.dataset.removeVehicle);
    const fare = event.target.closest('[data-save-fare]'); if (fare) saveFare(fare.dataset.saveFare);
    const inventory = event.target.closest('[data-save-inventory]'); if (inventory) saveInventory(inventory.dataset.saveInventory);
    if (event.target.closest('[data-use-shop-location]')) useShopLocation();
  });

  document.addEventListener('submit', async event => {
    if (!['add-vehicle-form', 'shop-profile-form'].includes(event.target.id)) return;
    event.preventDefault(); const form = event.target; const isVehicle = form.id === 'add-vehicle-form'; const url = isVehicle ? '/api/shopkeeper/vehicles/create/' : '/api/shopkeeper/profile/'; const messageId = isVehicle ? 'vehicle-create-message' : 'shop-profile-message'; const submit = form.querySelector('[type="submit"]'); submit.disabled = true;
    try { const data = await api(url, {method:'POST', body:new FormData(form)}); message(messageId, data.message); if (isVehicle) { form.reset(); setTimeout(vehicles, 700); } } catch (error) { message(messageId, error.message, true); } finally { submit.disabled = false; }
  });

  document.querySelector('#mobile-menu')?.addEventListener('click', () => document.querySelector('#portal-sidebar').classList.toggle('open'));
  document.querySelector('#profile-shortcut')?.addEventListener('click', () => go('shop'));
  document.querySelector('#logout-button')?.addEventListener('click', async () => { try { await api('/api/auth/logout/', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'}); } finally { window.location.assign('/auth/'); } });
  go(app.section || 'overview', false);
})();
