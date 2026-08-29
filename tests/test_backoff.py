"""Provisioning retry backoff.

Frappe Cloud is not ours to hammer: a tight retry loop against press is both
rude and a good way to get rate limited during an incident.
"""

import pytest


@pytest.fixture
def runner():
	from oneapp_control.provisioning import runner as module

	return module


def test_backoff_grows(runner):
	values = [runner.backoff_for(n) for n in range(1, 6)]
	assert values == sorted(values)
	assert values[0] < values[-1]


def test_first_attempt_is_short(runner):
	assert runner.backoff_for(1) == runner.BASE_BACKOFF_SECONDS


def test_backoff_is_capped(runner):
	assert runner.backoff_for(50) == runner.MAX_BACKOFF_SECONDS


def test_backoff_never_zero(runner):
	"""A zero backoff would spin the queue."""
	assert all(runner.backoff_for(n) > 0 for n in range(0, 20))


def test_attempt_ceiling_is_reachable_and_bounded(runner):
	"""A permanently broken job must eventually stop, not retry forever."""
	assert 1 < runner.MAX_ATTEMPTS <= 50
