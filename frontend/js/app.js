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

function validateDates(trip) {
    if (!pickupDate.value) return 'Please select a pickup date.';
    if (pickupDate.value < today) return 'Pickup date cannot be in the past.';
    if (trip === 'one-way') return '';
    if (!returnDate.value) return 'Please select a return date.';
    if (returnDate.value < today) return 'Return date cannot be in the past.';
    if (returnDate.value < pickupDate.value) return 'Return date must be on or after the pickup date.';
    if (returnDate.value > dateAfter(pickupDate.value, 7)) return 'Return date cannot be more than 7 days after pickup.';
    return '';
}

document.querySelectorAll('.trip-option').forEach((button) => {
    button.addEventListener('click', () => {
        document.querySelectorAll('.trip-option').forEach((option) => option.classList.remove('active'));
        button.classList.add('active');
        const oneWay = button.dataset.trip === 'one-way';
        document.querySelector('.return-field').style.opacity = oneWay ? '.45' : '1';
        returnDate.required = !oneWay;
        returnDate.disabled = oneWay;
        if (oneWay) returnDate.value = '';
        syncDateConstraints();
        setDateMessage();
    });
});

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
        resultsGrid.innerHTML = `<div class="live-empty">No verified sellers available near this location right now.</div>`;
        return;
    }
    resultsGrid.innerHTML = items.map((item) => {
        const title = kind === 'shops' ? item.name : item.name;
        const subtitle = kind === 'shops' ? `${item.vehicle_count} approved vehicle(s)` : `₹${item.daily_rate}/day · ${item.shop}`;
        const image = kind === 'vehicles' && item.image_url ? `<img class="live-result-thumb" src="${escapeHtml(item.image_url)}" alt="${escapeHtml(title)}">` : '';
        return `<article class="live-result-card">${image}<div><strong>${escapeHtml(title)}</strong><small>${escapeHtml(subtitle)}</small><p>${escapeHtml(item.address || '')}${item.distance_km !== undefined ? ` · ${item.distance_km} km away` : ''}</p></div>${item.directions_url ? `<a class="result-direction" href="${escapeHtml(item.directions_url)}" target="_blank" rel="noopener">Directions ↗</a>` : ''}</article>`;
    }).join('');
}

async function loadLiveResults(type, location) {
    const latitude = document.querySelector('#location-latitude').value;
    const longitude = document.querySelector('#location-longitude').value;
    const params = new URLSearchParams({ vehicle_type: type, q: location, pickup_date: pickupDate.value, return_date: returnDate.value });
    if (latitude && longitude) { params.set('latitude', latitude); params.set('longitude', longitude); }
    const endpoint = searchMode === 'shop' ? `/api/shops/search/?q=${encodeURIComponent(location)}&latitude=${encodeURIComponent(latitude)}&longitude=${encodeURIComponent(longitude)}` : `/api/vehicles/search/?${params}`;
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
    const trip = document.querySelector('.trip-option.active').dataset.trip;
    const dateError = validateDates(trip);
    if (dateError) {
        setDateMessage(dateError);
        return;
    }
    const type = document.querySelector('#vehicle-type').value;
    const location = document.querySelector('#location').value.split(',')[0];
    message.style.color = '#71c5ff';
    message.textContent = `Searching verified ${searchMode === 'shop' ? 'shops' : type === 'all' ? 'vehicles' : `${type}s`} near ${location}.`;
    await loadLiveResults(type, location);
    filterVehicles(type);
    document.querySelector('#trending').scrollIntoView({ behavior: 'smooth', block: 'start' });
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
