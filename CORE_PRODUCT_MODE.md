# TENARA core product mode

TENARA currently ships as a focused rental-management monolith.

## Core workflows

- Landlord sign-up and login
- Property and unit management
- Tenant and lease management
- Invoice creation and tracking
- Manual rent-payment recording
- Expense tracking
- Basic reports
- Tenant portal

## Deferred modules

The following remain in the repository for later reactivation but are not part of the primary workflow:

- Subscription plans and upgrades
- Reminders and automated notifications
- M-Pesa and SMS integrations
- Live demo auto-login
- Platform billing dashboards

## Configuration

`CORE_PRODUCT_MODE=True` is the default. The related feature flags are defined in `tenara/settings.py`:

- `ENABLE_SUBSCRIPTIONS=False`
- `ENABLE_REMINDERS=False`
- `ENABLE_MPESA=False`
- `ENABLE_SMS=False`

To reactivate a deferred module, enable its flag and restore its navigation/action entry points deliberately; do not expose partially configured integrations by default.
