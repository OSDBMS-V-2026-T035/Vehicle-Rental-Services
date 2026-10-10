const page = document.querySelector('.auth-page');
const toast = document.querySelector('#toast');
const messageBox = document.querySelector('#server-message');
let toastTimer;

function showToast(message) {
    toast.textContent = message;
    toast.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => toast.classList.remove('show'), 3500);
}

function showMessage(message, type = '') {
    messageBox.textContent = message;
    messageBox.className = `notice show ${type}`;
}

function clearErrors() {
    document.querySelectorAll('.field-error').forEach((item) => { item.textContent = ''; });
    document.querySelectorAll('.input-control').forEach((item) => { item.style.borderColor = ''; });
}

function setError(field, error) {
    const errorElement = document.querySelector(`[data-error-for="${field}"]`);
    const input = document.querySelector(`#${field}`);
    if (errorElement) errorElement.textContent = error;
    if (input) input.closest('.input-control')?.style.setProperty('border-color', '#e86d83');
}

function csrfToken() {
    return document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))?.split('=')[1] || '';
}

function setRole(role) {
    page.dataset.role = role;
    document.querySelectorAll('[data-role-button]').forEach((button) => button.classList.toggle('active', button.dataset.roleButton === role));
    const label = role === 'SHOPKEEPER' ? 'SHOPKEEPER ACCESS' : role === 'ADMIN' ? 'ADMIN ACCESS' : 'USER ACCESS';
    const title = role === 'SHOPKEEPER' ? 'Shopkeeper Login' : role === 'ADMIN' ? 'Admin Login' : 'User Login';
    const subtitle = role === 'SHOPKEEPER' ? 'Manage your shop, vehicles and bookings with ease.' : role === 'ADMIN' ? 'Access platform operations and trusted controls.' : 'Welcome back! Continue your journey with RideHub.';
    const icon = role === 'SHOPKEEPER' ? '▤' : role === 'ADMIN' ? '◆' : '♟';
    document.querySelector('.role-badge').textContent = label;
    document.querySelector('#panel-title').textContent = title;
    document.querySelector('#panel-subtitle').textContent = subtitle;
    document.querySelector('.panel-icon').textContent = icon;
    const signupTab = document.querySelector('[data-mode-button="signup"].auth-tab');
    const signupLinks = document.querySelectorAll('[data-mode-button="signup"]:not(.auth-tab)');
    const admin = role === 'ADMIN';
    signupTab.disabled = admin;
    signupTab.style.opacity = admin ? '.45' : '1';
    signupLinks.forEach((link) => { link.style.display = admin ? 'none' : ''; });
    if (admin && page.dataset.mode === 'signup') setMode('login');
    document.querySelector('.shopkeeper-fields').classList.toggle('hidden', role !== 'SHOPKEEPER');
}

function setMode(mode) {
    if (page.dataset.role === 'ADMIN' && mode === 'signup') return;
    page.dataset.mode = mode;
    document.querySelectorAll('.auth-tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.modeButton === mode));
    document.querySelector('#login-form').classList.toggle('hidden', mode !== 'login');
    document.querySelector('#signup-form').classList.toggle('hidden', mode !== 'signup');
    document.querySelector('#reset-form').classList.add('hidden');
    if (mode === 'signup') document.querySelector('#panel-title').textContent = page.dataset.role === 'SHOPKEEPER' ? 'Create Shopkeeper Account' : 'Create User Account';
    else document.querySelector('#panel-title').textContent = page.dataset.role === 'SHOPKEEPER' ? 'Shopkeeper Login' : page.dataset.role === 'ADMIN' ? 'Admin Login' : 'User Login';
    clearErrors();
    messageBox.className = 'notice';
    messageBox.textContent = '';
    placeCaptcha();
}

document.querySelectorAll('[data-role-button]').forEach((button) => button.addEventListener('click', () => setRole(button.dataset.roleButton)));
document.querySelectorAll('[data-mode-button]').forEach((button) => button.addEventListener('click', () => setMode(button.dataset.modeButton)));
document.querySelectorAll('[data-toast]').forEach((button) => button.addEventListener('click', (event) => { event.preventDefault(); showToast(button.dataset.toast); }));
document.querySelectorAll('[data-toggle-password]').forEach((button) => button.addEventListener('click', () => {
    const input = document.querySelector(`#${button.dataset.togglePassword}`);
    input.type = input.type === 'password' ? 'text' : 'password';
    button.textContent = input.type === 'password' ? '◉' : '◌';
}));

function passwordRules(value) {
    return { length: value.length >= 10, upper: /[A-Z]/.test(value), lower: /[a-z]/.test(value), number: /\d/.test(value), special: /[^A-Za-z0-9\s]/.test(value), space: !/\s/.test(value) };
}
document.querySelector('#signup-password').addEventListener('input', (event) => {
    const rules = passwordRules(event.target.value);
    Object.entries(rules).forEach(([key, valid]) => document.querySelector(`[data-rule="${key}"]`).classList.toggle('ok', valid));
    const score = Object.values(rules).filter(Boolean).length;
    document.querySelectorAll('.password-meter span').forEach((bar, index) => bar.className = index < Math.ceil(score / 1.5) ? score >= 6 ? 'great' : score >= 4 ? 'strong' : 'good' : '');
});

function validEmail(value) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value); }
function validPhone(value) { return /^[6-9]\d{9}$/.test(value); }
function validPassword(value) { return Object.values(passwordRules(value)).every(Boolean); }

async function sendOtp(button) {
    const channel = button.dataset.otpChannel;
    const contact = document.querySelector('#signup-email').value.trim();
    clearErrors();
    if (!validEmail(contact)) return setError('signup-email', 'Enter a valid email before requesting the OTP.');
    button.disabled = true;
    try {
        const response = await fetch('/api/auth/send-otp/', { method: 'POST', headers: {'Content-Type':'application/json', 'X-CSRFToken': csrfToken()}, body: JSON.stringify({ channel, contact, ...captchaPayload() }) });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || 'OTP could not be sent.');
        showMessage(data.message, 'success');
        placeCaptcha();
        refreshCaptcha();
        let seconds = 60;
        const original = button.textContent;
        const timer = setInterval(() => { seconds -= 1; button.textContent = `${seconds}s`; if (seconds <= 0) { clearInterval(timer); button.disabled = false; button.textContent = original; } }, 1000);
    } catch (error) { showMessage(error.message, 'error'); button.disabled = false; }
}
document.querySelectorAll('[data-otp-channel]').forEach((button) => button.addEventListener('click', () => sendOtp(button)));

document.querySelector('#login-form').addEventListener('submit', async (event) => {
    event.preventDefault(); clearErrors();
    const identifier = document.querySelector('#login-identifier').value.trim();
    const password = document.querySelector('#login-password').value;
    if (!identifier) setError('login-identifier', 'Email or phone is required.');
    if (!password) setError('login-password', 'Password is required.');
    if (!identifier || !password) return;
    await submitAuth('/api/auth/login/', { identifier, password, role: page.dataset.role });
});

document.querySelector('#signup-form').addEventListener('submit', async (event) => {
    event.preventDefault(); clearErrors();
    const fullName = document.querySelector('#full-name').value.trim();
    const email = document.querySelector('#signup-email').value.trim();
    const phone = document.querySelector('#signup-phone').value.trim();
    const password = document.querySelector('#signup-password').value;
    const confirmPassword = document.querySelector('#confirm-password').value;
    let valid = true;
    if (fullName.length < 2) { setError('full-name', 'Enter your full name.'); valid = false; }
    if (!validEmail(email)) { setError('signup-email', 'Enter a valid email address.'); valid = false; }
    if (!validPhone(phone)) { setError('signup-phone', 'Use exactly 10 digits beginning with 6, 7, 8, or 9.'); valid = false; }
    if (!validPassword(password)) { setError('signup-password', 'Meet all password rules shown below.'); valid = false; }
    if (password !== confirmPassword) { setError('confirm-password', 'Passwords do not match.'); valid = false; }
    if (!document.querySelector('#email-otp').value.trim()) { setError('email-otp', 'Verify your email first.'); valid = false; }
    if (page.dataset.role === 'SHOPKEEPER') { if (document.querySelector('#shop-name').value.trim().length < 2) { setError('shop-name', 'Shop name is required.'); valid = false; } if (document.querySelector('#shop-address').value.trim().length < 8) { setError('shop-address', 'Enter a complete shop address.'); valid = false; } }
    if (!document.querySelector('#terms').checked) { setError('terms', 'Accept the terms to continue.'); valid = false; }
    if (!valid) return;
    await submitAuth('/api/auth/signup/', { role: page.dataset.role, full_name: fullName, email, phone, email_otp: document.querySelector('#email-otp').value.trim(), password, confirm_password: confirmPassword, terms: true, shop_name: document.querySelector('#shop-name')?.value.trim(), shop_address: document.querySelector('#shop-address')?.value.trim(), shop_latitude: document.querySelector('#shop-latitude')?.value.trim(), shop_longitude: document.querySelector('#shop-longitude')?.value.trim(), shop_place_id: document.querySelector('#shop-place-id')?.value.trim() });
});

async function submitAuth(url, body) {
    const button = document.querySelector('.auth-form:not(.hidden) .submit-button');
    button.disabled = true;
    try {
        const response = await fetch(url, { method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken()}, body:JSON.stringify(body) });
        const data = await response.json();
        if (!response.ok) throw new Error(data.message || 'Please review the form and try again.');
        showMessage(data.message, 'success');
        showToast(data.message);
        if (data.redirect) setTimeout(() => { window.location.href = data.redirect; }, 900);
    } catch (error) { showMessage(error.message, 'error'); } finally { button.disabled = false; placeCaptcha();
refreshCaptcha(); }
}

const query = new URLSearchParams(window.location.search);
setRole(['USER', 'SHOPKEEPER', 'ADMIN'].includes(query.get('role')) ? query.get('role') : 'USER');
setMode(query.get('mode') === 'signup' ? 'signup' : 'login');

function placeCaptcha() {
    const card = document.querySelector('#captcha-card');
    const target = document.querySelector('#reset-form:not(.hidden), #signup-form:not(.hidden), #login-form:not(.hidden)');
    if (!card || !target) return;
    const submit = target.querySelector('.submit-button');
    if (submit) target.insertBefore(card, submit);
}
function resetMode(active) {
    document.querySelector('#login-form').classList.toggle('hidden', active);
    document.querySelector('#signup-form').classList.toggle('hidden', active);
    document.querySelector('#reset-form').classList.toggle('hidden', !active);
    if (active) { document.querySelector('#panel-title').textContent = 'Reset your password'; document.querySelector('#panel-subtitle').textContent = 'Use the secure code sent to your verified email.'; }
    else setMode('login');
    placeCaptcha();
}

function cooldown(button) {
    let seconds = 60; const original = button.textContent; button.disabled = true;
    const timer = setInterval(() => { seconds -= 1; button.textContent = `${seconds}s`; if (seconds <= 0) { clearInterval(timer); button.disabled = false; button.textContent = original; } }, 1000);
}

document.querySelector('#forgot-password-button').addEventListener('click', () => resetMode(true));
document.querySelector('#back-to-login').addEventListener('click', () => resetMode(false));
document.querySelector('#reset-otp-button').addEventListener('click', async (event) => {
    const email = document.querySelector('#reset-email').value.trim();
    if (!validEmail(email)) return setError('reset-email', 'Enter your account email first.');
    const button = event.currentTarget; clearErrors();
    try {
        const response = await fetch('/api/auth/password-reset/send-otp/', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken()}, body:JSON.stringify({email, ...captchaPayload()})});
        const data = await response.json(); if (!response.ok) throw new Error(data.message);
        showMessage(data.message, 'success'); placeCaptcha(); refreshCaptcha(); cooldown(button);
    } catch (error) { showMessage(error.message, 'error'); }
});
document.querySelector('#reset-form').addEventListener('submit', async (event) => {
    event.preventDefault(); clearErrors();
    const email = document.querySelector('#reset-email').value.trim(); const otp = document.querySelector('#reset-otp').value.trim();
    const password = document.querySelector('#reset-password').value; const confirm_password = document.querySelector('#reset-confirm-password').value;
    if (!validEmail(email) || !otp || !validPassword(password) || password !== confirm_password) { showMessage('Enter a valid email, code, and matching strong password.', 'error'); return; }
    const button = document.querySelector('#reset-form .submit-button'); button.disabled = true;
    try {
        const response = await fetch('/api/auth/password-reset/confirm/', {method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':csrfToken()}, body:JSON.stringify({email, otp, password, confirm_password, ...captchaPayload()})});
        const data = await response.json(); if (!response.ok) throw new Error(data.message);
        showMessage(data.message, 'success'); setTimeout(() => resetMode(false), 1200);
    } catch (error) { showMessage(error.message, 'error'); } finally { button.disabled = false; placeCaptcha();
refreshCaptcha(); }
});

let captchaId = '';
async function refreshCaptcha() {
    const image = document.querySelector('#captcha-image');
    const answer = document.querySelector('#captcha-answer');
    try {
        const response = await fetch('/api/auth/captcha/', {method: 'POST', headers: {'X-CSRFToken': csrfToken()}});
        const data = await response.json();
        if (!response.ok) throw new Error('Security code could not load.');
        captchaId = data.captcha_id; image.src = data.image; answer.value = ''; answer.focus();
    } catch (error) { showMessage(error.message, 'error'); }
}
function captchaPayload() { return {captcha_id: captchaId, captcha_answer: document.querySelector('#captcha-answer').value.trim().toUpperCase()}; }
document.querySelector('#captcha-refresh').addEventListener('click', refreshCaptcha);

const originalSubmitAuth = submitAuth;
submitAuth = async function(url, body) {
    const captcha = captchaPayload();
    if (!captcha.captcha_id || captcha.captcha_answer.length !== 5) { setError('captcha-answer', 'Enter the 5-character security code.'); return; }
    await originalSubmitAuth(url, {...body, ...captcha});
    placeCaptcha();
refreshCaptcha();
};

const originalResetSubmit = document.querySelector('#reset-form').onsubmit;
// Captcha is appended by the reset form listener below using its fetch payload.
const resetForm = document.querySelector('#reset-form');
resetForm.addEventListener('submit', (event) => {}, true);
placeCaptcha();
refreshCaptcha();







