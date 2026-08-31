"""The two ends have to spell the R2 key layout the same way.

They deploy separately. A rolling backup written under a prefix retention does
not sweep is a bill nobody notices; a cold copy written where retention *does*
sweep is a workspace that cannot be restored. Neither shows up as an error, and
both are one typo.

Static, by AST, because the tenant module and the control module cannot be
imported into the same process with one stub `frappe`.
"""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TENANT = ROOT / "apps/oneapp/oneapp/oneapp_core/backup.py"
CONTROL = ROOT / "apps/oneapp_control/oneapp_control/lifecycle/backups.py"


def constants(path: Path) -> dict:
	found = {}
	for node in ast.parse(path.read_text()).body:
		if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
			for target in node.targets:
				if isinstance(target, ast.Name):
					found[target.id] = node.value.value
	return found


def test_both_ends_agree_on_where_a_rolling_backup_goes():
	assert constants(TENANT)["BACKUP_PREFIX"] == constants(CONTROL)["BACKUP_PREFIX"]


def test_both_ends_agree_on_where_the_cold_copy_goes():
	assert constants(TENANT)["COLD_PREFIX"] == constants(CONTROL)["COLD_PREFIX"]


def test_the_two_prefixes_are_different():
	"""If they were the same, retention would expire the cold copy."""
	tenant = constants(TENANT)
	assert tenant["BACKUP_PREFIX"] != tenant["COLD_PREFIX"]


def test_neither_prefix_is_where_customer_files_live():
	"""`tenants/` is the attachments. Deleting a backup must never reach them."""
	tenant = constants(TENANT)
	assert "tenants" not in (tenant["BACKUP_PREFIX"], tenant["COLD_PREFIX"])


def test_the_artifacts_a_restore_needs_are_all_named():
	"""Fixed names rather than Frappe's timestamped ones, so a restore can
	address a file without listing the prefix first."""
	names = set()
	for node in ast.walk(ast.parse(TENANT.read_text())):
		if isinstance(node, ast.Assign) and any(
			getattr(t, "id", None) == "ARTIFACTS" for t in node.targets
		):
			names = {pair[1] for pair in ast.literal_eval(node.value)}

	assert names == {
		"database.sql.gz",
		"public-files.tar",
		"private-files.tar",
		"site-config.json",
	}, names
