import ast
import json
import pathlib
import tomllib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class PackageStructureTest(unittest.TestCase):
	def test_required_files_exist(self):
		required = [
			"pyproject.toml",
			"speedaily_bos/__init__.py",
			"speedaily_bos/hooks.py",
			"speedaily_bos/install.py",
			"speedaily_bos/sso.py",
			"speedaily_bos/public/css/speedaily.css",
			"speedaily_bos/public/js/speedaily.js",
			"speedaily_bos/public/images/logo.png",
			"speedaily_bos/speedaily_bos/workspace/speedaily_bos/speedaily_bos.json",
		]
		for relative_path in required:
			self.assertTrue((ROOT / relative_path).is_file(), relative_path)

	def test_python_files_parse(self):
		for path in (ROOT / "speedaily_bos").rglob("*.py"):
			ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

	def test_tenant_setup_bootstraps_required_erpnext_masters(self):
		source = (ROOT / "speedaily_bos" / "install.py").read_text(encoding="utf-8")
		tree = ast.parse(source)
		functions = {
			node.name: node
			for node in tree.body
			if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
		}
		configure_calls = {
			node.func.id
			for node in ast.walk(functions["configure_tenant"])
			if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
		}
		self.assertIn("ensure_required_erpnext_masters", configure_calls)
		self.assertIn("ensure_indian_fiscal_years", configure_calls)
		self.assertIn("complete_automated_setup", configure_calls)
		self.assertIn('"__newname": "Transit"', source)

	def test_workspace_is_valid_json(self):
		path = (
			ROOT
			/ "speedaily_bos"
			/ "speedaily_bos"
			/ "workspace"
			/ "speedaily_bos"
			/ "speedaily_bos.json"
		)
		workspace = json.loads(path.read_text(encoding="utf-8"))
		self.assertEqual("Workspace", workspace["doctype"])
		self.assertEqual("Speedaily BOS", workspace["name"])
		self.assertEqual("Speedaily BOS", workspace["title"])
		self.assertIsInstance(json.loads(workspace["content"]), list)
		self.assertGreater(len(workspace["links"]), 10)

	def test_owner_defaults_to_speedaily_workspace(self):
		install_source = (ROOT / "speedaily_bos" / "install.py").read_text(encoding="utf-8")
		sso_source = (ROOT / "speedaily_bos" / "sso.py").read_text(encoding="utf-8")
		self.assertIn("doc.default_workspace = APP_NAME", install_source)
		self.assertIn("redirect_post_login(desk_user=True)", sso_source)

	def test_sso_uses_frappe_redirect_and_friendly_expiry_page(self):
		source = (ROOT / "speedaily_bos" / "sso.py").read_text(encoding="utf-8")
		self.assertIn("from frappe.utils.oauth import redirect_post_login", source)
		self.assertIn("redirect_post_login(desk_user=True)", source)
		self.assertIn("frappe.respond_as_web_page(", source)
		self.assertIn("TICKET_TTL_SECONDS = 300", source)
		self.assertNotIn('frappe.local.response["location"]', source)

	def test_owner_receives_operational_master_data_roles(self):
		source = (ROOT / "speedaily_bos" / "install.py").read_text(encoding="utf-8")
		tree = ast.parse(source)
		owner_roles = next(
			node
			for node in tree.body
			if isinstance(node, ast.Assign)
			and any(isinstance(target, ast.Name) and target.id == "OWNER_ROLES" for target in node.targets)
		)
		roles = {element.value for element in owner_roles.value.elts}
		self.assertTrue(
			{
				"Accounts User",
				"Sales User",
				"Sales Master Manager",
				"Purchase User",
				"Purchase Master Manager",
				"Stock User",
				"Item Manager",
				"Manufacturing Manager",
				"Projects Manager",
				"Quality Manager",
				"Maintenance Manager",
				"Support Manager",
				"Analytics",
			}.issubset(roles)
		)
		self.assertTrue(
			{
				"System Manager",
				"Role Manager",
				"User Manager",
				"Script Manager",
				"Workspace Manager",
			}.isdisjoint(roles)
		)

	def test_teammate_profiles_are_explicit_and_managed_roles_are_replaced(self):
		source = (ROOT / "speedaily_bos" / "install.py").read_text(encoding="utf-8")
		self.assertIn('"ACCOUNTANT": (', source)
		self.assertIn('"SALES": (', source)
		self.assertIn('"PURCHASE": (', source)
		self.assertIn('"INVENTORY": (', source)
		self.assertIn('"AUDITOR": (', source)
		self.assertIn("MANAGED_BUSINESS_ROLES", source)
		self.assertIn("row.role not in MANAGED_BUSINESS_ROLES", source)
		self.assertIn("clear_sessions(user=email", source)

	def test_experience_profiles_control_roles_and_workspace_links(self):
		source = (ROOT / "speedaily_bos" / "install.py").read_text(encoding="utf-8")
		self.assertIn("OWNER_EXPERIENCE_ROLES", source)
		self.assertIn('"ESSENTIALS": {', source)
		self.assertIn('"BUSINESS": {', source)
		self.assertIn("def configure_experience(", source)
		self.assertIn("frappe.db.set_value(", source)
		self.assertNotIn("workspace.save()", source)
		self.assertIn("EXPERIENCE_BLOCKED_MODULES", source)
		self.assertIn('user_doc.set(\n\t\t"block_modules"', source)

	def test_owner_can_reach_speedaily_team_management(self):
		source = (
			ROOT / "speedaily_bos" / "public" / "js" / "speedaily.js"
		).read_text(encoding="utf-8")
		self.assertIn('const TEAM_URL = "https://speedaily.dev/app/team"', source)
		self.assertIn('roles.includes("Speedaily Owner")', source)

	def test_frappe_dependencies_are_pinned_to_version_16(self):
		metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
		dependencies = metadata["tool"]["bench"]["frappe-dependencies"]
		self.assertEqual(
			{"frappe", "erpnext", "india_compliance"},
			set(dependencies),
		)
		for version_range in dependencies.values():
			self.assertIn(">=16.0.0", version_range)
			self.assertIn("<17.0.0", version_range)


if __name__ == "__main__":
	unittest.main()
