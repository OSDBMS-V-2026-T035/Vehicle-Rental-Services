const toast = document.querySelector('#toast');
let toastTimer;

function showToast(message) {
    toast.textContent = message;
    toast.classList.add('show');
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.remove('show'), 3200);
}

document.querySelectorAll('[data-toast]').forEach((button) => {
    button.addEventListener('click', () => showToast(button.dataset.toast));
});

const menuToggle = document.querySelector('.menu-toggle');
const mainNav = document.querySelector('.main-nav');
menuToggle.addEventListener('click', () => {
    const open = mainNav.classList.toggle('open');
    menuToggle.setAttribute('aria-expanded', String(open));
});
document.querySelectorAll('.main-nav a').forEach((link) => {
    link.addEventListener('click', () => {
        mainNav.classList.remove('open');
        menuToggle.setAttribute('aria-expanded', 'false');
    });
});

const heroModeButtons = document.querySelectorAll('[data-hero-mode]');
const heroImages = document.querySelectorAll('.hero-visual img[data-car-src][data-bike-src]');
const heroModeContent = {
    car: {
        title: 'Find your fit.',
        copy: 'Cars for city drives and weekend escapes',
        label: 'FEATURED CAR',
        previews: ['Weekend drives', 'City-ready cars'],
        alts: ['Car available for local rental', 'Car on a scenic road', 'Car available to rent'],
    },
    bike: {
        title: 'Take the long way.',
        copy: 'Two-wheelers made for open roads and quick city rides',
        label: 'FEATURED BIKE',
        previews: ['Cruise beyond town', 'Easy city rides'],
        alts: ['Motorcycle available for local rental', 'Motorcycle ready for a weekend ride', 'Scooter available to rent'],
    },
};

heroModeButtons.forEach((button) => {
    button.addEventListener('click', () => {
        const mode = button.dataset.heroMode;
        const content = heroModeContent[mode];
        if (!content) return;
        heroModeButtons.forEach((option) => {
            const selected = option === button;
            option.classList.toggle('is-active', selected);
            option.setAttribute('aria-pressed', String(selected));
        });
        document.querySelector('.hero-visual').dataset.vehicleMode = mode;
        heroImages.forEach((image, index) => {
            image.classList.add('is-transitioning');
            window.setTimeout(() => {
                if (document.querySelector('.hero-visual').dataset.vehicleMode !== mode) return;
                image.src = image.dataset[`${mode}Src`];
                image.alt = content.alts[index];
                image.classList.remove('is-transitioning');
            }, 180);
        });
        document.querySelector('#hero-caption-title').textContent = content.title;
        document.querySelector('#hero-caption-copy').textContent = content.copy;
        document.querySelector('#hero-image-label').textContent = content.label;
        document.querySelector('#hero-image-number').textContent = mode === 'car' ? '01' : '02';
        document.querySelector('#hero-preview-one-label').textContent = content.previews[0];
        document.querySelector('#hero-preview-two-label').textContent = content.previews[1];
    });
});

let searchMode = 'rent';
document.querySelectorAll('.search-tab').forEach((button) => {
    button.addEventListener('click', () => {
        document.querySelectorAll('.search-tab').forEach((tab) => tab.classList.remove('active'));
        button.classList.add('active');
        searchMode = button.dataset.mode;
        document.querySelector('#live-results-title').textContent = searchMode === 'shop' ? 'Nearby verified shops' : 'Nearby approved vehicles';
    });
});

const pickupDate = document.querySelector('#pickup-date');
const returnDate = document.querySelector('#return-date');

function localDateString(date = new Date()) {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}-${month}-${day}`;
}

function dateAfter(dateString, days) {
    const date = new Date(`${dateString}T00:00:00`);
    date.setDate(date.getDate() + days);
    return localDateString(date);
}

const today = localDateString();

function syncDateConstraints() {
    pickupDate.min = today;
    const earliestReturn = pickupDate.value && pickupDate.value >= today ? pickupDate.value : today;
    returnDate.min = earliestReturn;
    returnDate.max = pickupDate.value && pickupDate.value >= today ? dateAfter(pickupDate.value, 7) : dateAfter(today, 7);
    if (returnDate.value && returnDate.value < earliestReturn) returnDate.value = '';
    if (returnDate.value && returnDate.value > returnDate.max) returnDate.value = '';
}

function setDateMessage(text = '') {
    message.textContent = text;
    message.style.color = text ? '#ff9d9d' : '#71c5ff';
}

function validateDates() {
    if (!pickupDate.value) return 'Please select a pickup date.';
    if (pickupDate.value < today) return 'Pickup date cannot be in the past.';
    if (!returnDate.value) return 'Please select a return date.';
    if (returnDate.value < today) return 'Return date cannot be in the past.';
    if (returnDate.value < pickupDate.value) return 'Return date must be on or after the pickup date.';
    if (returnDate.value > dateAfter(pickupDate.value, 7)) return 'Return date cannot be more than 7 days after pickup.';
    return '';
}

syncDateConstraints();
pickupDate.addEventListener('change', () => {
    syncDateConstraints();
    setDateMessage();
});
returnDate.addEventListener('change', () => setDateMessage());

const form = document.querySelector('#search-form');
const message = document.querySelector('#form-message');
const resultsPanel = document.querySelector('#live-results');
const resultsGrid = document.querySelector('#live-results-grid');

function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>'"]/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[character]));
}

function renderLiveResults(items, kind) {
    resultsPanel.hidden = false;
    document.querySelector('#live-results-count').textContent = `${items.length} found`;
    if (!items.length) {
        resultsGrid.innerHTML = `<div class="live-empty">No verified, available listings were found within 15 km of this location.</div>`;
        return;
    }
    const rows = items.map((item) => {
        const title = item.name;
        const image = kind === 'vehicles' && item.image_url ? `<img class="live-result-thumb" src="${escapeHtml(item.image_url)}" alt="${escapeHtml(title)}">` : '<span class="live-result-placeholder">⌁</span>';
        const unavailable = kind === 'vehicles' && item.availability_status === 'UNAVAILABLE';
        const bookingParams = new URLSearchParams({ vehicle_id: item.id, pickup_date: pickupDate.value, return_date: returnDate.value, checkout: '1' });
        const authUrl = `/auth/?role=USER&mode=login&next=${encodeURIComponent(`/user-portal/?${bookingParams.toString()}`)}`;
        const book = kind === 'vehicles' ? `<a class="result-direction${unavailable ? ' is-disabled' : ''}" ${unavailable ? 'aria-disabled="true"' : `href="${authUrl}"`}>${unavailable ? 'Unavailable' : 'Book now'}</a>` : '';
        const distance = item.distance_km !== undefined ? `${item.distance_km} km` : '—';
        if (kind === 'shops') return `<tr><td><div class="live-vehicle-cell">${image}<span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(item.address || 'Verified shop location')}</small></span></div></td><td>${escapeHtml(String(item.vehicle_count || 0))} vehicle(s)</td><td>${escapeHtml(distance)}</td><td>${item.directions_url ? `<a class="result-direction" href="${escapeHtml(item.directions_url)}" target="_blank" rel="noopener">Directions</a>` : '—'}</td></tr>`;
        return `<tr><td><div class="live-vehicle-cell">${image}<span><strong>${escapeHtml(title)}</strong><small>${escapeHtml(item.brand || '')} · ${escapeHtml(item.model || '')}</small></span></div></td><td><strong>₹${escapeHtml(item.daily_rate)}</strong><small>per day</small></td><td><strong>${escapeHtml(item.shop)}</strong><small>${escapeHtml(item.address || 'Verified location')}</small></td><td>${escapeHtml(distance)}</td><td><span class="live-availability ${unavailable ? 'unavailable' : ''}">${escapeHtml(item.availability_message || 'Available')}</span></td><td><div class="live-actions">${book}${item.directions_url ? `<a class="result-direction result-direction-secondary" href="${escapeHtml(item.directions_url)}" target="_blank" rel="noopener">Directions</a>` : ''}</div></td></tr>`;
    }).join('');
    const headings = kind === 'shops' ? '<tr><th>Shop</th><th>Fleet</th><th>Distance</th><th>Action</th></tr>' : '<tr><th>Vehicle</th><th>Rate</th><th>Shop</th><th>Distance</th><th>Availability</th><th>Action</th></tr>';
    resultsGrid.innerHTML = `<div class="live-table-wrap"><table class="live-results-table"><thead>${headings}</thead><tbody>${rows}</tbody></table></div>`;
}

async function loadLiveResults(type, location) {
    const latitude = document.querySelector('#location-latitude').value;
    const longitude = document.querySelector('#location-longitude').value;
    // Browser geolocation stores a human-readable label such as
    // "Current location: 30.272890, 77.900000" in the text box.  That label
    // is not a shop/address keyword, so never apply it as a text filter when
    // real coordinates are available; use only the 15 km geo-radius.
    const hasCoordinates = Boolean(latitude && longitude);
    const params = new URLSearchParams({ vehicle_type: type, q: hasCoordinates ? '' : location, pickup_date: pickupDate.value, return_date: returnDate.value, radius: '15' });
    if (latitude && longitude) { params.set('latitude', latitude); params.set('longitude', longitude); }
    const endpoint = searchMode === 'shop' ? `/api/shops/search/?q=${encodeURIComponent(hasCoordinates ? '' : location)}&latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}&radius=15` : `/api/vehicles/search/?${params}`;
    try {
        const response = await fetch(endpoint);
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || 'Live search could not be completed.');
        renderLiveResults(searchMode === 'shop' ? data.shops : data.vehicles, searchMode === 'shop' ? 'shops' : 'vehicles');
    } catch (error) {
        resultsPanel.hidden = false;
        resultsGrid.innerHTML = `<div class="live-empty">${escapeHtml(error.message)}</div>`;
    }
}

form.addEventListener('submit', async (event) => {
    event.preventDefault();
    const dateError = validateDates();
    if (dateError) {
        setDateMessage(dateError);
        return;
    }
    const type = document.querySelector('#vehicle-type').value;
    const location = document.querySelector('#location').value.split(',')[0];
    message.style.color = '#71c5ff';
    message.textContent = `Searching verified ${searchMode === 'shop' ? 'shops' : type === 'all' ? 'vehicles' : `${type}s`} within 15 km of ${location}.`;
    await loadLiveResults(type, location);
    filterVehicles(type);
    resultsPanel.scrollIntoView({ behavior: 'smooth', block: 'start' });
});

const emptyState = document.querySelector('#empty-state');
function filterVehicles(category) {
    let visible = 0;
    document.querySelectorAll('.vehicle-card:not(.explore-card)').forEach((card) => {
        const show = category === 'all' || card.dataset.type === category;
        card.style.display = show ? '' : 'none';
        if (show) visible += 1;
    });
    emptyState.classList.toggle('visible', visible === 0);
}

document.querySelectorAll('.category-card').forEach((card) => {
    card.addEventListener('click', () => {
        const category = card.dataset.category;
        document.querySelector('#vehicle-type').value = category;
        filterVehicles(category);
        document.querySelector('#trending').scrollIntoView({ behavior: 'smooth', block: 'start' });
        showToast(`${card.querySelector('strong').textContent} selected. Compare available rides below.`);
    });
});

document.querySelectorAll('.favorite').forEach((button) => {
    button.addEventListener('click', () => {
        button.classList.toggle('saved');
        button.textContent = button.classList.contains('saved') ? '♥' : '♡';
        showToast(button.classList.contains('saved') ? 'Vehicle saved to your favourites.' : 'Vehicle removed from your favourites.');
    });
});
