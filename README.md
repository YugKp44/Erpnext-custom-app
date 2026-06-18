# Speedaily BOS Frappe App

Upgrade-safe Speedaily branding and tenant setup for Frappe Framework 16 and
ERPNext 16.

## Responsibilities

- Apply Speedaily BOS branding to Desk and login pages.
- Install a focused Speedaily BOS workspace.
- Create Speedaily business roles.
- Configure Indian defaults.
- Create the tenant company and organization owner.
- Keep all customizations outside Frappe and ERPNext core.

## Supported stack

- Frappe Framework 16
- ERPNext 16
- India Compliance 16
- Python 3.10 or newer

## Local installation

From the Frappe bench:

```bash
bench get-app https://github.com/YOUR_ACCOUNT/Speedaily-BOS-Frappe-App.git
bench --site org-47.internal install-app speedaily_bos
bench --site org-47.internal migrate
bench build --app speedaily_bos
bench --site org-47.internal clear-cache
```

## Configure a tenant

Run after ERPNext and India Compliance are installed:

```bash
bench --site org-47.internal execute \
  speedaily_bos.install.configure_tenant \
  --kwargs '{
    "organization_name": "Example Private Limited",
    "country": "India",
    "currency": "INR",
    "timezone": "Asia/Kolkata"
  }'
```

Create the organization owner:

```bash
bench --site org-47.internal execute \
  speedaily_bos.install.provision_owner \
  --kwargs '{
    "email": "owner@example.com",
    "first_name": "Example",
    "last_name": "Owner"
  }'
```

The owner is created as a System User without a shared Administrator password.
Production access should use Speedaily SSO.

## Production image

Add the application to `apps.json` used by the custom Frappe Docker image:

```json
[
  {
    "url": "https://github.com/frappe/erpnext",
    "branch": "version-16"
  },
  {
    "url": "https://github.com/resilient-tech/india-compliance",
    "branch": "version-16"
  },
  {
    "url": "https://github.com/YOUR_ACCOUNT/Speedaily-BOS-Frappe-App",
    "branch": "main"
  }
]
```

Provisioning should install applications in this order:

```text
frappe -> erpnext -> india_compliance -> speedaily_bos
```

Then run `migrate`, set the public `host_name`, configure the tenant, provision
the owner, generate integration credentials, and verify the connection.

## Branding assets

The primary logo is:

```text
/assets/speedaily_bos/images/logo.png
```

Replace that file with a transparent PNG of the same brand when the production
logo changes. Rebuild assets and clear cache afterward.

## Security notes

- UI hiding is not authorization.
- Business access must be controlled through Frappe roles and permissions.
- Do not give tenant users the `Administrator` password.
- Do not expose integration API secrets to browser, Electron, or mobile code.
- Keep Frappe, ERPNext, and India Compliance licenses and notices intact.

