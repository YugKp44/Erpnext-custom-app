from __future__ import annotations

import re
from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.utils import getdate, today

APP_NAME = "Speedaily BOS"
LOGO_URL = "/assets/speedaily_bos/images/logo.png"
DEFAULT_COUNTRY = "India"
DEFAULT_CURRENCY = "INR"
DEFAULT_LANGUAGE = "en"
DEFAULT_TIMEZONE = "Asia/Kolkata"

SPEEDAILY_ROLES = (
	"Speedaily Owner",
	"Speedaily Accountant",
	"Speedaily Sales User",
	"Speedaily Purchase User",
	"Speedaily Inventory User",
	"Speedaily Viewer",
)

OWNER_ROLES = (
	"Speedaily Owner",
	"Accounts User",
	"Accounts Manager",
	"Auditor",
	"Sales User",
	"Sales Manager",
	"Sales Master Manager",
	"Purchase User",
	"Purchase Manager",
	"Purchase Master Manager",
	"Stock User",
	"Stock Manager",
	"Item Manager",
	"Manufacturing User",
	"Manufacturing Manager",
	"Projects User",
	"Projects Manager",
	"Quality Inspector",
	"Quality Manager",
	"Maintenance User",
	"Maintenance Manager",
	"Support Team",
	"Support Manager",
	"Agriculture User",
	"Agriculture Manager",
	"Fleet Manager",
	"Analytics",
	"Dashboard Manager",
	"India Compliance Manager",
)


def after_install() -> None:
	"""Install idempotent branding and access primitives."""
	apply_branding()
	ensure_roles()
	ensure_required_erpnext_masters()
	frappe.clear_cache()


def after_migrate() -> None:
	"""Restore app-owned configuration after framework migrations."""
	apply_branding()
	ensure_roles()
	ensure_required_erpnext_masters()
	frappe.clear_cache()


@frappe.whitelist()
def configure_tenant(
	organization_name: str,
	abbreviation: str | None = None,
	country: str = DEFAULT_COUNTRY,
	currency: str = DEFAULT_CURRENCY,
	timezone: str = DEFAULT_TIMEZONE,
) -> dict[str, Any]:
	"""Configure defaults and create the tenant company when it is missing."""
	_require_system_manager()
	organization_name = _required(organization_name, "organization_name")
	country = country or DEFAULT_COUNTRY
	currency = currency or DEFAULT_CURRENCY
	timezone = timezone or DEFAULT_TIMEZONE

	apply_branding()
	ensure_roles()
	ensure_required_erpnext_masters()
	_set_accounting_defaults(country, currency, timezone)
	company = _ensure_company(
		organization_name=organization_name,
		abbreviation=abbreviation,
		country=country,
		currency=currency,
	)
	ensure_indian_fiscal_years(company)
	complete_automated_setup()
	frappe.clear_cache()

	return {
		"company": company,
		"country": country,
		"currency": currency,
		"timezone": timezone,
		"status": "READY",
	}


@frappe.whitelist()
def provision_owner(
	email: str,
	first_name: str,
	last_name: str | None = None,
	company: str | None = None,
) -> dict[str, Any]:
	"""Create or update the tenant owner without exposing Administrator access."""
	_require_system_manager()
	email = _required(email, "email").strip().lower()
	first_name = _required(first_name, "first_name")

	if not frappe.utils.validate_email_address(email):
		frappe.throw(_("A valid owner email address is required"))

	user = frappe.db.exists("User", email)
	if user:
		doc = frappe.get_doc("User", email)
		doc.first_name = first_name
		doc.last_name = last_name or ""
		doc.enabled = 1
		doc.user_type = "System User"
	else:
		doc = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"last_name": last_name or "",
				"enabled": 1,
				"user_type": "System User",
				"send_welcome_email": 0,
			}
		)

	existing_roles = {row.role for row in doc.get("roles")}
	for role in OWNER_ROLES:
		if frappe.db.exists("Role", role) and role not in existing_roles:
			doc.append("roles", {"role": role})

	if frappe.db.exists("Workspace", APP_NAME):
		doc.default_workspace = APP_NAME

	doc.flags.ignore_permissions = True
	doc.save()

	company = company or frappe.defaults.get_global_default("company")
	if company and frappe.db.exists("Company", company):
		_ensure_company_permission(email, company)

	frappe.clear_cache(user=email)
	return {
		"user": email,
		"company": company,
		"roles": sorted({row.role for row in doc.get("roles")}),
		"status": "READY",
	}


def apply_branding() -> None:
	"""Apply only fields available in the installed Frappe version."""
	if frappe.db.exists("DocType", "Website Settings"):
		_set_single_if_field("Website Settings", "app_name", APP_NAME)
		_set_single_if_field("Website Settings", "app_logo", LOGO_URL)
		_set_single_if_field("Website Settings", "favicon", LOGO_URL)
		_set_single_if_field("Website Settings", "splash_image", LOGO_URL)
		_set_single_if_field("Website Settings", "banner_image", LOGO_URL)

	if frappe.db.exists("DocType", "System Settings"):
		_set_single_if_field("System Settings", "app_name", APP_NAME)


def ensure_roles() -> None:
	for role_name in SPEEDAILY_ROLES:
		if frappe.db.exists("Role", role_name):
			continue
		frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": role_name,
				"desk_access": 1,
			}
		).insert(ignore_permissions=True)


def ensure_required_erpnext_masters() -> None:
	"""Create ERPNext masters required by automated company provisioning."""
	if not frappe.db.exists("DocType", "Warehouse Type"):
		return
	if frappe.db.exists("Warehouse Type", "Transit"):
		return

	warehouse_type = frappe.get_doc(
		{
			"doctype": "Warehouse Type",
			"__newname": "Transit",
			"description": "Goods moving between company warehouses",
		}
	)
	warehouse_type.flags.ignore_permissions = True
	warehouse_type.insert()


def complete_automated_setup() -> None:
	"""Mark installed applications ready after Speedaily finishes tenant setup."""
	if not frappe.db.exists("DocType", "Installed Application"):
		return

	installed_apps = frappe.get_installed_apps(_ensure_on_bench=True)
	for app_name in installed_apps:
		frappe.db.set_value(
			"Installed Application",
			{"app_name": app_name},
			"is_setup_complete",
			1,
		)

	if frappe.db.exists("DocType", "System Settings"):
		_set_single_if_field("System Settings", "setup_complete", 1)
		_set_single_if_field("System Settings", "enable_onboarding", 1)
	frappe.db.set_default("desktop:home_page", "workspace")


def ensure_indian_fiscal_years(company: str, reference_date: str | date | None = None) -> list[str]:
	"""Ensure the current and next April-March fiscal years exist for a company."""
	if not frappe.db.exists("DocType", "Fiscal Year"):
		return []

	current_date = getdate(reference_date or today())
	start_year = current_date.year if current_date.month >= 4 else current_date.year - 1
	fiscal_years = []

	for year in (start_year, start_year + 1):
		start_date = date(year, 4, 1)
		end_date = date(year + 1, 3, 31)
		fiscal_years.append(_ensure_fiscal_year(company, start_date, end_date))

	frappe.cache().delete_key("fiscal_years")
	return fiscal_years


def _ensure_fiscal_year(company: str, start_date: date, end_date: date) -> str:
	existing = frappe.db.get_value(
		"Fiscal Year",
		{
			"year_start_date": start_date,
			"year_end_date": end_date,
		},
		"name",
	)
	if existing:
		doc = frappe.get_doc("Fiscal Year", existing)
		companies = {row.company for row in doc.get("companies")}
		if companies and company not in companies:
			doc.append("companies", {"company": company})
			doc.flags.ignore_permissions = True
			doc.save()
		if doc.disabled:
			doc.db_set("disabled", 0)
		return doc.name

	year_name = f"{start_date.year}-{end_date.year}"
	doc = frappe.get_doc(
		{
			"doctype": "Fiscal Year",
			"year": year_name,
			"year_start_date": start_date,
			"year_end_date": end_date,
			"disabled": 0,
			"companies": [{"company": company}],
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc.name


def _set_accounting_defaults(country: str, currency: str, timezone: str) -> None:
	frappe.db.set_default("country", country)
	frappe.db.set_default("currency", currency)
	frappe.db.set_default("language", DEFAULT_LANGUAGE)

	if frappe.db.exists("DocType", "System Settings"):
		_set_single_if_field("System Settings", "country", country)
		_set_single_if_field("System Settings", "language", DEFAULT_LANGUAGE)
		_set_single_if_field("System Settings", "time_zone", timezone)


def _ensure_company(
	organization_name: str,
	abbreviation: str | None,
	country: str,
	currency: str,
) -> str:
	if not frappe.db.exists("DocType", "Company"):
		frappe.throw(_("ERPNext must be installed before configuring a Speedaily tenant"))

	existing = frappe.db.exists("Company", organization_name)
	if existing:
		company_name = str(existing)
	else:
		company = frappe.get_doc(
			{
				"doctype": "Company",
				"company_name": organization_name,
				"abbr": _company_abbreviation(organization_name, abbreviation),
				"default_currency": currency,
				"country": country,
			}
		)
		company.flags.ignore_permissions = True
		company.insert()
		company_name = company.name

	frappe.db.set_default("company", company_name)
	frappe.db.set_default("default_company", company_name)
	return company_name


def _ensure_company_permission(user: str, company: str) -> None:
	if frappe.db.exists(
		"User Permission",
		{"user": user, "allow": "Company", "for_value": company},
	):
		return
	frappe.get_doc(
		{
			"doctype": "User Permission",
			"user": user,
			"allow": "Company",
			"for_value": company,
			"apply_to_all_doctypes": 1,
		}
	).insert(ignore_permissions=True)


def _company_abbreviation(name: str, requested: str | None) -> str:
	if requested and requested.strip():
		base = requested.strip().upper()
	else:
		words = re.findall(r"[A-Za-z0-9]+", name)
		base = "".join(word[0] for word in words[:5]).upper()
		if len(base) < 2:
			base = re.sub(r"[^A-Za-z0-9]", "", name).upper()[:5]
	base = base[:5] or "BOS"

	candidate = base
	suffix = 1
	while frappe.db.exists("Company", {"abbr": candidate}):
		suffix += 1
		candidate = f"{base[: max(1, 5 - len(str(suffix)))]}{suffix}"
	return candidate


def _set_single_if_field(doctype: str, fieldname: str, value: Any) -> None:
	if frappe.get_meta(doctype).has_field(fieldname):
		frappe.db.set_single_value(doctype, fieldname, value)


def _required(value: str | None, fieldname: str) -> str:
	if value is None or not value.strip():
		frappe.throw(_("{0} is required").format(fieldname))
	return value.strip()


def _require_system_manager() -> None:
	if getattr(frappe.flags, "in_install", False) or getattr(frappe.flags, "in_migrate", False):
		return
	if frappe.session.user == "Administrator":
		return
	frappe.only_for("System Manager")
