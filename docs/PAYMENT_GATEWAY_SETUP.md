# Razorpay payment gateway handoff

## Environment configuration

Keep gateway credentials only in the local `.env` file or the deployment
secret store. They must never be added to a commit or browser JavaScript.

```dotenv
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
```

Restart the web service after changing any of these values.

## Dashboard configuration

1. Use Test Mode while developing and Live Mode only after the business
   account is activated.
2. Add the `payment.captured` webhook in Razorpay Dashboard.
3. Set its endpoint to `https://YOUR_DOMAIN/api/payments/razorpay/webhook/`.
4. Copy the webhook signing secret into `RAZORPAY_WEBHOOK_SECRET`.

## Payment flow

RideHub creates the order on the server, verifies the Razorpay signature on
the server, and captures an authorised payment before marking a booking paid.
If Checkout closes or a callback is delayed, the client reconciles with the
server without cancelling the reservation, so a customer can retry safely.

## Release checklist

- Confirm `RAZORPAY_KEY_ID` uses the intended test or live key.
- Make one test payment and verify the booking is marked paid.
- Confirm the webhook has a 2xx delivery result in Razorpay Dashboard.
- Never expose keys, payment identifiers, or customer details in commits.
