from __future__ import annotations

import secrets

import frappe
from frappe import _

TICKET_TTL_SECONDS = 300
TICKET_PREFIX = "speedaily-sso:"


@frappe.whitelist(methods=["POST"])
def create_login_ticket(email: str) -> dict[str, str]:
	"""Create a short-lived one-time login ticket for a provisioned tenant user."""
	frappe.only_for("System Manager")
	email = (email or "").strip().lower()
	if not email:
		frappe.throw(_("User email is required"))

	user = frappe.db.get_value("User", email, ["name", "enabled", "user_type"], as_dict=True)
	if not user or not user.enabled or user.user_type != "System User":
		frappe.throw(_("The requested workspace user is unavailable"))

	ticket = secrets.token_urlsafe(32)
	frappe.cache.set_value(
		f"{TICKET_PREFIX}{ticket}",
		{"user": user.name},
		expires_in_sec=TICKET_TTL_SECONDS,
	)
	return {
		"path": f"/api/method/speedaily_bos.sso.consume_login_ticket?ticket={ticket}",
		"expires_in": str(TICKET_TTL_SECONDS),
	}


@frappe.whitelist(allow_guest=True, methods=["GET"])
def consume_login_ticket(ticket: str) -> None:
	"""Consume a login ticket once, establish a Frappe session, and enter Desk."""
	try:
		cache_key = f"{TICKET_PREFIX}{(ticket or '').strip()}"
		payload = frappe.cache.get_value(cache_key)
		if not payload:
			_respond_with_sign_in_error(
				_("Sign-in link expired"),
				_("Return to Speedaily and open your workspace again."),
				403,
				"orange",
			)
			return

		email = payload.get("user") if isinstance(payload, dict) else None
		if not email or not frappe.db.get_value("User", email, "enabled"):
			frappe.cache.delete_value(cache_key)
			_respond_with_sign_in_error(
				_("Workspace access unavailable"),
				_("Ask your organization owner to verify your workspace access."),
				403,
				"red",
			)
			return

		frappe.local.login_manager.login_as(email)
		frappe.db.commit()
		frappe.cache.delete_value(cache_key)
		frappe.local.response["type"] = "redirect"
		frappe.local.response["location"] = "/app"
	except Exception:
		frappe.log_error(
			title="Speedaily workspace sign-in failed",
			message=frappe.get_traceback(),
		)
		_respond_with_sign_in_error(
			_("Workspace sign-in could not finish"),
			_("Return to Speedaily and try opening your workspace again."),
			500,
			"red",
		)


def _respond_with_sign_in_error(
	title: str,
	message: str,
	status_code: int,
	indicator_color: str,
) -> None:
	frappe.respond_as_web_page(
		title,
		message,
		http_status_code=status_code,
		indicator_color=indicator_color,
	)
