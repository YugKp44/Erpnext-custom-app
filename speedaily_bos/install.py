from __future__ import annotations

import re
from datetime import date
from typing import Any

import frappe
from frappe import _
from frappe.sessions import clear_sessions
from frappe.utils import getdate, today

APP_NAME = "Speedaily BOS"
LOGO_URL = "/assets/speedaily_bos/images/logo.png"
DEFAULT_COUNTRY = "India"
DEFAULT_CURRENCY = "INR"
DEFAULT_LANGUAGE = "en"
DEFAULT_TIMEZONE = "Asia/Kolkata"
REQUIRED_ITEM_GROUPS = ("Products", "Services")
REQUIRED_PRICE_LISTS = {
	"Standard Selling": {"selling": 1, "buying": 0},
	"Standard Buying": {"selling": 0, "buying": 1},
}
REQUIRED_UOMS = {
	"Nos": True,
	"Kg": False,
	"Gram": False,
	"Litre": False,
	"Meter": False,
	"Box": True,
	"Set": True,
	"Hour": False,
	"Day": False,
}

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

OWNER_EXPERIENCE_ROLES = {
	"ESSENTIALS": (
		"Speedaily Owner",
		"Accounts User",
		"Accounts Manager",
		"Sales User",
		"Sales Manager",
		"Sales Master Manager",
		"Purchase User",
		"Purchase Manager",
		"Purchase Master Manager",
		"Stock User",
		"Stock Manager",
		"Item Manager",
		"Analytics",
	),
	"BUSINESS": (
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
		"Analytics",
		"India Compliance Manager",
	),
	"PROFESSIONAL": OWNER_ROLES,
}

ACCESS_PROFILE_ROLES = {
	"OWNER": OWNER_ROLES,
	"ADMIN": OWNER_ROLES,
	"ACCOUNTANT": (
		"Speedaily Accountant",
		"Accounts User",
		"Accounts Manager",
		"Auditor",
		"Analytics",
	),
	"SALES": (
		"Speedaily Sales User",
		"Sales User",
		"Sales Manager",
	),
	"PURCHASE": (
		"Speedaily Purchase User",
		"Purchase User",
		"Purchase Manager",
	),
	"INVENTORY": (
		"Speedaily Inventory User",
		"Stock User",
		"Stock Manager",
		"Item Manager",
	),
	"AUDITOR": (
		"Speedaily Viewer",
		"Auditor",
		"Analytics",
	),
	"VIEWER": (
		"Speedaily Viewer",
		"Auditor",
		"Analytics",
	),
}

MANAGED_BUSINESS_ROLES = frozenset(
	role
	for roles in (*ACCESS_PROFILE_ROLES.values(), *OWNER_EXPERIENCE_ROLES.values())
	for role in roles
)

EXPERIENCE_LINKS = {
	"ESSENTIALS": {
		"Customers",
		"Items",
		"Suppliers",
		"Sales Invoices",
		"Sales Orders",
		"Purchase Orders",
		"Purchase Invoices",
		"Payments",
		"Profit and Loss",
		"Balance Sheet",
		"Cash Flow",
		"Accounts Receivable",
	},
	"BUSINESS": {
		"Customers",
		"Items",
		"Quotations",
		"Sales Orders",
		"Sales Invoices",
		"Purchase Invoices",
		"Payments",
		"GST Settings",
		"Profit and Loss",
		"Balance Sheet",
		"Cash Flow",
		"General Ledger",
		"Accounts Receivable",
	},
}

EXPERIENCE_BLOCKED_MODULES = {
	"ESSENTIALS": {
		"Assets",
		"CRM",
		"Healthcare",
		"Maintenance",
		"Manufacturing",
		"Projects",
		"Quality Management",
		"Support",
	},
	"BUSINESS": {
		"Healthcare",
		"Maintenance",
		"Manufacturing",
		"Projects",
		"Quality Management",
		"Support",
	},
	"PROFESSIONAL": set(),
}


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
def prepare_provisioning_template(template_version: str) -> dict[str, Any]:
	"""Refuse customer data and remove reusable credentials before backup."""
	_require_system_manager()
	template_version = _required(template_version, "template_version")
	if not re.fullmatch(r"[A-Za-z0-9._-]{1,80}", template_version):
		frappe.throw(_("Template version contains unsupported characters"))

	companies = frappe.get_all("Company", pluck="name")
	if companies:
		frappe.throw(
			_("Provisioning template must not contain company data: {0}").format(
				", ".join(companies)
			)
		)

	allowed_users = {"Administrator", "Guest"}
	unexpected_users = [
		user
		for user in frappe.get_all("User", pluck="name")
		if user not in allowed_users
	]
	if unexpected_users:
		frappe.throw(
			_("Provisioning template contains non-system users: {0}").format(
				", ".join(unexpected_users)
			)
		)

	if frappe.get_meta("User").has_field("api_key"):
		frappe.db.sql("update `tabUser` set `api_key` = null")
	frappe.db.sql("delete from `__Auth` where `doctype` = 'User'")

	for doctype in (
		"Sessions",
		"Activity Log",
		"Access Log",
		"Error Log",
		"Scheduled Job Log",
		"Route History",
	):
		if frappe.db.exists("DocType", doctype):
			frappe.db.delete(doctype)

	frappe.db.set_default("speedaily_template_version", template_version)
	frappe.db.commit()
	frappe.clear_cache()
	return {
		"template_version": template_version,
		"status": "READY_FOR_BACKUP",
	}


@frappe.whitelist()
def configure_tenant(
	organization_name: str,
	abbreviation: str | None = None,
	country: str = DEFAULT_COUNTRY,
	currency: str = DEFAULT_CURRENCY,
	timezone: str = DEFAULT_TIMEZONE,
	business_type: str = "OTHER",
	industry: str = "OTHER",
	experience_level: str = "ESSENTIALS",
	employee_size: str = "SOLO",
	state: str = "",
	gst_registered: bool = False,
	gst_number: str = "",
	sells_products: bool = False,
	provides_services: bool = False,
	maintains_inventory: bool = False,
	uses_purchase_workflow: bool = False,
	uses_payroll: bool = False,
	uses_projects: bool = False,
	uses_manufacturing: bool = False,
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
	_configure_migration_friendly_gst_settings()
	company = _ensure_company(
		organization_name=organization_name,
		abbreviation=abbreviation,
		country=country,
		currency=currency,
	)
	_apply_company_profile(company, state, gst_registered, gst_number)
	configure_experience(
		experience_level=experience_level,
		industry=industry,
		maintains_inventory=maintains_inventory,
		uses_purchase_workflow=uses_purchase_workflow,
		uses_projects=uses_projects,
		uses_manufacturing=uses_manufacturing,
	)
	_store_business_profile(
		business_type=business_type,
		industry=industry,
		experience_level=experience_level,
		employee_size=employee_size,
		sells_products=sells_products,
		provides_services=provides_services,
		maintains_inventory=maintains_inventory,
		uses_purchase_workflow=uses_purchase_workflow,
		uses_payroll=uses_payroll,
		uses_projects=uses_projects,
		uses_manufacturing=uses_manufacturing,
	)
	ensure_indian_fiscal_years(company)
	complete_automated_setup()
	frappe.clear_cache()

	return {
		"company": company,
		"country": country,
		"currency": currency,
		"timezone": timezone,
		"industry": industry,
		"experience_level": experience_level,
		"status": "READY",
	}


@frappe.whitelist()
def provision_owner(
	email: str,
	first_name: str,
	last_name: str | None = None,
	company: str | None = None,
	experience_level: str = "ESSENTIALS",
) -> dict[str, Any]:
	"""Create or update the tenant owner without exposing Administrator access."""
	return provision_user(
		email=email,
		first_name=first_name,
		last_name=last_name,
		company=company,
		access_profile="OWNER",
		experience_level=experience_level,
		enabled=1,
	)


@frappe.whitelist()
def provision_user(
	email: str,
	first_name: str,
	last_name: str | None = None,
	company: str | None = None,
	access_profile: str = "VIEWER",
	experience_level: str = "ESSENTIALS",
	enabled: int = 1,
) -> dict[str, Any]:
	"""Synchronize a Speedaily teammate and replace app-managed business roles."""
	_require_system_manager()
	email = _required(email, "email").strip().lower()
	first_name = _required(first_name, "first_name")
	access_profile = _required(access_profile, "access_profile").strip().upper()
	experience_level = _required(experience_level, "experience_level").strip().upper()

	if not frappe.utils.validate_email_address(email):
		frappe.throw(_("A valid owner email address is required"))
	if access_profile not in ACCESS_PROFILE_ROLES:
		frappe.throw(_("Unsupported Speedaily access profile"))
	if experience_level not in OWNER_EXPERIENCE_ROLES:
		frappe.throw(_("Unsupported Speedaily experience level"))

	user = frappe.db.exists("User", email)
	if user:
		doc = frappe.get_doc("User", email)
		doc.first_name = first_name
		doc.last_name = last_name or ""
		doc.enabled = int(bool(enabled))
		doc.user_type = "System User"
	else:
		doc = frappe.get_doc(
			{
				"doctype": "User",
				"email": email,
				"first_name": first_name,
				"last_name": last_name or "",
				"enabled": int(bool(enabled)),
				"user_type": "System User",
				"send_welcome_email": 0,
			}
		)

	doc.set(
		"roles",
		[
			row
			for row in doc.get("roles")
			if row.role not in MANAGED_BUSINESS_ROLES
		],
	)
	existing_roles = {row.role for row in doc.get("roles")}
	roles_to_assign = (
		OWNER_EXPERIENCE_ROLES[experience_level]
		if access_profile in {"OWNER", "ADMIN"}
		else ACCESS_PROFILE_ROLES[access_profile]
	)
	for role in roles_to_assign:
		if frappe.db.exists("Role", role) and role not in existing_roles:
			doc.append("roles", {"role": role})

	_apply_user_module_visibility(doc, access_profile, experience_level)

	if frappe.db.exists("Workspace", APP_NAME):
		doc.default_workspace = APP_NAME

	doc.flags.ignore_permissions = True
	doc.save()

	company = company or frappe.defaults.get_global_default("company")
	if doc.enabled and company and frappe.db.exists("Company", company):
		_ensure_company_permission(email, company)

	if not doc.enabled:
		clear_sessions(user=email, keep_current=False, force=True)

	frappe.clear_cache(user=email)
	return {
		"user": email,
		"company": company,
		"access_profile": access_profile,
		"experience_level": experience_level,
		"enabled": bool(doc.enabled),
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


def configure_experience(
	experience_level: str,
	industry: str,
	maintains_inventory: bool = False,
	uses_purchase_workflow: bool = False,
	uses_projects: bool = False,
	uses_manufacturing: bool = False,
) -> None:
	"""Keep the first workspace focused while preserving ERP data underneath."""
	experience_level = (experience_level or "ESSENTIALS").upper()
	if experience_level not in OWNER_EXPERIENCE_ROLES:
		frappe.throw(_("Unsupported Speedaily experience level"))
	if not frappe.db.exists("Workspace", APP_NAME):
		return

	workspace = frappe.get_doc("Workspace", APP_NAME)
	allowed = EXPERIENCE_LINKS.get(experience_level)
	for link in workspace.get("links"):
		if link.type == "Card Break":
			hidden = 0
		elif allowed is None:
			hidden = 0
		else:
			hidden = 0 if link.label in allowed else 1
		if link.hidden != hidden:
			frappe.db.set_value(
				link.doctype,
				link.name,
				"hidden",
				hidden,
				update_modified=False,
			)

	workspace.db_set("modified", frappe.utils.now(), update_modified=False)
	frappe.clear_cache(doctype="Workspace")
	frappe.db.set_default("speedaily_experience_level", experience_level)
	frappe.db.set_default("speedaily_industry", (industry or "OTHER").upper())
	frappe.db.set_default("speedaily_inventory_enabled", int(bool(maintains_inventory)))
	frappe.db.set_default("speedaily_purchase_enabled", int(bool(uses_purchase_workflow)))
	frappe.db.set_default("speedaily_projects_enabled", int(bool(uses_projects)))
	frappe.db.set_default("speedaily_manufacturing_enabled", int(bool(uses_manufacturing)))


def _apply_user_module_visibility(
	user_doc: Any,
	access_profile: str,
	experience_level: str,
) -> None:
	if access_profile not in {"OWNER", "ADMIN"}:
		return
	available_modules = set(frappe.get_all("Module Def", pluck="name"))
	blocked_modules = EXPERIENCE_BLOCKED_MODULES[experience_level] & available_modules
	user_doc.set(
		"block_modules",
		[{"module": module} for module in sorted(blocked_modules)],
	)


def _apply_company_profile(
	company_name: str,
	state: str,
	gst_registered: bool,
	gst_number: str,
) -> None:
	company = frappe.get_doc("Company", company_name)
	meta = frappe.get_meta("Company")
	if state and meta.has_field("state"):
		company.state = state
	if gst_registered and gst_number and meta.has_field("gstin"):
		company.gstin = gst_number
	if gst_registered and gst_number and meta.has_field("tax_id"):
		company.tax_id = gst_number
	company.flags.ignore_permissions = True
	company.save()


def _store_business_profile(**profile: Any) -> None:
	for key, value in profile.items():
		frappe.db.set_default(f"speedaily_{key}", value)


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
	_install_erpnext_presets_if_missing()
	_ensure_item_groups()
	_ensure_uoms()
	_ensure_price_lists()
	_ensure_transit_warehouse_type()


def _install_erpnext_presets_if_missing() -> None:
	if (
		"erpnext" not in frappe.get_installed_apps()
		or not frappe.db.exists("DocType", "Item Group")
		or frappe.db.exists("Item Group", _("All Item Groups"))
	):
		return

	from erpnext.setup.setup_wizard.operations.install_fixtures import install

	install(DEFAULT_COUNTRY)


def _ensure_item_groups() -> None:
	if not frappe.db.exists("DocType", "Item Group"):
		return

	root_item_group = _("All Item Groups")
	if not frappe.db.exists("Item Group", root_item_group):
		doc = frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": root_item_group,
				"parent_item_group": "",
				"is_group": 1,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()

	parent = frappe.db.get_value(
		"Item Group",
		{"is_group": 1},
		"name",
		order_by="lft asc",
	)
	if not parent:
		frappe.throw(_("ERPNext does not contain a root Item Group"))

	for item_group in REQUIRED_ITEM_GROUPS:
		if frappe.db.exists("Item Group", item_group):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Item Group",
				"item_group_name": item_group,
				"parent_item_group": parent,
				"is_group": 0,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()


def _ensure_uoms() -> None:
	if not frappe.db.exists("DocType", "UOM"):
		return

	for uom_name, whole_number in REQUIRED_UOMS.items():
		if frappe.db.exists("UOM", uom_name):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "UOM",
				"uom_name": uom_name,
				"enabled": 1,
				"must_be_whole_number": int(whole_number),
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()


def _ensure_price_lists() -> None:
	if not frappe.db.exists("DocType", "Price List"):
		return

	currency = frappe.defaults.get_global_default("currency") or DEFAULT_CURRENCY
	for price_list_name, flags in REQUIRED_PRICE_LISTS.items():
		if frappe.db.exists("Price List", price_list_name):
			continue
		doc = frappe.get_doc(
			{
				"doctype": "Price List",
				"price_list_name": price_list_name,
				"currency": currency,
				"enabled": 1,
				**flags,
			}
		)
		doc.flags.ignore_permissions = True
		doc.insert()


def _ensure_transit_warehouse_type() -> None:
	if (
		not frappe.db.exists("DocType", "Warehouse Type")
		or frappe.db.exists("Warehouse Type", "Transit")
	):
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
		_set_single_if_field("System Settings", "enable_onboarding", 0)
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


def _configure_migration_friendly_gst_settings() -> None:
	"""Allow incomplete legacy masters to import before final GST classification."""
	if not frappe.db.exists("DocType", "GST Settings"):
		return
	_set_single_if_field("GST Settings", "validate_hsn_code", 0)


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
