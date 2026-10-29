(() => {
  if ((window.RIDEHUB_PORTAL || {}).role !== 'SHOPKEEPER') return;

  const app = window.RIDEHUB_PORTAL;
  const content = document.querySelector('#portal-content');
  const nav = document.querySelector('#portal-nav');
  const csrf = app.csrf || '';
  let shopStatus = '';
  const allowedViews = ['overview', 'shop', 'vehicles', 'addvehicle', 'reservations', 'earnings', 'fares'];
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
  function bindRowSearch(inputId, selector) {
    document.querySelector(`#${inputId}`)?.addEventListener('input', event => {
      const term = event.currentTarget.value.trim().toLowerCase();
      document.querySelectorAll(selector).forEach(row => { row.hidden = !!term && !row.dataset.search.toLowerCase().includes(term); });
    });
  }

  function renderNav(active = 'overview') {
    nav.innerHTML = `<div class="nav-group">OPERATIONS</div>
      <button class="nav-item ${active === 'overview' ? 'active' : ''}" data-shop-view="overview"><span class="nav-icon">◉</span>Business overview</button>
      <button class="nav-item ${active === 'shop' ? 'active' : ''}" data-shop-view="shop"><span class="nav-icon">⌖</span>Shop profile</button>
      <button class="nav-item ${active === 'vehicles' ? 'active' : ''}" data-shop-view="vehicles"><span class="nav-icon">▤</span>Manage fleet</button>
      <button class="nav-item ${active === 'addvehicle' ? 'active' : ''}" data-shop-view="addvehicle"><span class="nav-icon">＋</span>Add vehicle</button>
      <button class="nav-item ${active === 'reservations' ? 'active' : ''}" data-shop-view="reservations"><span class="nav-icon">▣</span>Reservation centre</button>
      <button class="nav-item ${active === 'earnings' ? 'active' : ''}" data-shop-view="earnings"><span class="nav-icon">₹</span>Earnings</button>
      <button class="nav-item ${active === 'fares' ? 'active' : ''}" data-shop-view="fares"><span class="nav-icon">₹</span>Fare & pricing</button>`;
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
    ({overview, vehicles, reservations, earnings, addvehicle: addVehicle, shop: shopProfile, fares}[target] || overview)();
  }

  async function earnings() {
    shell('Earnings', 'Commission snapshots from paid bookings. Computed earnings are not payouts.', '<div class="loading-block">Loading earnings…</div>', 'earnings');
    try {
      const data = await api('/api/shopkeeper/earnings/'); const s=data.summary;
      content.innerHTML += `<div class="dashboard-grid">${[['Eligible fare',s.eligible_rental_fare],['Commission deducted',s.commission_deducted],['Net earnings',s.net_earnings],['Eligible bookings',s.eligible_bookings]].map(([label,value])=>`<article class="card stat-card"><h3>${typeof value==='number'?value:money(value)}</h3><p>${label}</p></article>`).join('')}</div><article class="card"><p class="notice-bar">${esc(s.note)}</p><div class="table-wrap"><table class="user-table"><thead><tr><th>Booking</th><th>Vehicle</th><th>Rental</th><th>Commission</th><th>Net</th><th>Status</th></tr></thead><tbody>${data.rows.map(r=>`<tr><td>${esc(r.reference)}<small>${esc(r.customer)}</small></td><td>${esc(r.vehicle)}</td><td>${money(r.commissionable_base)}</td><td>${esc(r.commission_rate)}% · ${money(r.platform_commission)}${r.reversed?'<small>Reversed</small>':''}</td><td>${money(r.net_earnings)}</td><td>${esc(r.booking_status)}<small>${esc(r.payment_status)}</small></td></tr>`).join('') || '<tr><td colspan="6">No financial snapshots yet.</td></tr>'}</tbody></table></div></article>`;
    } catch (error) { content.innerHTML = empty(error.message); }
  }

  async function overview() {
    shell('Business overview', 'A clear view of listings, customer requests and payment-safe actions.', '<div class="loading-block">Loading workspace…</div>', 'overview');
    try {
      const data = await api('/api/shopkeeper/summary/'); const s = data.summary; shopStatus = data.profile.verification_status; renderNav('overview');
      const locationNotice = data.profile.latitude && data.profile.longitude ? '' : `<div class="notice-bar warning">Add your shop's manual address and current GPS location after registration so nearby customers can find you. <button class="row-action" data-shop-view="shop">Complete location</button></div>`;
      const complianceNotice = data.profile.compliance_complete ? '' : `<div class="notice-bar warning"><strong>Compliance profile required.</strong> Upload business, PAN, Aadhaar, address and GST documents before RideHub can review your account. <button class="row-action" data-shop-view="shop">Complete now</button></div>`;
      const pendingNotice = shopStatus === 'VERIFIED' ? `${complianceNotice}${locationNotice}` : `<div class="notice-bar warning">${shopStatus === 'PENDING' ? 'Your account is awaiting RideHub verification after the compliance profile is submitted.' : 'Update your shop profile and submit it for review again.'}</div>${complianceNotice}${locationNotice}`;
      if (!data.profile.compliance_complete) setTimeout(() => { if (!document.querySelector('[data-compliance-popup]')) alert('Complete your compliance profile to submit your shop for RideHub verification.'); }, 0);
      content.querySelector('.loading-block').outerHTML = `<div class="notice-bar">${esc(data.profile.shop_name)} · ${esc(data.profile.verification_status)} · ${esc(data.profile.shop_address)}</div>${pendingNotice}
        <div class="dashboard-grid">
          <article class="card stat-card"><span class="stat-icon">▤</span><h3>${s.total_vehicles}</h3><p>Fleet listings</p><small>${s.approved_vehicles} live</small></article>
          <article class="card stat-card"><span class="stat-icon">◷</span><h3>${s.available_vehicles}</h3><p>Searchable vehicles</p><small>Live marketplace</small></article>
          <article class="card stat-card"><span class="stat-icon">▣</span><h3>${s.pending_reservations}</h3><p>Confirmed rides</p><small>Ready for handover</small></article>
          <article class="card stat-card"><span class="stat-icon">₹</span><h3>${money(s.gross_earnings)}</h3><p>Gross earnings</p><small>${s.paid_bookings} paid bookings</small></article>
          <article class="card wide-card"><div class="card-head"><div><h2>Run the operation</h2><p>Every vehicle is document-reviewed before it goes live.</p></div><button class="ghost-button" data-shop-view="shop">Edit shop details →</button></div>${shopStatus === 'VERIFIED' ? `<div class="module-list"><button class="module-row" data-shop-view="vehicles"><span class="mini-icon">▤</span><span><strong>Manage fleet</strong><small>Track approved and review-pending listings.</small></span><span class="status-tag">OPEN</span></button><button class="module-row" data-shop-view="reservations"><span class="mini-icon">▣</span><span><strong>Reservation centre</strong><small>Record handover, return, or a reasoned cancellation.</small></span><span class="status-tag">OPEN</span></button><button class="module-row" data-shop-view="fares"><span class="mini-icon">₹</span><span><strong>Track earnings</strong><small>Review payment activity and settlement signals.</small></span><span class="status-tag">OPEN</span></button></div>` : '<div class="empty-state compact"><div><h2>Complete verification to unlock fleet tools</h2><p>Upload your required business documents and submit the shop for RideHub review.</p></div></div>'}</article>
          <article class="card side-card"><div class="card-head"><div><h2>Shop health</h2><p>What customers can see today.</p></div></div><div class="feature-grid"><div class="feature-option"><b>Verification</b><span>${esc(data.profile.verification_status)}</span></div><div class="feature-option"><b>Location</b><span>${data.profile.latitude && data.profile.longitude ? 'Map saved' : 'Add map location'}</span></div><div class="feature-option"><b>Availability</b><span>${s.available_vehicles} live listings</span></div></div></article>
        </div>`;
    } catch (error) { content.innerHTML = empty(error.message); }
  }

  async function vehicles() {
    shell('Manage fleet', 'Control your live inventory, availability and removals.', '<article class="card"><div class="loading-block">Loading fleet…</div></article>', 'vehicles');
    try {
      const data = await api('/api/shopkeeper/vehicles/');
      content.querySelector('.card').innerHTML = `<div class="card-head"><div><h2>Your fleet</h2><p>New listings remain pending until RideHub verifies RC, insurance and photos.</p></div><button class="ghost-button" data-shop-view="addvehicle">Add vehicle</button></div><div id="fleet-message"></div>${data.vehicles.length ? `<div class="admin-toolbar"><label><span>Search fleet</span><input id="fleet-search" type="search" placeholder="Vehicle, registration, fuel or status"></label></div><div class="table-wrap"><table class="user-table"><thead><tr><th>Vehicle</th><th>Inventory</th><th>Rate</th><th>Status</th><th>Action</th></tr></thead><tbody>${data.vehicles.map(v => `<tr data-fleet-row data-search="${esc(Object.values(v).join(' '))}"><td><strong>${esc(v.name)}</strong><small>${esc(v.type)} · ${v.seating_capacity} seats · ${esc(v.fuel_type || 'fuel n/a')}</small></td><td><strong>${v.available_quantity}/${v.quantity} available</strong><small>Live quantity</small></td><td>${money(v.daily_rate)} / day</td><td><span class="payment-state ${esc(v.listing_status)}">${esc(v.listing_status)}</span><small>${esc(v.admin_note || (v.listing_status === 'PENDING' ? 'RideHub review in progress' : ''))}</small></td><td>${v.listing_status === 'APPROVED' ? `<button class="row-action ${v.is_available ? 'danger' : ''}" data-availability="${v.id}" data-available="${!v.is_available}">${v.is_available ? 'Pause' : 'Publish'}</button>` : ''} <button class="row-action danger" data-remove-vehicle="${v.id}">Remove</button></td></tr>`).join('')}</tbody></table></div>` : empty('No vehicles submitted yet. Submit your first vehicle for RideHub review.')}`; bindRowSearch('fleet-search', '[data-fleet-row]');
    } catch (error) { content.querySelector('.card').innerHTML = empty(error.message); }
  }

  function addVehicle() {
    shell('Add vehicle', 'Submit complete ownership, insurance and condition evidence for RideHub approval.', `<article class="card"><div class="notice-bar">Your vehicle remains pending until RideHub verifies its RC, insurance and photos.</div><form class="user-form" id="add-vehicle-form" enctype="multipart/form-data">
      <label class="user-field">Vehicle type<select name="vehicle_type" required><option value="car">Car</option><option value="bike">Bike</option><option value="scooter">Scooter</option><option value="commercial">Commercial</option></select></label><label class="user-field">Body style<select name="body_style"><option value="hatchback">Hatchback</option><option value="sedan">Sedan</option><option value="suv">SUV</option><option value="xuv">XUV</option><option value="standard">Standard</option></select></label><label class="user-field">Brand<input name="brand" maxlength="80" placeholder="Hyundai, TVS, Maruti" required></label><label class="user-field">Model<input name="model_name" maxlength="120" placeholder="i10, Jupiter, Swift" required></label><label class="user-field">Registration number<input name="registration_number" maxlength="13" placeholder="UK07AB1234" pattern="(?:[A-Za-z]{2}[0-9]{1,2}[A-Za-z]{1,3}[0-9]{4}|[0-9]{2}[Bb][Hh][0-9]{4}[A-Za-z]{1,2})" title="Use an Indian registration format, for example UK07AB1234 or 24BH1234AA" data-uppercase required></label><label class="user-field">Manufacturing year<input type="number" name="manufacturing_year" min="1900" max="2100" required></label><label class="user-field">Fuel type<select name="fuel_type"><option value="petrol">Petrol</option><option value="diesel">Diesel</option><option value="electric">Electric</option><option value="cng">CNG</option><option value="hybrid">Hybrid</option></select></label><label class="user-field">Fuel capacity (L)<input type="number" name="fuel_capacity" min="0" max="999" step="0.1" placeholder="e.g. 37"></label><label class="user-field">Daily rate (₹)<input type="number" name="daily_rate" min="0" max="99999999" step="0.01" required></label><label class="user-field">Fleet quantity<input type="number" name="quantity" min="1" max="999" value="1" required></label><label class="user-field">Seats<input type="number" name="seating_capacity" min="1" max="100" value="2" required></label><label class="user-field">RC number<input name="rc_number" maxlength="13" placeholder="Must match registration number" pattern="(?:[A-Za-z]{2}[0-9]{1,2}[A-Za-z]{1,3}[0-9]{4}|[0-9]{2}[Bb][Hh][0-9]{4}[A-Za-z]{1,2})" title="Enter the same valid registration shown on the RC" data-uppercase required></label><label class="user-field">Chassis / VIN number<input name="chassis_number" maxlength="17" minlength="17" pattern="[A-HJ-NPR-Za-hj-npr-z0-9]{17}" title="Enter the 17-character chassis/VIN (I, O and Q are not used)" data-uppercase required></label><label class="user-field">RC document<input type="file" name="rc_document" accept="image/*,application/pdf" required></label><label class="user-field">Insurance policy number<input name="insurance_policy_number" minlength="5" maxlength="40" pattern="(?=.*[0-9])[A-Za-z0-9/-]{5,40}" title="Use 5–40 letters/digits, optionally with / or -, and include at least one digit" data-uppercase required></label><label class="user-field">Insurance expiry<input type="date" name="insurance_expiry_date" required></label><label class="user-field">Insurance document<input type="file" name="insurance_document" accept="image/*,application/pdf" required></label><label class="user-field">PUC document (if applicable)<input type="file" name="puc_document" accept="image/*,application/pdf"></label><label class="user-field">PUC expiry<input type="date" name="puc_expiry_date"></label><label class="user-field">Front photo<input type="file" name="vehicle_photo_front" accept="image/*" required></label><label class="user-field">Rear photo<input type="file" name="vehicle_photo_rear" accept="image/*" required></label><label class="user-field">Left-side photo<input type="file" name="vehicle_photo_left" accept="image/*" required></label><label class="user-field">Right-side photo<input type="file" name="vehicle_photo_right" accept="image/*" required></label><label class="user-field form-wide">Description<textarea name="description" maxlength="1000" placeholder="Condition, accessories, pickup notes…"></textarea></label><button class="form-action" type="submit">Submit for RideHub review</button></form><div id="vehicle-create-message"></div></article>`, 'addvehicle');
  }

  async function shopProfile() {
    shell('Shop profile', 'Edit the public business information and map location customers see.', '<article class="card"><div class="loading-block">Loading shop profile…</div></article>', 'shop');
    try {
      const data = await api('/api/shopkeeper/summary/'); const p = data.profile; shopStatus = p.verification_status; renderNav('shop');
      content.querySelector('.card').innerHTML = `<div class="notice-bar">Complete every item once. RideHub verifies this information before accepting vehicle listings.</div><form class="user-form" id="shop-profile-form" enctype="multipart/form-data"><label class="user-field">Shop name<input name="shop_name" maxlength="120" value="${esc(p.shop_name)}" required></label><label class="user-field">Business email<input value="${esc(p.email)}" disabled></label><label class="user-field">Legal business name<input name="legal_business_name" maxlength="160" value="${esc(p.legal_business_name || '')}" required></label><label class="user-field">Proprietor / authorised person<input name="proprietor_name" maxlength="150" value="${esc(p.proprietor_name || '')}" required></label><label class="user-field">Business type<select name="business_type" required><option value="">Select type</option>${['Sole proprietorship','Partnership','LLP','Private limited','Other'].map(x => `<option ${p.business_type === x ? 'selected' : ''}>${x}</option>`).join('')}</select></label><label class="user-field">PAN number<input name="pan_number" maxlength="10" pattern="[A-Za-z]{3}[ABCFGHLJPT][A-Za-z][0-9]{4}[A-Za-z]" title="Enter a valid 10-character PAN" value="${esc(p.pan_number || '')}" data-uppercase required></label><label class="user-field">GSTIN (if registered)<input name="gstin" maxlength="15" pattern="(?:0[1-9]|[12][0-9]|3[0-8]|97)[A-Za-z]{3}[ABCFGHLJPT][A-Za-z][0-9]{4}[A-Za-z][0-9A-Za-z]Z[A-Za-z0-9]" title="Enter a valid 15-character GSTIN matching the PAN above" value="${esc(p.gstin || '')}" data-uppercase></label><label class="user-field">Last 4 Aadhaar digits<input name="aadhaar_last4" inputmode="numeric" maxlength="4" minlength="4" pattern="[0-9]{4}" title="Enter exactly the final 4 digits" value="${esc(p.aadhaar_last4 || '')}" required></label><label class="user-field">Business registration no. (optional)<input name="business_registration_number" maxlength="80" pattern="[A-Za-z0-9/-]{3,80}" title="Use 3–80 letters, digits, slash or hyphen" value="${esc(p.business_registration_number || '')}" data-uppercase></label><label class="user-field form-wide">Manual shop address<input name="shop_address" maxlength="255" value="${esc(p.shop_address)}" required></label><label class="user-field form-wide">Shop description<textarea name="shop_description" minlength="20" maxlength="1000" required>${esc(p.shop_description || '')}</textarea></label><label class="user-field">Shop exterior / signage photo<input type="file" name="shop_photo" accept="image/*" ${p.compliance_complete ? '' : 'required'}></label><label class="user-field">Address proof<input type="file" name="address_proof" accept="image/*,application/pdf" ${p.compliance_complete ? '' : 'required'}></label><label class="user-field">PAN card<input type="file" name="pan_document" accept="image/*,application/pdf" ${p.compliance_complete ? '' : 'required'}></label><label class="user-field">Aadhaar card<input type="file" name="aadhaar_document" accept="image/*,application/pdf" ${p.compliance_complete ? '' : 'required'}></label><label class="user-field">GST certificate (if GSTIN entered)<input type="file" name="gst_certificate" accept="image/*,application/pdf"></label><label class="user-field">Current latitude<input name="latitude" value="${esc(p.latitude)}" inputmode="decimal"></label><label class="user-field">Current longitude<input name="longitude" value="${esc(p.longitude)}" inputmode="decimal"></label><button class="ghost-button" type="button" data-use-shop-location>◎ Capture current location</button><button class="form-action" type="submit">Save & submit compliance profile</button></form><div id="shop-profile-message"></div><div class="notice-bar" style="margin-top:16px">Verification: ${esc(p.verification_status)}. Documents are visible only to RideHub review staff.</div>`;
    } catch (error) { content.querySelector('.card').innerHTML = empty(error.message); }
  }

  async function reservations() {
    shell('Reservation centre', 'Paid bookings are already confirmed. Record the real-world handover and return here.', '<article class="card"><div class="loading-block">Loading confirmed rides…</div></article>', 'reservations');
    try {
      const data = await api('/api/shopkeeper/reservations/');
      content.querySelector('.card').innerHTML = data.reservations.length ? `<div id="reservation-message"></div><div class="admin-toolbar"><label><span>Search reservations</span><input id="reservation-search" type="search" placeholder="Booking ID, customer, email, phone, vehicle or date"></label></div><div class="table-wrap"><table class="user-table"><thead><tr><th>Customer & ride</th><th>Dates</th><th>Amount</th><th>Payment</th><th>Action</th></tr></thead><tbody>${data.reservations.map(b => `<tr data-reservation-row data-search="${esc(Object.values(b).join(' '))}"><td><strong>${esc(b.customer)} · ${esc(b.vehicle)}</strong><small>#${b.id} · ${esc(b.customer_email)} · ${esc(b.customer_phone)}</small></td><td>${date(b.pickup_date)}<small>to ${date(b.return_date)}</small></td><td>${money(b.total_amount)}</td><td><span class="payment-state ${esc(b.payment_status)}">${esc(b.payment_status)}</span><small>${esc(b.status)}</small></td><td>${b.payment_status === 'PAID' ? `<a class="row-action" href="/api/bookings/${b.id}/documents/receipt/">Receipt</a> <a class="row-action" href="/api/bookings/${b.id}/documents/confirmation/">Ticket</a> ` : ''}${b.status === 'CONFIRMED' ? `<button class="row-action" data-reservation="${b.id}" data-reservation-action="TAKEOVER">Vehicle takeover</button> <button class="row-action danger" data-reservation="${b.id}" data-reservation-action="CANCEL">Cancel ride</button>` : b.status === 'HANDED_OVER' ? `<button class="row-action" data-reservation="${b.id}" data-reservation-action="RECEIVED_BACK">Received back</button> <button class="row-action danger" data-reservation="${b.id}" data-reservation-action="CANCEL">Cancel ride</button>` : 'Processed'}</td></tr>`).join('')}</tbody></table></div>` : empty('No successful online reservations yet.'); bindRowSearch('reservation-search', '[data-reservation-row]');
    } catch (error) { content.querySelector('.card').innerHTML = empty(error.message); }
  }

  async function fares() {
    shell('Fare & pricing', 'Set the daily rate for your live vehicle listings.', '<article class="card"><div class="loading-block">Loading approved fleet…</div></article>', 'fares');
    try {
      const data = await api('/api/shopkeeper/vehicles/'); const fleet = data.vehicles.filter(v => v.listing_status === 'APPROVED');
      content.querySelector('.card').innerHTML = fleet.length ? `<div id="fare-message"></div><div class="admin-toolbar"><label><span>Search fares</span><input id="fare-search" type="search" placeholder="Vehicle, registration or rate"></label></div><div class="table-wrap"><table class="user-table"><thead><tr><th>Vehicle</th><th>Current daily fare</th><th>New daily fare</th><th>Action</th></tr></thead><tbody>${fleet.map(v => `<tr data-fare-row data-search="${esc(Object.values(v).join(' '))}"><td><strong>${esc(v.name)}</strong><small>${esc(v.registration_number)}</small></td><td>${money(v.daily_rate)}</td><td><input class="fare-input" type="number" min="0" step="0.01" value="${esc(v.daily_rate)}" data-fare-input="${v.id}"></td><td><button class="row-action" data-save-fare="${v.id}">Save fare</button></td></tr>`).join('')}</tbody></table></div>` : empty('No approved vehicles are available for pricing yet.'); bindRowSearch('fare-search', '[data-fare-row]');
    } catch (error) { content.querySelector('.card').innerHTML = empty(error.message); }
  }

  function openInspection(id, action) {
    const stage = action === 'TAKEOVER' ? 'pickup' : 'return';
    const fields = [['exterior','Exterior/body'],['lights','Lights'],['tires','Tyres'],['brakes','Brakes'],['mirrors','Mirrors'],['documents','Vehicle documents'],['keys','Keys']];
    const overlay = document.createElement('div'); overlay.className = 'checkout-overlay shop-inspection-overlay';
    overlay.innerHTML = `<section class="checkout-modal shop-inspection-modal" role="dialog" aria-modal="true" aria-labelledby="inspection-title"><button class="modal-close" type="button" aria-label="Close">×</button><p class="user-eyebrow">DIGITAL ${stage.toUpperCase()} INSPECTION</p><h2 id="inspection-title">${stage === 'pickup' ? 'Vehicle pickup' : 'Vehicle return'}</h2><p>Complete the checklist with the customer present. Scan their short-lived RideHub QR or enter the 6-digit code.</p><form id="shop-inspection-form"><label>Customer code<input name="code" inputmode="numeric" autocomplete="one-time-code" pattern="[0-9]{6}" minlength="6" maxlength="6" required></label><button class="ghost-button qr-scan-button" type="button" data-scan-handover-qr>Scan customer QR</button><p class="inspection-message" data-qr-message aria-live="polite"></p><div class="inspection-fields">${fields.map(([key,label]) => `<label>${label}<select name="${key}" required><option value="">Choose condition</option><option value="true">Pass</option><option value="false">Needs attention</option></select></label>`).join('')}</div><div class="inspection-fields"><label>Odometer (km)<input name="odometer_km" type="number" min="0" max="2000000" step="1" required></label><label>Fuel / battery (%)<input name="fuel_percent" type="number" min="0" max="100" step="1" required></label></div><label>Notes (optional)<textarea name="notes" maxlength="1000" rows="3"></textarea></label><p class="inspection-message" aria-live="polite"></p><button class="form-action" type="submit">Verify code & record ${stage} inspection</button></form></section>`;
    document.body.appendChild(overlay);
    const close = () => { overlay._stopQrScanner?.(); overlay.remove(); }; overlay.querySelector('.modal-close').addEventListener('click', close); overlay.addEventListener('click', event => { if (event.target === overlay) close(); });
    overlay.querySelector('[data-scan-handover-qr]')?.addEventListener('click', () => scanHandoverQr(overlay, id, stage));
    overlay.querySelector('#shop-inspection-form').addEventListener('submit', async event => {
      event.preventDefault(); const form = event.currentTarget; const submit = form.querySelector('[type="submit"]'); const messageTarget = form.querySelector('.inspection-message'); submit.disabled = true; messageTarget.textContent = 'Saving inspection…';
      const formData = new FormData(form); const condition_checklist = Object.fromEntries(fields.map(([key]) => [key, formData.get(key) === 'true']));
      const body = { action, code: formData.get('code'), odometer_km: formData.get('odometer_km'), fuel_percent: formData.get('fuel_percent'), condition_checklist, notes: formData.get('notes') };
      try { const result = await api(`/api/shopkeeper/reservations/${id}/action/`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)}); close(); message('reservation-message', result.message); setTimeout(reservations, 500); }
      catch (error) { messageTarget.textContent = error.message; messageTarget.classList.add('error'); submit.disabled = false; }
    });
  }

  async function scanHandoverQr(overlay, bookingId, stage) {
    const target = overlay.querySelector('[name="code"]'); const messageTarget = overlay.querySelector('[data-qr-message]'); const button = overlay.querySelector('[data-scan-handover-qr]');
    if (!navigator.mediaDevices?.getUserMedia) { messageTarget.textContent = 'This browser cannot access a camera. Enter the customer’s 6-digit code instead.'; messageTarget.classList.add('error'); return; }
    if (!('BarcodeDetector' in window)) { messageTarget.textContent = 'Camera permission is available, but QR detection is not supported by this browser. Use current Chrome/Edge or enter the customer’s 6-digit code.'; messageTarget.classList.add('error'); return; }
    let detector; let stream; let preview; let stopped = false; let frame;
    try { detector = new BarcodeDetector({ formats: ['qr_code'] }); }
    catch (_) { messageTarget.textContent = 'QR detection could not initialise. Enter the customer’s 6-digit code instead.'; messageTarget.classList.add('error'); return; }
    const stop = () => { stopped = true; if (frame) cancelAnimationFrame(frame); stream?.getTracks().forEach(track => track.stop()); preview?.remove(); if (button) button.disabled = false; };
    overlay._stopQrScanner?.(); overlay._stopQrScanner = stop;
    try {
      if (button) button.disabled = true;
      messageTarget.classList.remove('error'); messageTarget.textContent = 'Requesting camera permission…';
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' } } });
      const video = document.createElement('video'); video.autoplay = true; video.playsInline = true; video.srcObject = stream;
      preview = document.createElement('div'); preview.className = 'qr-camera-preview'; preview.append(video); overlay.querySelector('#shop-inspection-form').prepend(preview); await video.play(); messageTarget.textContent = 'Camera ready. Point it at the customer QR code…';
      const scan = async () => {
        if (stopped || !document.body.contains(overlay)) return stop();
        try {
          if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA) {
            const found = await detector.detect(video); const value = found[0]?.rawValue || ''; const match = /^ridehub-handover:v1:(\d+):(PICKUP|RETURN):(\d{6})$/.exec(value);
            if (match && Number(match[1]) === Number(bookingId) && match[2] === stage.toUpperCase()) { target.value = match[3]; stop(); messageTarget.textContent = 'QR verified. Continue with the checklist.'; return; }
            if (value) { messageTarget.textContent = 'This QR does not belong to this booking or handover stage.'; }
          }
        } catch (_) { /* Frames can be unavailable while a device refocuses; keep scanning. */ }
        frame = requestAnimationFrame(scan);
      };
      frame = requestAnimationFrame(scan);
    } catch (error) { stop(); const denied = error?.name === 'NotAllowedError' || error?.name === 'SecurityError'; messageTarget.textContent = denied ? 'Camera permission was denied. Allow camera access in your browser settings, or enter the 6-digit code.' : 'Camera could not start. Enter the customer’s 6-digit code instead.'; messageTarget.classList.add('error'); }
  }

  async function reservationAction(id, action) {
    if (action === 'TAKEOVER' || action === 'RECEIVED_BACK') return openInspection(id, action);
    const reason = prompt('Cancellation reason (this starts the customer refund):'); if (!reason) return;
    if (!confirm('Cancel this ride and initiate its refund?')) return;
    try { const data = await api(`/api/shopkeeper/reservations/${id}/action/`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({action, reason})}); message('reservation-message', data.message); setTimeout(reservations, 500); }
    catch (error) { message('reservation-message', error.message, true); }
  }
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

  document.addEventListener('input', event => {
    if (event.target.matches('[data-uppercase]')) event.target.value = event.target.value.toUpperCase();
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
