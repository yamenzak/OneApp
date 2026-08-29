"""Domain modes.

Wildcard creates sites directly on our root domain — one certificate covers every
tenant. Per-tenant creates on Frappe Cloud's domain and attaches ours, which
costs one Let's Encrypt certificate per tenant against a limit of 50 per
registered domain per week.
"""

import pytest


@pytest.fixture
def steps(stub_frappe):
	from oneapp_control.provisioning import steps as module

	return module


class FakeShard:
	def __init__(self, mode="Per-tenant", press_default_domain="frappe.cloud"):
		self.name = "shard-1"
		self.domain = "4dl.app"
		self.domain_mode = mode
		self.press_default_domain = press_default_domain


def test_wildcard_creates_on_our_own_domain(steps):
	assert steps.creation_domain(FakeShard(mode="Wildcard")) == "4dl.app"


def test_per_tenant_creates_on_the_frappe_cloud_domain(steps):
	"""A site cannot be created on a root domain press holds no certificate for."""
	assert steps.creation_domain(FakeShard()) == "frappe.cloud"


def test_per_tenant_without_a_default_domain_fails_loudly(steps):
	from oneapp_control.press.client import PressPermanentError

	with pytest.raises(PressPermanentError):
		steps.creation_domain(FakeShard(press_default_domain=""))


def test_uses_wildcard_flag(steps):
	assert steps.uses_wildcard(FakeShard(mode="Wildcard"))
	assert not steps.uses_wildcard(FakeShard())


def test_domain_steps_are_in_the_pipeline_before_routing(steps):
	"""Mail routing and finalisation record the hostname, so it has to work first."""
	names = [n for n, _ in steps.PIPELINES["Create Site"]]

	# every domain step precedes both
	for step in ("create_dns_record", "attach_domain", "await_domain_active", "promote_domain"):
		assert names.index(step) < names.index("register_mail_routing"), step
		assert names.index(step) < names.index("finalise_creation"), step


def test_certificate_waits_come_after_the_site_exists(steps):
	names = [n for n, _ in steps.PIPELINES["Create Site"]]
	assert names.index("create_site") < names.index("create_dns_record")
	assert names.index("create_dns_record") < names.index("attach_domain")
	assert names.index("attach_domain") < names.index("await_domain_active")


def test_archive_releases_the_hostname(steps):
	names = [n for n, _ in steps.PIPELINES["Archive Site"]]
	assert "remove_dns_record" in names
	# Cleanup precedes the archive so a failed archive does not strand DNS.
	assert names.index("remove_dns_record") < names.index("archive_site")


def test_dns_propagation_is_treated_as_transient(steps):
	"""Press resolves the CNAME inside add_domain. We create that record seconds
	earlier, so a propagation lag must retry rather than fail the tenant."""
	assert steps._is_dns_not_ready(
		Exception("Unable to connect to the domain. Is the DNS correct?")
	)
	assert steps._is_dns_not_ready(Exception("domain does not resolve to the site"))


def test_a_real_domain_error_is_still_permanent(steps):
	"""Retrying a genuinely invalid domain forever would hide the problem."""
	assert not steps._is_dns_not_ready(Exception("Domain already belongs to another site"))
	assert not steps._is_dns_not_ready(Exception("Invalid domain name"))
