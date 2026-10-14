function csrfToken() {
    return document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))?.split('=')[1] || '';
}

document.querySelector('[data-sidebar-toggle]')?.addEventListener('click', () => {
    document.querySelector('#workspace-sidebar')?.classList.toggle('open');
});
document.querySelectorAll('.sidebar-nav .nav-item[href^="#"]').forEach((link) => {
    link.addEventListener('click', () => document.querySelector('#workspace-sidebar')?.classList.remove('open'));
});

function dashboardMessage(message, type = '') {
    const box = document.querySelector('#dashboard-message');
    if (!box) return;
    box.textContent = message;
    box.className = `dashboard-message show ${type}`;
}

async function postForm(url, body, isFormData = false) {
    const options = {
        method: 'POST',
        headers: { 'X-CSRFToken': csrfToken() },
        body,
    };
    if (!isFormData) options.headers['Content-Type'] = 'application/json';
    const response = await fetch(url, options);
    const raw = await response.text();
    let data = {};
    try { data = raw ? JSON.parse(raw) : {}; }
    catch { data = { message: `The server returned an unreadable response (HTTP ${response.status}). Check the Django server log for the underlying error.` }; }
    if (!response.ok || data.ok === false) {
        const message = data.message || `Request failed with HTTP ${response.status}. Check the Django server log for the underlying error.`;
        throw new Error(message);
    }
    return data;
}

async function handleActionButton(button) {
    const action = button.dataset.action || (button.dataset.actionKind === 'availability' ? 'availability' : 'update');
    const isDelete = button.dataset.actionKind === 'delete';
    const confirmation = button.dataset.actionKind === 'availability'
        ? `${button.dataset.available === 'true' ? 'Publish' : 'Pause'} this vehicle for new searches?`
        : isDelete ? 'Remove this vehicle from your active fleet? Existing booking history will be preserved.'
        : `${action.toLowerCase() === 'revoke' ? 'Revoke this account/listing?' : `${action[0].toUpperCase()}${action.slice(1).toLowerCase()} this request?`}`;
    if (!window.confirm(confirmation)) return;
    button.disabled = true;
    try {
        const body = button.dataset.actionKind === 'availability'
            ? JSON.stringify({ is_available: button.dataset.available === 'true' })
            : isDelete ? '{}'
            : JSON.stringify({ action });
        const data = await postForm(button.dataset.adminAction || button.dataset.actionUrl, body);
        dashboardMessage(data.message, 'success');
        window.setTimeout(() => window.location.reload(), 500);
    } catch (error) {
        dashboardMessage(error.message, 'error');
        button.disabled = false;
    }
}

document.querySelectorAll('[data-admin-action], [data-action-url]').forEach((button) => {
    button.addEventListener('click', async () => {
        await handleActionButton(button);
    });
});

const profileForm = document.querySelector('#shop-profile-form');
if (profileForm) {
    profileForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        try {
            const data = await postForm('/api/shopkeeper/profile/', new FormData(profileForm), true);
            dashboardMessage(data.message, 'success');
        } catch (error) {
            dashboardMessage(error.message, 'error');
        }
    });
}

const vehicleForm = document.querySelector('#vehicle-form');
if (vehicleForm) {
    vehicleForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        try {
            const data = await postForm('/api/shopkeeper/vehicles/create/', new FormData(vehicleForm), true);
            dashboardMessage(data.message, 'success');
            vehicleForm.reset();
            window.setTimeout(() => window.location.reload(), 600);
        } catch (error) {
            dashboardMessage(error.message, 'error');
        }
    });
}

document.querySelector('[data-logout]')?.addEventListener('click', async () => {
    try {
        await postForm('/api/auth/logout/', '{}');
        window.location.href = '/';
    } catch (error) {
        dashboardMessage(error.message, 'error');
    }
});
