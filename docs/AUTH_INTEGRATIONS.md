# Authentication and location integrations

The authentication flow is intentionally provider-optional. It works locally with
Django's console OTP delivery, and switches to a real provider only when its
environment variables are configured.

| Capability | Current implementation | Cost status |
| --- | --- | --- |
| Email OTP | Brevo API adapter, then Django SMTP fallback, then console OTP | Brevo currently has a free plan with a daily email limit; SMTP cost depends on the mailbox provider |
| Mobile OTP | Twilio Verify adapter, then console OTP fallback | Twilio has trial units, but production SMS is usage-priced; it is not permanently free |
| Current location | Browser `navigator.geolocation` | Free browser capability; it needs the user's permission |
| Google Maps | Not required for current-location capture | Google Maps Platform requires an API key and billing-enabled project; free usage credits/quotas may apply, but it is not a no-setup free API |

## Environment setup

Use `.env.example` as the starting point. For a local demo, leave provider keys
empty and run Django in `DEBUG=True`; OTPs are printed by the console backend and
the development UI shows the returned code. Never expose development OTPs when
`DEBUG=False`.

For real email delivery, configure either the Django SMTP variables or
`BREVO_API_KEY` plus `DEFAULT_FROM_EMAIL`. For real SMS delivery, configure the
three Twilio Verify variables. No third-party Python package is required for
these adapters; they use Django and Python's standard library.

The Google Maps JavaScript API is deliberately not enabled by default because it
would require a user-owned API key and billing setup. The shopkeeper form's
current-location button uses the browser API and stores coordinates in the form;
an address/geocoding service can be added later after a key and budget are chosen.

## Official references checked

- [Brevo pricing and free-plan limits](https://help.brevo.com/hc/en-us/articles/208589409-About-Brevo-s-pricing-plans)
- [Twilio Verify pricing](https://www.twilio.com/en-us/verify/pricing) and [Twilio trial units](https://www.twilio.com/docs/usage/trials)
- [Google Maps Platform setup and billing requirements](https://developers.google.com/maps/get-started)
