function csrfToken() {
    return document.cookie.split('; ').find((row) => row.startsWith('csrftoken='))?.split('=')[1] || '';
}

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
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || 'Request could not be completed.');
    return data;
}

document.querySelectorAll('[data-admin-action]').forEach((button) => {
    button.addEventListener('click', async () => {
        const action = button.dataset.action;
        const confirmation = action === 'revoke' ? 'Revoke this account/listing?' : `${action[0].toUpperCase()}${action.slice(1)} this request?`;
        if (!window.confirm(confirmation)) return;
        button.disabled = true;
        try {
            const data = await postForm(button.dataset.adminAction, JSON.stringify({ action }));
            dashboardMessage(data.message, 'success');
            window.setTimeout(() => window.location.reload(), 500);
        } catch (error) {
            dashboardMessage(error.message, 'error');
            button.disabled = false;
        }
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
