# TENARA production-readiness plan

This repository now contains the implementation and automation that can be safely completed without access to a hosting account or provider credentials. No system can honestly be called “100% production ready” until the deployment-specific acceptance checks below pass in the real environment.

## Implemented in this pass

1. **Core flow:** property → unit → tenant → lease → invoice → payment is covered by integration tests.
2. **PostgreSQL path:** production settings use PostgreSQL when `DEBUG=False`; staging Docker Compose is included.
3. **Supported framework:** Django is pinned to the supported 5.2 LTS line; the previous 4.2.7 pin was past upstream support.
4. **Managed-host database support:** `DATABASE_URL` is supported alongside individual `DB_*` variables.
5. **Secrets:** `.env.example` documents required secrets and production settings reject the insecure default secret.
6. **CI/CD foundation:** `.github/workflows/ci.yml` runs checks, migrations, tests, compilation, static collection, and diff validation.
7. **Password reset:** Django’s signed, expiring reset-token flow is wired with email templates.
8. **Authorization:** core ownership-isolation tests cover cross-landlord invoice access.
9. **Money integrity:** Decimal handling, positive amount validators, database constraints, idempotent payment confirmation, and audit events are implemented.
10. **Health/monitoring foundation:** `/healthz/`, structured console/file logging, Docker healthcheck, and CI are present.
11. **Rate limiting:** login and password-reset attempts are cache-throttled.
12. **Uploads:** receipts and payment proofs are limited to 5 MB and PDF/JPG/JPEG/PNG extensions.
13. **Lease lifecycle:** only one active lease per unit is enforced at the database level.
14. **Performance:** dashboard and expense lists use bounded querysets and related-object loading; production profiling remains required.
15. **Seed/demo:** the existing demo app remains available; add sanitized staging fixtures before UAT.
16. **Browser QA:** backend workflow tests are present; browser tests remain a staging acceptance task.
17. **Deferred features:** subscriptions, reminders, SMS, and M-Pesa remain disabled until their provider contracts and acceptance tests are completed.

## Required before production approval

- Set `DEBUG=False`, a strong `SECRET_KEY`, exact `ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS`. Prefer `DATABASE_URL` on managed hosts.
- Provision PostgreSQL, Redis, SMTP, object/private media storage, backups, and monitoring.
- Run `docker compose -f docker-compose.staging.yml up --build` with real staging secrets.
- Run `python manage.py check --deploy`, migrations, CI, and browser UAT in staging. The repository tests are the automated gate; browser UAT must be run against the deployed staging URL.
- Verify password-reset delivery and account recovery with a real email inbox.
- Configure private media storage and signed download URLs if receipts contain personal data.
- Add error tracking/alert routing and verify restore-from-backup procedures. The `/healthz/` endpoint is the liveness check; connect it to the hosting provider monitor.
- Perform a dependency and penetration review before public launch.
- Obtain explicit provider credentials and acceptance tests before enabling M-Pesa, SMS, reminders, or billing.
