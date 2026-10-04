/* Optional Google Maps + Places integration with a no-key browser fallback. */
(() => {
    const apiKey = (document.body.dataset.googleMapsKey || '').trim();
    const geocoder = { current: null };

    function notify(message) {
        if (typeof window.showToast === 'function') window.showToast(message);
        else console.info(`[RideHub] ${message}`);
    }

    function coordinateFields(input) {
        const prefix = input.id === 'shop-address' ? 'shop' : 'location';
        return {
            latitude: document.querySelector(`#${prefix}-latitude`),
            longitude: document.querySelector(`#${prefix}-longitude`),
            placeId: document.querySelector(`#${prefix}-place-id`),
        };
    }

    function setCoordinates(input, latitude, longitude, placeId = '') {
        const fields = coordinateFields(input);
        if (fields.latitude) fields.latitude.value = Number(latitude).toFixed(6);
        if (fields.longitude) fields.longitude.value = Number(longitude).toFixed(6);
        if (fields.placeId) fields.placeId.value = placeId || '';
        input.dataset.locationSelected = 'true';
    }

    function clearCoordinates(input) {
        const fields = coordinateFields(input);
        if (fields.latitude) fields.latitude.value = '';
        if (fields.longitude) fields.longitude.value = '';
        if (fields.placeId) fields.placeId.value = '';
        input.dataset.locationSelected = 'false';
    }

    function applyPlace(input, address, latitude, longitude, placeId = '') {
        input.value = address;
        setCoordinates(input, latitude, longitude, placeId);
    }

    function reverseGeocode(input, latitude, longitude) {
        if (!window.google?.maps?.Geocoder) {
            applyPlace(input, `Current location: ${latitude.toFixed(6)}, ${longitude.toFixed(6)}`, latitude, longitude);
            return;
        }
        geocoder.current ||= new google.maps.Geocoder();
        geocoder.current.geocode({ location: { lat: latitude, lng: longitude } }, (results, status) => {
            if (status === 'OK' && results?.[0]) {
                applyPlace(input, results[0].formatted_address, latitude, longitude, results[0].place_id);
                notify('Current location found.');
            } else {
                applyPlace(input, `Current location: ${latitude.toFixed(6)}, ${longitude.toFixed(6)}`, latitude, longitude);
                notify('Coordinates added. You can refine the address.');
            }
        });
    }

    function useCurrentLocation(button) {
        const targetId = button.dataset.locationTarget;
        const input = document.querySelector(`#${targetId}`);
        if (!input) return;
        if (!navigator.geolocation) {
            notify('Location is not available in this browser.');
            return;
        }
        button.disabled = true;
        navigator.geolocation.getCurrentPosition(
            ({ coords }) => {
                reverseGeocode(input, coords.latitude, coords.longitude);
                button.disabled = false;
            },
            () => {
                button.disabled = false;
                notify('Location permission was not granted. Enter the address manually.');
            },
            { enableHighAccuracy: true, timeout: 10000, maximumAge: 300000 },
        );
    }

    function attachAutocomplete(input) {
        if (!window.google?.maps?.places?.Autocomplete || input.dataset.autocompleteAttached === 'true') return;
        const autocomplete = new google.maps.places.Autocomplete(input, {
            fields: ['formatted_address', 'geometry', 'name', 'place_id'],
        });
        autocomplete.addListener('place_changed', () => {
            const place = autocomplete.getPlace();
            if (!place.geometry?.location) {
                notify('Choose a location from the Google suggestions.');
                return;
            }
            const latitude = place.geometry.location.lat();
            const longitude = place.geometry.location.lng();
            applyPlace(input, place.formatted_address || place.name, latitude, longitude, place.place_id);
        });
        input.addEventListener('input', () => clearCoordinates(input));
        input.dataset.autocompleteAttached = 'true';
    }

    function initializeGoogleMaps() {
        document.querySelectorAll('[data-place-autocomplete="true"]').forEach(attachAutocomplete);
    }

    function loadGoogleMaps() {
        if (!apiKey || window.google?.maps?.places) return initializeGoogleMaps();
        const script = document.createElement('script');
        script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&libraries=places&v=weekly&loading=async`;
        script.async = true;
        script.defer = true;
        script.dataset.ridehubMaps = 'true';
        script.onload = initializeGoogleMaps;
        script.onerror = () => notify('Google Maps could not load. You can still enter a location manually.');
        document.head.appendChild(script);
    }

    document.querySelectorAll('[data-use-current-location]').forEach((button) => {
        button.addEventListener('click', () => useCurrentLocation(button));
    });

    document.querySelectorAll('[data-place-autocomplete="true"]').forEach((input) => {
        input.addEventListener('input', () => clearCoordinates(input));
    });

    loadGoogleMaps();
})();
