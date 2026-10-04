# Authentication and location integrations

The authentication flow is intentionally provider-optional. It works locally with
Django's console OTP delivery, and switches to a real provider only when its
environment variables are configured.

| Capability | Current implementation | Cost status |
| --- | --- | --- |
| Email OTP | Brevo API adapter, then Django SMTP fallback, then console OTP | Brevo currently has a free plan with a daily email limit; SMTP cost depends on the mailbox provider |
| Phone number | Format and uniqueness validation only; no SMS provider is connected | No SMS cost because mobile OTP is intentionally disabled |
| Current location | Browser `navigator.geolocation` | Free browser capability; it needs the user's permission |
| Google Maps | Optional Places autocomplete, reverse geocoding, and coordinate capture; browser geolocation remains the fallback | Google Maps Platform requires an API key; standard production projects also require billing, while a no-cost demo key is available for prototyping |

## Environment setup

Use `.env.example` as the starting point. For a local demo, leave provider keys
empty and run Django in `DEBUG=True`; OTPs are printed by the console backend and
the development UI shows the returned code. Never expose development OTPs when
`DEBUG=False`.

For real email delivery, configure either the Django SMTP variables or
`BREVO_API_KEY` plus `DEFAULT_FROM_EMAIL`. Mobile OTP is intentionally not part
of the current signup flow. No third-party Python package is required for the
email adapter; it uses Django and Python's standard library.

Google Maps integration is enabled when `GOOGLE_MAPS_API_KEY` is set. The home
search field and shopkeeper address field then use Google Places autocomplete,
and the current-location buttons reverse-geocode browser coordinates when
possible. Without a key, users can still enter an address manually and the
browser geolocation fallback stores coordinates when permission is granted.
Shopkeeper coordinates and the Google place ID are persisted in
`ShopkeeperProfile`.

## Official references checked

- [Brevo pricing and free-plan limits](https://help.brevo.com/hc/en-us/articles/208589409-About-Brevo-s-pricing-plans)
- [Google Maps Platform setup and billing requirements](https://developers.google.com/maps/get-started)
- [Google Maps JavaScript API key setup](https://developers.google.com/maps/documentation/javascript/get-api-key)
