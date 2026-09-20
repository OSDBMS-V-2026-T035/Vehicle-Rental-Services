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

document.querySelectorAll('.search-tab').forEach((button) => {
    button.addEventListener('click', () => {
        document.querySelectorAll('.search-tab').forEach((tab) => tab.classList.remove('active'));
        button.classList.add('active');
        if (button.dataset.mode === 'shop') showToast('Shop discovery is ready for the shops app integration.');
    });
});

document.querySelectorAll('.trip-option').forEach((button) => {
    button.addEventListener('click', () => {
        document.querySelectorAll('.trip-option').forEach((option) => option.classList.remove('active'));
        button.classList.add('active');
        document.querySelector('.return-field').style.opacity = button.dataset.trip === 'one-way' ? '.45' : '1';
        document.querySelector('#return-date').required = button.dataset.trip !== 'one-way';
    });
});

const today = new Date().toISOString().split('T')[0];
const pickupDate = document.querySelector('#pickup-date');
const returnDate = document.querySelector('#return-date');
pickupDate.min = today;
returnDate.min = today;
pickupDate.addEventListener('change', () => { returnDate.min = pickupDate.value || today; });

const form = document.querySelector('#search-form');
const message = document.querySelector('#form-message');
form.addEventListener('submit', (event) => {
    event.preventDefault();
    const trip = document.querySelector('.trip-option.active').dataset.trip;
    if (trip === 'round-trip' && returnDate.value && pickupDate.value && returnDate.value < pickupDate.value) {
        message.textContent = 'Return date must be on or after the pickup date.';
        message.style.color = '#ff9d9d';
        return;
    }
    const type = document.querySelector('#vehicle-type').value;
    const location = document.querySelector('#location').value.split(',')[0];
    message.style.color = '#71c5ff';
    message.textContent = `Showing ${type === 'all' ? 'all vehicles' : `${type}s`} available near ${location}.`;
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
