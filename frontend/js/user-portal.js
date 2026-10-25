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
  const initialBooking = new URLSearchParams(window.location.search);
  const state = { page: app.section || 'overview', pickup: initialBooking.get('pickup_date') || '', returnDate: initialBooking.get('return_date') || '', type: 'all', location: '', latitude: '', longitude: '', maxRate: '', minSeats: '', fuel: 'all', sort: 'recommended', vehicles: [], selectedVehicle: null };
  const labels = { overview: 'Overview', rides: 'Find a ride', shops: 'Nearby shops', bookings: 'My bookings', profile: 'Profile & security', checkout: 'Secure checkout' };
  const icons = { overview: '◉', rides: '⌕', shops: '⌖', bookings: '▣', profile: '◌', checkout: '₹' };
  const escape = value => String(value ?? '').replace(/[&<>'"]/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[char]));
  const csrf = () => app.csrf || document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1] || '';
  const showToast = message => { toast.textContent = message; toast.classList.add('show'); clearTimeout(window.userPortalToast); window.userPortalToast = setTimeout(() => toast.classList.remove('show'), 3600); };
  const request = async (url, options = {}) => {
    const response = await fetch(url, { credentials: 'same-origin', ...options, headers: { 'X-CSRFToken': csrf(), ...(options.headers || {}) } });
    const data = await response.json().catch(() => ({ ok: false, message: 'The server returned an unexpected response.' }));
    if (!response.ok || data.ok === false) throw new Error(data.message || 'Something went wrong.');
    return data;
  };
  const razorpayCheckoutUrl = 'https://checkout.razorpay.com/v1/checkout.js';
  const loadRazorpayCheckout = () => {
    if (typeof window.Razorpay === 'function') return Promise.resolve();
    // Retry the provider script once. This avoids a stuck/blank checkout when
    // its first CDN request was interrupted while the portal was loading.
    document.querySelector('script[data-razorpay-checkout]')?.remove();
    return new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = razorpayCheckoutUrl; script.async = true; script.dataset.razorpayCheckout = 'retry';
      script.onload = () => typeof window.Razorpay === 'function' ? resolve() : reject(new Error('Razorpay Checkout did not initialise.'));
      script.onerror = () => reject(new Error('Razorpay Checkout could not be loaded. Check your internet connection and try again.'));
      document.head.appendChild(script);
    });
  };
  const dateParams = () => ({ pickup_date: state.pickup, return_date: state.returnDate });
  const queryString = values => new URLSearchParams(Object.entries(values).filter(([, value]) => value !== undefined && value !== null && value !== '')).toString();

  function renderNav() {
    nav.innerHTML = `<div class="nav-group">RENTAL DESK</div>${['overview', 'rides', 'shops', 'bookings'].map(key => `<button class="nav-item ${state.page === key ? 'active' : ''}" data-user-page="${key}"><span class="nav-icon">${icons[key]}</span>${labels[key]}</button>`).join('')}${state.page === 'checkout' ? `<button class="nav-item active" aria-current="page"><span class="nav-icon">${icons.checkout}</span>${labels.checkout}</button>` : ''}<div class="nav-group">ACCOUNT</div><button class="nav-item ${state.page === 'profile' ? 'active' : ''}" data-user-page="profile"><span class="nav-icon">${icons.profile}</span>Profile & security</button>`;
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
        ${mode === 'vehicles' ? `<label class="user-field"><span>Vehicle type</span><span class="user-input-shell"><span class="field-symbol">▰</span><select id="user-type"><option value="all" ${state.type === 'all' ? 'selected' : ''}>All vehicles</option><option value="car" ${state.type === 'car' ? 'selected' : ''}>Cars</option><option value="bike" ${state.type === 'bike' ? 'selected' : ''}>Bikes</option><option value="scooter" ${state.type === 'scooter' ? 'selected' : ''}>Scooters</option><option value="cycle" ${state.type === 'cycle' ? 'selected' : ''}>Cycles</option><option value="commercial" ${state.type === 'commercial' ? 'selected' : ''}>Commercial</option></select></span></label><label class="user-field"><span>Daily budget (₹ max)</span><span class="user-input-shell"><input id="user-budget" type="number" min="0" step="100" placeholder="Any budget" value="${escape(state.maxRate)}"></span></label><label class="user-field"><span>Minimum seats</span><span class="user-input-shell"><input id="user-seats" type="number" min="1" max="100" step="1" placeholder="Any" value="${escape(state.minSeats)}"></span></label><label class="user-field"><span>Fuel</span><span class="user-input-shell"><select id="user-fuel"><option value="all">Any fuel</option>${['petrol','diesel','electric','cng','hybrid','other'].map(fuel => `<option value="${fuel}" ${state.fuel === fuel ? 'selected' : ''}>${fuel[0].toUpperCase()}${fuel.slice(1)}</option>`).join('')}</select></span></label><label class="user-field"><span>Sort by</span><span class="user-input-shell"><select id="user-sort"><option value="recommended" ${state.sort === 'recommended' ? 'selected' : ''}>Recommended</option><option value="nearest" ${state.sort === 'nearest' ? 'selected' : ''}>Nearest first</option><option value="price_low" ${state.sort === 'price_low' ? 'selected' : ''}>Price: low to high</option><option value="price_high" ${state.sort === 'price_high' ? 'selected' : ''}>Price: high to low</option></select></span></label>` : ''}
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
    form.addEventListener('submit', event => { event.preventDefault(); state.location = document.querySelector('#user-location').value.trim(); state.pickup = pickup.value; state.returnDate = returnDate.value; state.type = document.querySelector('#user-type')?.value || 'all'; state.maxRate = document.querySelector('#user-budget')?.value || ''; state.minSeats = document.querySelector('#user-seats')?.value || ''; state.fuel = document.querySelector('#user-fuel')?.value || 'all'; state.sort = document.querySelector('#user-sort')?.value || 'recommended'; runSearch(form.dataset.searchMode); });
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
    const params = mode === 'shops' ? { q: locationQuery, latitude: state.latitude, longitude: state.longitude, radius: 15 } : { q: locationQuery, latitude: state.latitude, longitude: state.longitude, radius: 15, vehicle_type: state.type, max_daily_rate: state.maxRate, min_seats: state.minSeats, fuel_type: state.fuel, sort: state.sort, ...dateParams() };
    try {
      const data = await request(`/api/${mode === 'shops' ? 'shops/search' : 'vehicles/search'}/?${queryString(params)}`);
      state.vehicles = mode === 'vehicles' ? data.vehicles : [];
      if (mode === 'shops') window.__ridehubShops = data.shops || [];
      if (mode === 'vehicles') {
        const availableListings = Number(data.available_count ?? data.count ?? 0);
        const availableUnits = Number(data.available_units_count ?? availableListings);
        const unavailableListings = Math.max(0, Number(data.count || 0) - availableListings);
        setMessage(`${availableUnits} vehicle unit${availableUnits === 1 ? '' : 's'} available across ${availableListings} listing${availableListings === 1 ? '' : 's'}; ${unavailableListings} fully booked listing${unavailableListings === 1 ? '' : 's'} shown for your dates.`);
      } else {
        setMessage(`${data.count} verified shop${data.count === 1 ? '' : 's'} found.`);
      }
      mode === 'shops' ? renderShopResults(data.shops) : renderVehicleResults(data.vehicles);
    } catch (error) { setMessage(error.message, true); if (results) results.innerHTML = `<div class="results-empty"><span>⌖</span><strong>We could not load listings</strong><p>${escape(error.message)}</p></div>`; }
  }

  function renderVehicleResults(vehicles) {
    const results = document.querySelector('#user-results'); if (!results) return;
    if (!vehicles.length) { results.innerHTML = '<div class="results-empty"><span>⌖</span><strong>No verified vehicles nearby yet</strong><p>Try a wider area, another date, or a different vehicle type.</p></div>'; return; }
    const sortLabels = { recommended: 'Recommended match', nearest: 'Nearest first', price_low: 'Lowest daily rate', price_high: 'Highest daily rate' };
    results.innerHTML = `<div class="results-heading"><div><p class="user-eyebrow">MATCHED FOR YOUR DATES</p><h2>Vehicle availability</h2></div><small>${escape(sortLabels[state.sort] || sortLabels.recommended)}</small></div><div class="vehicle-result-grid">${vehicles.map(vehicle => { const unavailable = vehicle.availability_status === 'UNAVAILABLE'; return `<article class="vehicle-result-card ${unavailable ? 'is-unavailable' : ''}"><div class="vehicle-result-image" style="background-image:url('${escape(vehicle.image_url)}')"><span>${escape(vehicle.type)}</span>${unavailable ? '<b class="unavailable-ribbon">UNAVAILABLE</b>' : ''}</div><div class="vehicle-result-body"><div class="result-title"><div><h3>${escape(vehicle.name)}</h3><small>${escape(vehicle.brand)} · ${escape(vehicle.model)}</small></div><strong>₹${escape(Number(vehicle.daily_rate).toLocaleString('en-IN'))}<small>/day</small></strong></div><p class="result-shop">⌖ ${escape(vehicle.shop)} <span>${vehicle.distance_km !== undefined ? `· ${escape(vehicle.distance_km)} km away` : ''}</span></p><p class="result-address">${escape(vehicle.address || 'Verified rental location')}</p><div class="result-availability ${unavailable ? 'unavailable' : ''}"><span>●</span>${escape(vehicle.availability_message || 'Available for your dates')}</div><div class="result-actions"><button class="user-secondary-action" data-vehicle-details="${vehicle.id}">${unavailable ? 'View unavailable details' : 'View details'}</button>${vehicle.directions_url ? `<a class="direction-link" href="${escape(vehicle.directions_url)}" target="_blank" rel="noopener">Directions ↗</a>` : ''}</div></div></article>`; }).join('')}</div>`;
  }

  function shopMonogram(shop) {
    return escape(shop.monogram || shop.name.split(/\s+/).map(word => word[0]).slice(0, 2).join('').toUpperCase() || 'RH');
  }

  function renderShopResults(shops) {
    const results = document.querySelector('#user-results'); if (!results) return;
    if (!shops.length) { results.innerHTML = '<div class="results-empty"><span>⌖</span><strong>No verified shops in this area</strong><p>Try another city or allow location access to search globally.</p></div>'; return; }
    results.innerHTML = `<div class="results-heading"><div><p class="user-eyebrow">VERIFIED LOCAL PARTNERS</p><h2>Rental shops near you</h2></div><small>${shops.length} locations</small></div><div class="shop-result-grid">${shops.map(shop => `<article class="shop-result-card"><button class="shop-result-main" data-open-shop="${shop.id}" aria-label="Open ${escape(shop.name)} listings"><span class="shop-logo" aria-hidden="true">${shopMonogram(shop)}</span><span class="shop-result-copy"><strong>${escape(shop.name)}</strong><span>${escape(shop.address || 'Verified rental location')}</span><small>${shop.vehicle_count} live vehicle unit${shop.vehicle_count === 1 ? '' : 's'}${shop.distance_km !== undefined ? ` · ${escape(shop.distance_km)} km away` : ''}</small></span><span class="shop-open-arrow">→</span></button>${shop.directions_url ? `<a class="direction-link" href="${escape(shop.directions_url)}" target="_blank" rel="noopener">Open directions ↗</a>` : ''}</article>`).join('')}</div>`;
  }

  async function openShopListings(shop) {
    const modal = document.createElement('div'); modal.className = 'shop-listing-overlay';
    modal.innerHTML = `<section class="shop-listing-modal" role="dialog" aria-modal="true" aria-labelledby="shop-listing-title"><button class="modal-close" data-close-shop aria-label="Close">×</button><p class="user-eyebrow">VERIFIED PARTNER</p><h2 id="shop-listing-title">${escape(shop.name)}</h2><p class="modal-subtitle">${escape(shop.address || 'Verified rental location')} · Live inventory for your selected dates.</p><div class="shop-listing-loading results-loading"><span></span><span></span><span></span>Loading vehicles</div><div class="shop-listing-content"></div></section>`;
    document.body.appendChild(modal);
    const close = () => modal.remove(); modal.querySelector('[data-close-shop]').addEventListener('click', close); modal.addEventListener('click', event => { if (event.target === modal) close(); });
    try {
      const data = await request(`/api/vehicles/search/?${queryString({shop_id: shop.id, pickup_date: state.pickup, return_date: state.returnDate})}`);
      state.vehicles = [...state.vehicles, ...data.vehicles.filter(item => !state.vehicles.some(existing => String(existing.id) === String(item.id)))];
      const target = modal.querySelector('.shop-listing-content'); modal.querySelector('.shop-listing-loading').remove();
      target.innerHTML = data.vehicles.length ? `<div class="shop-listing-grid">${data.vehicles.map(vehicle => { const unavailable = vehicle.availability_status === 'UNAVAILABLE'; return `<article class="shop-listing-card ${unavailable ? 'is-unavailable' : ''}"><img src="${escape(vehicle.image_url)}" alt="${escape(vehicle.name)}"><div><div class="shop-listing-card-title"><h3>${escape(vehicle.name)}</h3><strong>₹${escape(Number(vehicle.daily_rate).toLocaleString('en-IN'))}<small>/day</small></strong></div><p>${escape(vehicle.body_style || vehicle.type)} · ${vehicle.seating_capacity} seats · ${escape(vehicle.fuel_type || 'Fuel details unavailable')}</p><span class="result-availability ${unavailable ? 'unavailable' : ''}">● ${escape(vehicle.availability_message || 'Available')}</span><button class="user-secondary-action" data-vehicle-details="${vehicle.id}">${unavailable ? 'View details' : 'View & reserve'}</button></div></article>`; }).join('')}</div>` : '<div class="results-empty"><span>⌖</span><strong>No vehicles available at this shop</strong><p>This shop has no approved inventory for the selected dates.</p></div>';
    } catch (error) { modal.querySelector('.shop-listing-loading').outerHTML = `<div class="results-empty"><strong>Could not load this shop</strong><p>${escape(error.message)}</p></div>`; }
  }

  async function resumeBookingFromAuth() {
    const vehicleId = initialBooking.get('vehicle_id');
    if (initialBooking.get('checkout') !== '1' || !/^\d+$/.test(vehicleId || '') || !state.pickup || !state.returnDate) return;
    try {
      const data = await request(`/api/vehicles/${vehicleId}/?${queryString({ pickup_date: state.pickup, return_date: state.returnDate })}`);
      const vehicle = data.vehicle;
      if (vehicle.availability_status === 'UNAVAILABLE') throw new Error('That vehicle is no longer available for the selected dates. Please search again.');
      state.vehicles = [vehicle];
      const dedicated = app.section === 'checkout';
      if (!dedicated) window.history.replaceState({}, document.title, '/user-portal/');
      openCheckout(vehicle, dedicated);
    } catch (error) {
      showToast(error.message);
    }
  }

  function openVehicleDetails(vehicle) {
    const modal = document.createElement('div'); modal.className = 'shop-listing-overlay'; const unavailable = vehicle.availability_status === 'UNAVAILABLE';
    modal.innerHTML = `<section class="vehicle-detail-modal" role="dialog" aria-modal="true"><button class="modal-close" data-close-vehicle aria-label="Close">×</button><img src="${escape(vehicle.image_url)}" alt="${escape(vehicle.name)}"><div class="vehicle-detail-body"><p class="user-eyebrow">${escape(vehicle.type)} · ${escape(vehicle.listing_status)}</p><h2>${escape(vehicle.name)}</h2><p class="modal-subtitle">${escape(vehicle.shop)} · ${escape(vehicle.address || '')}</p><div class="vehicle-spec-grid"><span><small>Body style</small><b>${escape(vehicle.body_style || 'Standard')}</b></span><span><small>Seats</small><b>${escape(vehicle.seating_capacity)}</b></span><span><small>Fuel</small><b>${escape(vehicle.fuel_type || '—')}</b></span><span><small>Capacity</small><b>${escape(vehicle.fuel_capacity || '—')} L</b></span><span><small>Inventory</small><b>${escape(vehicle.availability_message || '—')}</b></span><span><small>Rate</small><b>₹${escape(Number(vehicle.daily_rate).toLocaleString('en-IN'))}/day</b></span></div><p class="vehicle-detail-description">${escape(vehicle.description || 'Verified rental vehicle with shop-managed availability.')}</p><div class="result-actions"><button class="user-primary-action" data-reserve-vehicle="${vehicle.id}" ${unavailable ? 'disabled' : ''}>${unavailable ? 'Unavailable for selected dates' : 'Continue to checkout'} <b>→</b></button>${vehicle.directions_url ? `<a class="direction-link" href="${escape(vehicle.directions_url)}" target="_blank" rel="noopener">Directions ↗</a>` : ''}</div></div></section>`;
    document.body.appendChild(modal); const close = () => modal.remove(); modal.querySelector('[data-close-vehicle]').addEventListener('click', close); modal.addEventListener('click', event => { if (event.target === modal) close(); }); modal.querySelector('[data-reserve-vehicle]')?.addEventListener('click', () => { close(); openCheckout(vehicle); });
  }

  async function openCheckout(vehicle, dedicated = false) {
    state.selectedVehicle = vehicle;
    let defaults = { full_name: app.name, age: '', gender: '', phone: app.phone, email: app.email };
    try { defaults = { ...defaults, ...(await request('/api/bookings/checkout/defaults/')).defaults }; } catch (_) { /* Checkout stays available with account details. */ }
    const aadhaarKey = `ridehub-checkout-aadhaar-${app.email}`;
    const rememberedAadhaarDigits = (sessionStorage.getItem(aadhaarKey) || '').replace(/\D/g, '');
    const rememberedAadhaar = rememberedAadhaarDigits.length === 12 ? rememberedAadhaarDigits.replace(/(\d{4})(?=\d)/g, '$1 ').trim() : '';
    const selectedGender = value => defaults.gender === value ? 'selected' : '';
    const rentalDays = Math.max(1, Math.round((new Date(`${state.returnDate}T00:00:00`) - new Date(`${state.pickup}T00:00:00`)) / 86400000));
    const rentalFare = Number(vehicle.daily_rate) * rentalDays;
    const modal = dedicated ? content : document.createElement('div');
    modal.className = dedicated ? 'checkout-page-shell' : 'checkout-overlay';
    modal.innerHTML = `<section class="checkout-modal${dedicated ? ' checkout-page-card' : ''}" role="dialog" aria-modal="${dedicated ? 'false' : 'true'}" aria-labelledby="checkout-title">${dedicated ? '<a class="user-secondary-action checkout-back" href="/user-portal/rides/">← Back to rides</a>' : '<button class="modal-close" id="close-checkout" aria-label="Close">×</button>'}<p class="user-eyebrow">SECURE RESERVATION</p><h2 id="checkout-title">Reserve your RideHub vehicle</h2><div class="checkout-vehicle-card"><img src="${escape(vehicle.image_url)}" alt="${escape(vehicle.name)}"><div><strong>${escape(vehicle.name)}</strong><small>${escape(vehicle.type)} · ${escape(vehicle.fuel_type || 'Fuel details unavailable')} · ${escape(vehicle.seating_capacity)} seats</small><small>${escape(vehicle.shop)} · ${escape(vehicle.address || 'Verified rental location')}</small></div></div><div class="checkout-date-grid"><span><small>Pickup</small><b>${escape(state.pickup)}</b></span><span><small>Return</small><b>${escape(state.returnDate)}</b></span><span><small>Duration</small><b>${rentalDays} day${rentalDays === 1 ? '' : 's'}</b></span></div><div class="checkout-summary checkout-fare-summary"><span>Rental fare (${rentalDays} × ₹${escape(Number(vehicle.daily_rate).toLocaleString('en-IN'))})<small>Tax-exclusive; RideHub has no configured GST charge.</small></span><strong>₹${escape(rentalFare.toLocaleString('en-IN'))}</strong></div><form id="checkout-form" class="checkout-form"><h3>Renter details</h3><label>Full name<input name="full_name" value="${escape(defaults.full_name || app.name)}" required></label><div class="checkout-two"><label>Age<input name="age" type="number" min="18" max="90" placeholder="18+" value="${escape(defaults.age || '')}" required></label><label>Gender<select name="gender" required><option value="">Select</option><option value="male" ${selectedGender('male')}>Male</option><option value="female" ${selectedGender('female')}>Female</option><option value="non_binary" ${selectedGender('non_binary')}>Non-binary</option><option value="prefer_not_to_say" ${selectedGender('prefer_not_to_say')}>Prefer not to say</option></select></label></div><label>Mobile number<input name="phone" inputmode="numeric" value="${escape(defaults.phone || app.phone)}" maxlength="10" required></label><label>Verified email<input name="email" type="email" value="${escape(defaults.email || app.email)}" readonly><small class="verified-note">✓ Email verified on your RideHub account</small></label><label>Aadhaar number<input name="aadhaar" inputmode="numeric" maxlength="14" value="${escape(rememberedAadhaar)}" placeholder="12-digit Aadhaar number" required><small>Enter exactly 12 digits. Spaces are added automatically; the complete number is never stored by RideHub.</small></label><p id="checkout-message" class="checkout-message" role="status"></p><button class="user-primary-action" type="submit">Continue to secure payment <b>→</b></button></form></section>`;
    if (!dedicated) document.body.appendChild(modal);
    const aadhaarInput = modal.querySelector('[name="aadhaar"]'); aadhaarInput.addEventListener('input', () => { const digits = aadhaarInput.value.replace(/\D/g, '').slice(0, 12); aadhaarInput.value = digits.replace(/(\d{4})(?=\d)/g, '$1 ').trim(); });
    if (!dedicated) { modal.querySelector('#close-checkout').addEventListener('click', () => modal.remove()); modal.addEventListener('click', event => { if (event.target === modal) modal.remove(); }); }
    modal.querySelector('#checkout-form').addEventListener('submit', event => submitCheckout(event, modal)); }

  async function reconcilePayment(paymentId, bookingId, modal = null) {
    if (!paymentId) return false;
    try {
      const result = await request(`/api/payments/razorpay/reconcile/${paymentId}/`, { method:'POST', headers:{'Content-Type':'application/json'}, body:'{}' });
      if (result.status === 'PAID') {
        if (modal) { await showPaymentSuccess(modal, bookingId); return true; }
        sessionStorage.setItem('ridehub-payment-success-booking', String(bookingId));
        window.location.assign(`/user-portal/bookings/?success=${encodeURIComponent(bookingId)}`);
        return true;
      }
      return false;
    } catch (_) { return false; }
  }

  async function showPaymentSuccess(modal, bookingId) {
    try {
      const data = await request('/api/bookings/history/');
      const booking = data.bookings.find(item => String(item.id) === String(bookingId));
      if (!booking || booking.payment?.status !== 'PAID') throw new Error('Booking refresh pending');
      const ticket = booking.status !== 'CANCELLED' ? `<a class="user-secondary-action" href="/api/bookings/${booking.id}/documents/confirmation/">Download ride ticket</a>` : '';
      modal.querySelector('.checkout-modal').innerHTML = `<div class="checkout-success"><span>✓</span><p class="user-eyebrow">PAYMENT SUCCESSFUL</p><h2>Your ride is booked.</h2><p>Payment is confirmed. Download your documents now or find them later in My bookings.</p><div class="success-reference"><small>Booking reference</small><strong>RH-${String(booking.id).padStart(6, '0')}</strong><small>₹${escape(Number(booking.payment.amount || booking.total_amount).toLocaleString('en-IN'))} · Paid online</small></div><div class="result-actions"><a class="user-primary-action" href="/api/bookings/${booking.id}/documents/receipt/">Download payment receipt</a>${ticket}</div><a class="user-secondary-action" href="/user-portal/bookings/">View my bookings</a></div>`;
    } catch (_) {
      sessionStorage.setItem('ridehub-payment-success-booking', String(bookingId));
      window.location.assign(`/user-portal/bookings/?success=${encodeURIComponent(bookingId)}`);
    }
  }

  async function startPayment(paymentId, modal, bookingId, prefetchedOrder = null) {
    const payButton = modal.querySelector('#pay-reservation');
    try { await loadRazorpayCheckout(); }
    catch (error) { showToast(error.message); payButton.disabled = false; return; }
    payButton.disabled = true;
    try {
      const order = prefetchedOrder || await request(`/api/payments/razorpay/order/${paymentId}/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
      let paymentCompletionStarted = false;
      let reconciliationInFlight = false;
      let reconciliationTimer = null;
      const stopReconciliation = () => {
        if (reconciliationTimer) window.clearInterval(reconciliationTimer);
        reconciliationTimer = null;
      };
      // Some bank/UPI flows return through a secondary browser window. If that
      // window prevents Razorpay's JavaScript handler from reaching the opener,
      // ask our server about the order instead of leaving the customer stranded.
      const recoverCompletedPayment = async () => {
        if (paymentCompletionStarted || reconciliationInFlight) return false;
        reconciliationInFlight = true;
        try {
          const confirmed = await reconcilePayment(paymentId, bookingId, modal);
          if (confirmed) {
            paymentCompletionStarted = true;
            stopReconciliation();
            return true;
          }
        } finally {
          reconciliationInFlight = false;
        }
        return false;
      };
      const checkout = new window.Razorpay({
        key: order.key_id, amount: order.amount, currency: order.currency, order_id: order.order_id,
        name: 'RideHub', description: order.description,
        // Do not filter methods here. Availability is configured in the
        // Razorpay account and differs between test accounts; forcing UPI can
        // leave Checkout with no eligible method at all.
        prefill: order.prefill,
        theme: { color: '#236ee8' },
        // Keep the standard web checkout on RideHub and return payment data to
        // the handler; do not hand the browser off to a gateway callback page.
        redirect: false,
        retry: { enabled: true },
        // Razorpay closes its popup before invoking the success handler. Do not
        // cancel a reservation once that verified-payment flow has started.
        modal: { backdropclose: false, escape: false, confirm_close: true, ondismiss: async () => { stopReconciliation(); if (!paymentCompletionStarted) { const confirmed = await recoverCompletedPayment(); if (!confirmed) { payButton.disabled = false; showToast('Payment window closed. Your reservation is still active; you can safely retry payment.'); } } } },
        handler: async response => {
          paymentCompletionStarted = true;
          stopReconciliation();
          try {
            const result = await request('/api/payments/razorpay/verify/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...response, payment_id: order.payment_id }) });
            await showPaymentSuccess(modal, bookingId);
          } catch (error) { paymentCompletionStarted = false; showToast(error.message); payButton.disabled = false; }
        },
      });
      checkout.on('payment.failed', async failure => { const confirmed = await recoverCompletedPayment(); if (!confirmed) { payButton.disabled = false; showToast(failure?.error?.description || 'Payment was not completed. You can safely retry payment.'); } });
      checkout.open();
      // Poll briefly as a recovery path only. The normal handler above remains
      // the primary fast path, while this catches a lost redirect/callback.
      reconciliationTimer = window.setInterval(recoverCompletedPayment, 5000);
      window.setTimeout(stopReconciliation, 120000);
    } catch (error) { showToast(error.message); payButton.disabled = false; }
  }

  async function submitCheckout(event, modal) {
    event.preventDefault(); const form = event.currentTarget; const message = form.querySelector('#checkout-message'); const button = form.querySelector('button[type="submit"]'); const payload = Object.fromEntries(new FormData(form).entries()); Object.assign(payload, { vehicle_id: state.selectedVehicle.id, pickup_date: state.pickup, return_date: state.returnDate }); message.textContent = 'Validating details and holding the vehicle…'; message.className = 'checkout-message'; button.disabled = true;
    try {
      const data = await request('/api/bookings/checkout/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      sessionStorage.setItem(`ridehub-checkout-aadhaar-${app.email}`, String(payload.aadhaar || '').replace(/\D/g, ''));
      const deadline = new Date(data.payment_expires_at);
      modal.querySelector('.checkout-modal').innerHTML = `<div class="checkout-success"><span>₹</span><p class="user-eyebrow">10-MINUTE PAYMENT HOLD</p><h2>Vehicle locked for you</h2><p id="hold-copy">Complete payment before the timer ends. On expiry, this booking will fail and the vehicle will be released automatically.</p><div class="success-reference"><small>Booking reference</small><strong>RH-${String(data.booking_id).padStart(6, '0')}</strong><small>Estimated total · ₹${escape(Number(data.total_amount).toLocaleString('en-IN'))}</small><strong id="hold-countdown" aria-live="polite">10:00 remaining</strong></div><p class="payment-test-note" id="payment-test-note"></p><button class="user-primary-action" id="pay-reservation">Pay securely <b>→</b></button></div>`;
      const pay = modal.querySelector('#pay-reservation'); const countdown = modal.querySelector('#hold-countdown');
      const updateHold = () => {
        const seconds = Math.max(0, Math.ceil((deadline.getTime() - Date.now()) / 1000));
        if (seconds <= 0) {
          window.clearInterval(timer); pay.disabled = true; countdown.textContent = 'Booking failed — try again';
          modal.querySelector('#hold-copy').textContent = 'Your 10-minute payment window expired. The vehicle is free again; search and try booking again.';
          return;
        }
        countdown.textContent = `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')} remaining`;
      };
      const timer = window.setInterval(updateHold, 250); updateHold();
      pay.addEventListener('click', async () => {
        pay.disabled = true;
        try {
          const checkoutStatus = await request('/api/payments/razorpay/status/');
          const order = await request(`/api/payments/razorpay/order/${data.payment_id}/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
          if (checkoutStatus.test_mode && order.test_mode) modal.querySelector('#payment-test-note').textContent = 'Test mode: use Razorpay test payment details or UPI ID success@razorpay. No real money is charged.';
          await startPayment(data.payment_id, modal, data.booking_id, order);
        } catch (error) { showToast(error.message); if (Date.now() < deadline.getTime()) pay.disabled = false; }
      });
    } catch (error) { message.textContent = error.message; message.className = 'checkout-message error'; button.disabled = false; }
  }

  async function renderBookings() {
    content.innerHTML = '<div class="user-page-heading"><p class="user-eyebrow">RESERVATION HISTORY</p><h1>My bookings</h1><p>Keep every ride, date and shop detail in one clear timeline.</p></div><div class="admin-toolbar"><label><span>Search bookings</span><input id="booking-search" type="search" placeholder="Booking ID, vehicle, shop, date or payment ID"></label></div><div id="booking-list" class="booking-list"><div class="results-loading"><span></span><span></span><span></span>Loading your bookings</div></div>';
    try { const data = await request('/api/bookings/history/'); const list = document.querySelector('#booking-list'); list.innerHTML = data.bookings.length ? data.bookings.map(booking => { const paid = booking.payment?.status === 'PAID'; const ticket = paid && booking.status !== 'CANCELLED'; const searchable = [booking.id, booking.vehicle, booking.vehicle_type, booking.shop, booking.shop_address, booking.pickup_date, booking.return_date, booking.status, booking.total_amount, booking.renter_name, booking.renter_email, booking.renter_phone, booking.payment?.reference, booking.payment?.provider].join(' '); return `<article class="booking-card" data-booking-search data-search="${escape(searchable)}"><div class="booking-card-icon">▣</div><div class="booking-card-main"><div class="booking-card-title"><div><h3>${escape(booking.vehicle)}</h3><p>${escape(booking.shop)} · RH-${String(booking.id).padStart(6, '0')}</p></div><span class="booking-status status-${booking.status.toLowerCase()}">${escape(booking.status)}</span></div><div class="booking-meta"><span>Pickup <strong>${escape(booking.pickup_date)}</strong></span><span>Return <strong>${escape(booking.return_date)}</strong></span><span>Total <strong>₹${escape(Number(booking.total_amount).toLocaleString('en-IN'))}</strong></span></div><div class="result-actions"><button class="user-secondary-action" data-view-booking="${booking.id}">View details</button>${paid ? `<a class="user-secondary-action" href="/api/bookings/${booking.id}/documents/receipt/">Payment receipt</a>` : ''}${ticket ? `<a class="user-secondary-action" href="/api/bookings/${booking.id}/documents/confirmation/">Ride ticket</a>` : ''}<small class="verified-note">${booking.payment?.status === 'PAID' ? '✓ Paid online — documents ready' : `Payment: ${escape(booking.payment?.status || 'Cancelled')}`}</small></div></div></article>`; }).join('') : '<div class="results-empty"><span>▣</span><strong>No bookings yet</strong><p>Your paid reservations will appear here after online checkout.</p><button class="user-secondary-action" data-user-page="rides">Find a ride</button></div>'; document.querySelector('#booking-search')?.addEventListener('input', event => { const term = event.currentTarget.value.trim().toLowerCase(); document.querySelectorAll('[data-booking-search]').forEach(card => { card.hidden = !!term && !card.dataset.search.toLowerCase().includes(term); }); }); window.__ridehubBookings = data.bookings; const successId = new URLSearchParams(window.location.search).get('success') || sessionStorage.getItem('ridehub-payment-success-booking'); const successBooking = data.bookings.find(item => String(item.id) === String(successId)); if (successBooking) { sessionStorage.removeItem('ridehub-payment-success-booking'); window.history.replaceState({}, '', '/user-portal/bookings/'); openBookingSummary(successBooking, true); } } catch (error) { document.querySelector('#booking-list').innerHTML = `<div class="results-empty"><strong>Could not load bookings</strong><p>${escape(error.message)}</p></div>`; }
  }

  function openBookingSummary(booking, paymentSuccess = false) {
    const payment = booking.payment || {};
    const modal = document.createElement('div'); modal.className = 'checkout-overlay booking-summary-overlay';
    const gender = String(booking.renter_gender || '').replaceAll('_', ' ');
    const documents = payment.status === 'PAID' ? `<div class="result-actions"><a class="user-secondary-action" href="/api/bookings/${booking.id}/documents/receipt/">Download payment receipt</a>${booking.status !== 'CANCELLED' ? `<a class="user-secondary-action" href="/api/bookings/${booking.id}/documents/confirmation/">Download ride ticket</a>` : ''}</div>` : '';
    const handoverStage = payment.status === 'PAID' && booking.status === 'CONFIRMED' ? 'PICKUP' : payment.status === 'PAID' && booking.status === 'HANDED_OVER' ? 'RETURN' : '';
    const handoverAction = handoverStage ? `<section class="handover-code-panel"><h3>${handoverStage === 'PICKUP' ? 'Pickup handover' : 'Return handover'}</h3><p>Generate a short-lived verification code when you are with the shopkeeper. Share it in person to confirm the vehicle condition.</p><button class="user-secondary-action" data-handover-code="${handoverStage}" data-booking-id="${booking.id}">Generate ${handoverStage === 'PICKUP' ? 'pickup' : 'return'} code</button><p class="handover-code-result" aria-live="polite"></p></section>` : '';
    modal.innerHTML = `<section class="checkout-modal booking-summary-modal" role="dialog" aria-modal="true" aria-labelledby="booking-summary-title"><button class="modal-close" aria-label="Close booking details">×</button><div class="booking-summary-hero"><span>${paymentSuccess ? '✓' : '▣'}</span><p class="user-eyebrow">${paymentSuccess ? 'PAYMENT SUCCESSFUL' : 'BOOKING DETAILS'}</p><h2 id="booking-summary-title">${paymentSuccess ? 'Your ride is booked.' : escape(booking.vehicle)}</h2><p>${paymentSuccess ? 'Payment is confirmed and your reservation is now visible in My bookings.' : 'Complete reservation and payment information.'}</p></div><div class="success-reference"><small>Booking reference</small><strong>RH-${String(booking.id).padStart(6, '0')}</strong><small>${escape(booking.status)} · ${payment.status === 'PAID' ? 'Paid online' : escape(payment.status || 'Payment pending')}</small></div><div class="booking-summary-grid"><section><h3>Ride</h3><p><b>${escape(booking.vehicle)}</b><br>${escape(booking.vehicle_type || 'Vehicle')} · ${escape(booking.shop)}<br>${escape(booking.shop_address || 'Verified shop location')}</p><p><b>Pickup</b><br>${escape(booking.pickup_date)} → ${escape(booking.return_date)}</p></section><section><h3>Payment</h3><p><b>₹${escape(Number(payment.amount || booking.total_amount).toLocaleString('en-IN'))} ${escape(payment.status || 'PENDING')} · ${escape(payment.provider || 'Online payment')}</p><p><b>Transaction reference</b><br>${escape(payment.reference || 'Pending')}</p></section><section><h3>Renter</h3><p><b>${escape(booking.renter_name || app.name)}</b><br>${escape(booking.renter_phone || app.phone)}<br>${escape(booking.renter_email || app.email)}</p><p><b>Age / gender</b><br>${escape(booking.renter_age || '—')} / ${escape(gender || '—')}</p></section></div>${handoverAction}${documents}<p class="booking-identity-note">${booking.identity_verified ? '✓ Identity format verified for this booking.' : ''}</p><button class="user-primary-action" data-close-booking-summary>Done <b>→</b></button></section>`;
    document.body.appendChild(modal); const close = () => modal.remove(); modal.querySelector('.modal-close').addEventListener('click', close); modal.querySelector('[data-close-booking-summary]').addEventListener('click', close); modal.addEventListener('click', event => { if (event.target === modal) close(); });
    modal.querySelector('[data-handover-code]')?.addEventListener('click', async event => {
      const button = event.currentTarget; button.disabled = true;
      const result = modal.querySelector('.handover-code-result');
      try {
        const response = await request(`/api/bookings/${button.dataset.bookingId}/handover-code/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ stage: button.dataset.handoverCode }) });
        const svg = typeof response.qr_svg === 'string' ? btoa(response.qr_svg) : '';
        result.innerHTML = `<span>Code <strong>${escape(response.code)}</strong> · expires in 10 minutes.</span>${svg ? `<figure class="handover-qr"><img src="data:image/svg+xml;base64,${svg}" alt="QR code for the ${escape(response.stage || button.dataset.handoverCode).toLowerCase()} handover"><figcaption>Shopkeeper can scan this QR, or enter the 6-digit code.</figcaption></figure>` : ''}<small>${escape(response.message)}</small>`;
        result.classList.remove('error');
      } catch (error) { result.textContent = error.message; result.classList.add('error'); }
      finally { button.disabled = false; }
    });
  }

  async function renderProfile() {
    content.innerHTML = `<div class="user-page-heading"><p class="user-eyebrow">ACCOUNT CENTRE</p><h1>Profile & security</h1><p>View and update your own contact details securely.</p></div><div class="profile-grid"><section class="profile-card"><div class="results-loading"><span></span><span></span><span></span>Loading profile</div></section></div>`;
    try { const data = await request('/api/customer/profile/'); const p = data.profile; content.querySelector('.profile-card').innerHTML = `<div class="profile-card-heading"><span class="profile-avatar">${escape((p.full_name || 'R').slice(0, 1).toUpperCase())}</span><div><h2>${escape(p.full_name || 'RideHub user')}</h2><p>Customer account</p></div></div><form id="customer-profile-form" class="checkout-form"><label>Full name<input name="full_name" value="${escape(p.full_name)}" required></label><label>Email address<input value="${escape(p.email)}" readonly><small class="verified-note">${p.email_verified ? '✓ Verified email' : 'Email pending verification'}</small></label><label>Mobile number<input name="phone" inputmode="numeric" maxlength="10" value="${escape(p.phone)}" required></label><p id="profile-message" class="checkout-message"></p><button class="user-primary-action" type="submit">Save changes <b>→</b></button></form>`; content.querySelector('#customer-profile-form').addEventListener('submit', async event => { event.preventDefault(); const form = event.currentTarget; const msg = form.querySelector('#profile-message'); try { const result = await request('/api/customer/profile/update/', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(Object.fromEntries(new FormData(form).entries())) }); app.name = result.profile.full_name; app.phone = result.profile.phone; msg.textContent = result.message; msg.className = 'checkout-message'; } catch (error) { msg.textContent = error.message; msg.className = 'checkout-message error'; } }); } catch (error) { content.innerHTML = `<div class="results-empty"><strong>Could not load your profile</strong><p>${escape(error.message)}</p></div>`; }
  }

  function go(page, navigate = true) { const valid = Object.keys(labels); const target = valid.includes(page) ? page : 'overview'; if (navigate && target !== state.page) { window.location.assign(target === 'overview' ? '/user-portal/' : `/user-portal/${target}/`); return; } state.page = target; crumb.textContent = labels[target] || 'Overview'; renderNav(); document.querySelector('#portal-sidebar').classList.remove('open'); if (target === 'overview') renderOverview(); else if (target === 'rides') renderRides(); else if (target === 'shops') renderShops(); else if (target === 'bookings') renderBookings(); else if (target === 'checkout') content.innerHTML = '<div class="loading-block">Preparing your secure checkout…</div>'; else renderProfile(); window.scrollTo({ top: 0, behavior: 'auto' }); }
  document.addEventListener('click', event => { const page = event.target.closest('[data-user-page]')?.dataset.userPage; if (page) go(page); const shopId = event.target.closest('[data-open-shop]')?.dataset.openShop; if (shopId) { const shop = (window.__ridehubShops || []).find(item => String(item.id) === String(shopId)); if (shop) openShopListings(shop); } const detailId = event.target.closest('[data-vehicle-details]')?.dataset.vehicleDetails; if (detailId) { const vehicle = state.vehicles.find(item => String(item.id) === String(detailId)); if (vehicle) openVehicleDetails(vehicle); } const viewBooking = event.target.closest('[data-view-booking]')?.dataset.viewBooking; if (viewBooking) { const b=(window.__ridehubBookings||[]).find(item=>String(item.id)===String(viewBooking)); if (b) openBookingSummary(b); } });
  document.querySelector('#mobile-menu').addEventListener('click', () => document.querySelector('#portal-sidebar').classList.toggle('open'));
  document.querySelector('#profile-shortcut').addEventListener('click', () => go('profile'));
  document.querySelector('#logout-button').addEventListener('click', async () => { try { await request('/api/auth/logout/', { method: 'POST' }); } finally { window.location.assign('/auth/'); } });
  go(state.page, false);
  resumeBookingFromAuth();
})();
