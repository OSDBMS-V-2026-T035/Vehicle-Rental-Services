(() => {
  const app = window.RIDEHUB_PORTAL || {};
  const content = document.querySelector('#portal-content');
  const nav = document.querySelector('#portal-nav');
  const crumb = document.querySelector('#crumb-label');
  const toast = document.querySelector('#portal-toast');
  const mapsKey = document.body.dataset.googleMapsKey || '';
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const iso = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
  const state = { page: 'overview', pickup: '', returnDate: '', type: 'all', location: '', latitude: '', longitude: '', vehicles: [], selectedVehicle: null };
  const labels = { overview: 'Overview', rides: 'Find a ride', shops: 'Nearby shops', bookings: 'My bookings', profile: 'Profile & security' };
  const icons = { overview: '◉', rides: '⌕', shops: '⌖', bookings: '▣', profile: '◌' };
  const escape = value => String(value ?? '').replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
  const csrf = () => app.csrf || document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
  const showToast = message => { toast.textContent = message; toast.classList.add('show'); clearTimeout(window.userPortalToast); window.userPortalToast = setTimeout(() => toast.classList.remove('show'), 3600); };
  const request = async (url, options = {}) => {
    const response = await fetch(url, { credentials: 'same-origin', ...options, headers: { 'X-CSRFToken': csrf(), ...(options.headers || {}) } });
    const data = await response.json().catch(() => ({ ok: false, message: 'The server returned an unexpected response.' }));
    if (!response.ok || data.ok === false) throw new Error(data.message || 'Something went wrong.');
    return data;
  };
  const dateParams = () => ({ pickup_date: state.pickup, return_date: state.returnDate });
  const queryString = values => new URLSearchParams(Object.entries(values).filter(([, value]) => value !== undefined && value !== null && value !== '')).toString();

  function renderNav() {
    nav.innerHTML = `<div class="nav-group">RENTAL DESK</div>${['overview', 'rides', 'shops', 'bookings'].map(key => `<button class="nav-item ${state.page === key ? 'active' : ''}" data-user-page="${key}"><span class="nav-icon">${icons[key]}</span>${labels[key]}</button>`).join('')}<div class="nav-group">ACCOUNT</div><button class="nav-item ${state.page === 'profile' ? 'active' : ''}" data-user-page="profile"><span class="nav-icon">${icons.profile}</span>Profile & security</button>`;
  }

  function locationControls() {
    return `<label class="user-field location-field"><span>Pickup location</span><span class="user-input-shell"><span class="field-symbol">⌖</span><input id="user-location" value="${escape(state.location)}" placeholder="Search a city, area or shop" autocomplete="off"><button type="button" class="location-use" id="use-user-location" title="Use current location">◎</button></span></label>`;
  }

  function searchPanel(mode = 'vehicles') {
    return `<section class="user-search-card" aria-label="Find a vehicle">
      <div class="search-card-heading"><div><p class="user-eyebrow">SMART DISCOVERY</p><h2>${mode === 'shops' ? 'Find verified rental shops' : 'Find your next ride'}</h2><p>Search availability around you and compare verified local listings.</p></div><span class="live-chip"><i></i> Live availability</span></div>
      <form id="user-search-form" class="user-search-form" data-search-mode="${mode}" novalidate>
        ${locationControls()}
        <label class="user-field"><span>Pickup date</span><span class="user-input-shell"><span class="field-symbol">▣</span><input id="user-pickup" type="date" value="${state.pickup}" min="${iso(today)}" required></span></label>
        <label class="user-field"><span>Return date</span><span class="user-input-shell"><span class="field-symbol">▣</span><input id="user-return" type="date" value="${state.returnDate}" min="${state.pickup || iso(today)}" max="${state.pickup ? iso(new Date(new Date(state.pickup).getTime() + 7 * 86400000)) : ''}" required></span></label>
        ${mode === 'vehicles' ? `<label class="user-field"><span>Vehicle type</span><span class="user-input-shell"><span class="field-symbol">▰</span><select id="user-type"><option value="all" ${state.type === 'all' ? 'selected' : ''}>All vehicles</option><option value="car" ${state.type === 'car' ? 'selected' : ''}>Cars</option><option value="bike" ${state.type === 'bike' ? 'selected' : ''}>Bikes</option><option value="scooter" ${state.type === 'scooter' ? 'selected' : ''}>Scooters</option><option value="cycle" ${state.type === 'cycle' ? 'selected' : ''}>Cycles</option><option value="commercial" ${state.type === 'commercial' ? 'selected' : ''}>Commercial</option></select></span></label>` : ''}
        <button class="user-primary-action search-action" type="submit"><span>⌕</span>${mode === 'shops' ? 'Find shops' : 'Search vehicles'}<b>→</b></button>
      </form><p id="user-search-message" class="user-form-message" role="status"></p></section>`;
  }

  function renderOverview() {
    content.innerHTML = `<div class="user-hero"><div><p class="user-eyebrow">RIDEHUB CUSTOMER SPACE</p><h1>Ready for your<br><em>next journey?</em></h1><p>Discover verified vehicles near you, compare rates and reserve in a few clear steps.</p></div><div class="hero-orbit"><span>R</span><small>Move freely.<br>Live more.</small></div></div>${searchPanel()}<div id="user-results" class="user-results" hidden></div><div class="user-section-heading"><div><p class="user-eyebrow">YOUR RIDEHUB</p><h2>Everything in one place</h2></div></div><div class="user-feature-grid"><button class="user-feature-card" data-user-page="rides"><span>⌕</span><strong>Find a ride</strong><small>Use live dates, location and vehicle type to compare nearby options.</small></button><button class="user-feature-card" data-user-page="bookings"><span>▣</span><strong>Track bookings</strong><small>Review upcoming, active and completed reservations with clear statuses.</small></button><button class="user-feature-card" data-user-page="shops"><span>⌖</span><strong>Explore shops</strong><small>See verified local shops, distance and directions before you book.</small></button></div>`;
    bindSearch();
  }

  function renderRides() {
    content.innerHTML = `${searchPanel()}<div id="user-results" class="user-results" hidden></div>`;
    bindSearch();
  }

  function renderShops() {
    content.innerHTML = `${searchPanel('shops')}<div id="user-results" class="user-results" hidden></div>`;
    bindSearch();
  }

  function setMessage(message, error = false) { const element = document.querySelector('#user-search-message'); if (element) { element.textContent = message; element.classList.toggle('error', error); } }

  function bindSearch() {
    const form = document.querySelector('#user-search-form');
    if (!form) return;
    const location = document.querySelector('#user-location');
    location.addEventListener('input', () => { state.location = location.value; state.latitude = ''; state.longitude = ''; });
    const pickup = document.querySelector('#user-pickup');
    const returnDate = document.querySelector('#user-return');
    pickup.addEventListener('change', () => { state.pickup = pickup.value; const max = new Date(new Date(state.pickup).getTime() + 7 * 86400000); returnDate.min = state.pickup; returnDate.max = iso(max); if (returnDate.value < state.pickup) returnDate.value = state.pickup; if (returnDate.value > iso(max)) returnDate.value = iso(max); });
    document.querySelector('#use-user-location')?.addEventListener('click', useCurrentLocation);
    form.addEventListener('submit', event => { event.preventDefault(); state.location = document.querySelector('#user-location').value.trim(); state.pickup = pickup.value; state.returnDate = returnDate.value; state.type = document.querySelector('#user-type')?.value || 'all'; runSearch(form.dataset.searchMode); });
    if (mapsKey) loadPlacesAutocomplete();
  }

  function useCurrentLocation() {
    if (!navigator.geolocation) return showToast('Location access is not available in this browser.');
    const button = document.querySelector('#use-user-location'); if (button) button.disabled = true;
    navigator.geolocation.getCurrentPosition(position => { state.latitude = position.coords.latitude.toFixed(6); state.longitude = position.coords.longitude.toFixed(6); state.location = `Current location (${state.latitude}, ${state.longitude})`; const input = document.querySelector('#user-location'); if (input) input.value = state.location; if (button) button.disabled = false; showToast('Current location added.'); }, () => { if (button) button.disabled = false; showToast('Location permission was not granted. Enter an area manually.'); }, { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 });
  }

  function loadPlacesAutocomplete() {
    if (window.google?.maps?.places?.Autocomplete) return attachPlaces();
    if (document.querySelector('script[data-user-maps]')) return;
    const script = document.createElement('script'); script.dataset.userMaps = 'true'; script.async = true; script.defer = true; script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(mapsKey)}&libraries=places&v=weekly`; script.onload = attachPlaces; script.onerror = () => showToast('Google location search is unavailable; manual search still works.'); document.head.appendChild(script);
  }

  function attachPlaces() {
    const input = document.querySelector('#user-location'); if (!input || input.dataset.placesAttached || !window.google?.maps?.places?.Autocomplete) return;
    const autocomplete = new google.maps.places.Autocomplete(input, { fields: ['formatted_address', 'geometry', 'name', 'place_id'] });
    autocomplete.addListener('place_changed', () => { const place = autocomplete.getPlace(); if (!place.geometry?.location) return; state.location = place.formatted_address || place.name || ''; state.latitude = place.geometry.location.lat().toFixed(6); state.longitude = place.geometry.location.lng().toFixed(6); }); input.dataset.placesAttached = 'true';
  }

  async function runSearch(mode = 'vehicles') {
    const results = document.querySelector('#user-results');
    if (!state.pickup || !state.returnDate) return setMessage('Choose both dates to search.', true);
    if (state.returnDate < state.pickup) return setMessage('Return date must be on or after pickup date.', true);
    setMessage('Searching verified listings around you…'); if (results) { results.hidden = false; results.innerHTML = '<div class="results-loading"><span></span><span></span><span></span>Checking live availability</div>'; }
    const locationQuery = state.latitude && state.longitude ? '' : state.location;
    const params = mode === 'shops' ? { q: locationQuery, latitude: state.latitude, longitude: state.longitude, radius: 50 } : { q: locationQuery, latitude: state.latitude, longitude: state.longitude, radius: 50, vehicle_type: state.type, ...dateParams() };
    try {
      const data = await request(`/api/${mode === 'shops' ? 'shops/search' : 'vehicles/search'}/?${queryString(params)}`);
      state.vehicles = mode === 'vehicles' ? data.vehicles : [];
      if (mode === 'vehicles') {
        const available = Number(data.available_count ?? data.count ?? 0);
        setMessage(`${available} available · ${data.count} matching listing${data.count === 1 ? '' : 's'} for your dates.`);
      } else {
        setMessage(`${data.count} verified shop${data.count === 1 ? '' : 's'} found.`);
      }
      mode === 'shops' ? renderShopResults(data.shops) : renderVehicleResults(data.vehicles);
    } catch (error) { setMessage(error.message, true); if (results) results.innerHTML = `<div class="results-empty"><span>⌖</span><strong>We could not load listings</strong><p>${escape(error.message)}</p></div>`; }
  }

  function renderVehicleResults(vehicles) {
    const results = document.querySelector('#user-results'); if (!results) return;
    if (!vehicles.length) { results.innerHTML = '<div class="results-empty"><span>⌖</span><strong>No verified vehicles nearby yet</strong><p>Try a wider area, another date, or a different vehicle type.</p></div>'; return; }
    results.innerHTML = `<div class="results-heading"><div><p class="user-eyebrow">MATCHED FOR YOUR DATES</p><h2>Vehicle availability</h2></div><small>Sorted by nearest shop</small></div><div class="vehicle-result-grid">${vehicles.map(vehicle => { const unavailable = vehicle.availability_status === 'UNAVAILABLE'; return `<article class="vehicle-result-card ${unavailable ? 'is-unavailable' : ''}"><div class="vehicle-result-image" style="background-image:url('${escape(vehicle.image_url)}')"><span>${escape(vehicle.type)}</span>${unavailable ? '<b class="unavailable-ribbon">UNAVAILABLE</b>' : ''}</div><div class="vehicle-result-body"><div class="result-title"><div><h3>${escape(vehicle.name)}</h3><small>${escape(vehicle.brand)} · ${escape(vehicle.model)}</small></div><strong>₹${escape(Number(vehicle.daily_rate).toLocaleString('en-IN'))}<small>/day</small></strong></div><p class="result-shop">⌖ ${escape(vehicle.shop)} <span>${vehicle.distance_km !== undefined ? `· ${escape(vehicle.distance_km)} km away` : ''}</span></p><p class="result-address">${escape(vehicle.address || 'Verified rental location')}</p><div class="result-availability ${unavailable ? 'unavailable' : ''}"><span>${unavailable ? '●' : '●'}</span>${escape(vehicle.availability_message || 'Available for your dates')}</div><div class="result-actions"><button class="user-secondary-action" data-select-vehicle="${vehicle.id}" ${unavailable ? 'disabled' : ''}>${unavailable ? 'Unavailable for selected dates' : 'View & reserve'}</button>${vehicle.directions_url ? `<a class="direction-link" href="${escape(vehicle.directions_url)}" target="_blank" rel="noopener">Directions ↗</a>` : ''}</div></div></article>`; }).join('')}</div>`;
  }

  function renderShopResults(shops) {
    const results = document.querySelector('#user-results'); if (!results) return;
    if (!shops.length) { results.innerHTML = '<div class="results-empty"><span>⌖</span><strong>No verified shops in this area</strong><p>Try another city or allow location access to search globally.</p></div>'; return; }
    results.innerHTML = `<div class="results-heading"><div><p class="user-eyebrow">VERIFIED LOCAL PARTNERS</p><h2>Rental shops near you</h2></div><small>${shops.length} locations</small></div><div class="shop-result-grid">${shops.map(shop => `<article class="shop-result-card"><span class="shop-icon">⌂</span><div><h3>${escape(shop.name)}</h3><p>${escape(shop.address)}</p><small>${shop.vehicle_count} approved vehicle${shop.vehicle_count === 1 ? '' : 's'}${shop.distance_km !== undefined ? ` · ${escape(shop.distance_km)} km away` : ''}</small></div>${shop.directions_url ? `<a class="direction-link" href="${escape(shop.directions_url)}" target="_blank" rel="noopener">Open directions ↗</a>` : ''}</article>`).join('')}</div>`;
  }

  function openCheckout(vehicle) {
    state.selectedVehicle = vehicle;
    const modal = document.createElement('div'); modal.className = 'checkout-overlay'; modal.innerHTML = `<section class="checkout-modal" role="dialog" aria-modal="true" aria-labelledby="checkout-title"><button class="modal-close" id="close-checkout" aria-label="Close">×</button><p class="user-eyebrow">SECURE RESERVATION</p><h2 id="checkout-title">Reserve ${escape(vehicle.name)}</h2><p class="modal-subtitle">${escape(vehicle.shop)} · ${escape(state.pickup)} to ${escape(state.returnDate)}</p><div class="checkout-summary"><span>Estimated rental total</span><strong>₹${escape(Number(vehicle.daily_rate * Math.max(1, (new Date(state.returnDate) - new Date(state.pickup)) / 86400000)).toLocaleString('en-IN'))}</strong></div><form id="checkout-form" class="checkout-form"><label>Full name<input name="full_name" value="${escape(app.name)}" required></label><div class="checkout-two"><label>Age<input name="age" type="number" min="18" max="90" placeholder="18+" required></label><label>Gender<select name="gender" required><option value="">Select</option><option value="male">Male</option><option value="female">Female</option><option value="non_binary">Non-binary</option><option value="prefer_not_to_say">Prefer not to say</option></select></label></div><label>Mobile number<input name="phone" inputmode="numeric" value="${escape(app.phone)}" maxlength="10" required></label><label>Verified email<input name="email" type="email" value="${escape(app.email)}" readonly><small class="verified-note">✓ Email verified on your RideHub account</small></label><label>Aadhaar number<input name="aadhaar" inputmode="numeric" maxlength="12" placeholder="12-digit Aadhaar number" required><small>Used only for checksum validation; the full number is never stored.</small></label><p id="checkout-message" class="checkout-message" role="status"></p><button class="user-primary-action" type="submit">Continue reservation <b>→</b></button></form></section>`; document.body.appendChild(modal); document.querySelector('#close-checkout').addEventListener('click', () => modal.remove()); modal.addEventListener('click', event => { if (event.target === modal) modal.remove(); }); document.querySelector('#checkout-form').addEventListener('submit', event => submitCheckout(event, modal)); }

  async function startPayment(paymentId, modal) {
    const payButton = modal.querySelector('#pay-reservation');
    if (typeof window.Razorpay !== 'function') { showToast('Secure checkout did not load. Check your connection and try again.'); return; }
    payButton.disabled = true;
    try {
      const order = await request(`/api/payments/razorpay/order/${paymentId}/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      const checkout = new window.Razorpay({
        key: order.key_id, amount: order.amount, currency: order.currency, order_id: order.order_id,
        name: 'RideHub', description: order.description, prefill: order.prefill, theme: { color: '#236ee8' },
        handler: async response => {
          try {
            const result = await request('/api/payments/razorpay/verify/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...response, payment_id: order.payment_id }) });
            showToast(result.message); modal.remove(); go('bookings');
          } catch (error) { showToast(error.message); payButton.disabled = false; }
        },
      });
      checkout.on('payment.failed', () => { showToast('Payment was not completed. You can safely try again.'); payButton.disabled = false; });
      checkout.open();
    } catch (error) { showToast(error.message); payButton.disabled = false; }
  }

  async function submitCheckout(event, modal) {
    event.preventDefault(); const form = event.currentTarget; const message = form.querySelector('#checkout-message'); const button = form.querySelector('button[type="submit"]'); const payload = Object.fromEntries(new FormData(form).entries()); Object.assign(payload, { vehicle_id: state.selectedVehicle.id, pickup_date: state.pickup, return_date: state.returnDate }); message.textContent = 'Validating details and holding the vehicle…'; message.className = 'checkout-message'; button.disabled = true;
    try { const data = await request('/api/bookings/checkout/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) }); modal.querySelector('.checkout-modal').innerHTML = `<button class="modal-close" id="close-checkout" aria-label="Close">×</button><div class="checkout-success"><span>✓</span><p class="user-eyebrow">RESERVATION CREATED</p><h2>Your ride is on hold.</h2><p>${escape(data.message)}</p><div class="success-reference"><small>Booking reference</small><strong>RH-${String(data.booking_id).padStart(6, '0')}</strong><small>Estimated total · ₹${escape(Number(data.total_amount).toLocaleString('en-IN'))}</small></div><button class="user-primary-action" id="pay-reservation">Pay securely <b>→</b></button><button class="user-secondary-action" id="view-bookings">Pay later</button></div>`; modal.querySelector('#close-checkout').addEventListener('click', () => modal.remove()); modal.querySelector('#pay-reservation').addEventListener('click', () => startPayment(data.payment_id, modal)); modal.querySelector('#view-bookings').addEventListener('click', () => { modal.remove(); go('bookings'); }); } catch (error) { message.textContent = error.message; message.className = 'checkout-message error'; button.disabled = false; }
  }

  async function renderBookings() {
    content.innerHTML = '<div class="user-page-heading"><p class="user-eyebrow">RESERVATION HISTORY</p><h1>My bookings</h1><p>Keep every ride, date and shop detail in one clear timeline.</p></div><div id="booking-list" class="booking-list"><div class="results-loading"><span></span><span></span><span></span>Loading your bookings</div></div>';
    try { const data = await request('/api/bookings/history/'); const list = document.querySelector('#booking-list'); list.innerHTML = data.bookings.length ? data.bookings.map(booking => `<article class="booking-card"><div class="booking-card-icon">▣</div><div class="booking-card-main"><div class="booking-card-title"><div><h3>${escape(booking.vehicle)}</h3><p>${escape(booking.shop)}</p></div><span class="booking-status status-${booking.status.toLowerCase()}">${escape(booking.status)}</span></div><div class="booking-meta"><span>Pickup <strong>${escape(booking.pickup_date)}</strong></span><span>Return <strong>${escape(booking.return_date)}</strong></span><span>Total <strong>₹${escape(Number(booking.total_amount).toLocaleString('en-IN'))}</strong></span></div></div></article>`).join('') : '<div class="results-empty"><span>▣</span><strong>No bookings yet</strong><p>Your confirmed reservations will appear here after you reserve a vehicle.</p><button class="user-secondary-action" data-user-page="rides">Find a ride</button></div>'; } catch (error) { document.querySelector('#booking-list').innerHTML = `<div class="results-empty"><strong>Could not load bookings</strong><p>${escape(error.message)}</p></div>`; }
  }

  function renderProfile() {
    content.innerHTML = `<div class="user-page-heading"><p class="user-eyebrow">ACCOUNT CENTRE</p><h1>Profile & security</h1><p>Your identity and account controls stay protected inside RideHub.</p></div><div class="profile-grid"><section class="profile-card"><div class="profile-card-heading"><span class="profile-avatar">${escape((app.name || 'R').slice(0, 1).toUpperCase())}</span><div><h2>${escape(app.name || 'RideHub user')}</h2><p>Customer account</p></div></div><dl class="profile-details"><div><dt>Email address</dt><dd>${escape(app.email)} <span class="verified-pill">${app.emailVerified ? '✓ Verified' : 'Pending'}</span></dd></div><div><dt>Mobile number</dt><dd>+91 ${escape(app.phone)}</dd></div><div><dt>Access level</dt><dd>Verified customer</dd></div></dl></section><section class="profile-card security-card"><p class="user-eyebrow">TRUST & SAFETY</p><h2>Booking safeguards</h2><div class="safety-list"><p><span>✓</span> Email verified before reservation</p><p><span>✓</span> Vehicle availability checked inside a database transaction</p><p><span>✓</span> Aadhaar checksum validation with masked storage</p><p><span>✓</span> No payment information is collected at this stage</p></div></section></div>`;
  }

  function go(page) { state.page = page; crumb.textContent = labels[page] || 'Overview'; renderNav(); document.querySelector('#portal-sidebar').classList.remove('open'); if (page === 'overview') renderOverview(); else if (page === 'rides') renderRides(); else if (page === 'shops') renderShops(); else if (page === 'bookings') renderBookings(); else renderProfile(); window.scrollTo({ top: 0, behavior: 'auto' }); }
  document.addEventListener('click', event => { const page = event.target.closest('[data-user-page]')?.dataset.userPage; if (page) go(page); const vehicleId = event.target.closest('[data-select-vehicle]')?.dataset.selectVehicle; if (vehicleId) { const vehicle = state.vehicles.find(item => String(item.id) === String(vehicleId)); if (vehicle) openCheckout(vehicle); } });
  document.querySelector('#mobile-menu').addEventListener('click', () => document.querySelector('#portal-sidebar').classList.toggle('open'));
  document.querySelector('#profile-shortcut').addEventListener('click', () => go('profile'));
  document.querySelector('#logout-button').addEventListener('click', async () => { try { await request('/api/auth/logout/', { method: 'POST' }); } finally { window.location.assign('/auth/'); } });
  go('overview');
})();
