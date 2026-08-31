"""A shard may not name something Frappe Cloud does not have.

`press_server`, `press_release_group` and `press_version` are typed by hand and
read off a different screen, and every one of them fails *late*: press matches a
bench by server, version and apps, so a wrong value gets several steps into a
provision — past `create_site`, with a real site already made — and then fails
naming the wrong cause. The version is the worst, because press falls back to
its public marketplace path and the error talks about that instead.

The refusals matter, and so does everything that must *not* refuse: a shard that
cannot be saved because Frappe Cloud is briefly down is a worse failure than the
typo this prevents.
"""

import types

import pytest


@pytest.fixture
def shard(stub_frappe):
    from oneapp_control.control_plane.doctype.shard import shard as module

    # `frappe.local` is where the per-request cache lives.
    stub_frappe.local = types.SimpleNamespace()
    stub_frappe.bold = lambda v: str(v)
    return module


@pytest.fixture
def make(shard):
    """A real Shard, with the fields a save would have set.

    Subclasses the controller rather than standing in for it, so `validate`
    reaches the real `validate_against_press` — a fake that reimplements the
    method under test proves nothing about it.
    """
    class FakeShard(shard.Shard):
        def __init__(self, **kw):
            self.press_server = "u25-nuremberg-3.frappe.cloud"
            self.press_release_group = "bench-46919"
            self.press_cluster = "Nuremberg-3"
            self.press_version = "Nightly"
            self.capacity_tenants = 0
            self.tenant_count = 0
            self.accepts_new_tenants = 1
            self.__dict__.update(kw)

        def get(self, key, default=None):
            return getattr(self, key, default)

    return FakeShard


INVENTORY = {
    "servers": [{"name": "u25-nuremberg-3.frappe.cloud"}],
    "release_groups": [{"name": "bench-46919", "version": "Nightly"}],
    "versions": ["Nightly"],
}


def _known(shard, monkeypatch, inventory=INVENTORY):
    monkeypatch.setattr(shard, "press_inventory", lambda: inventory)


def validate(doc):
    doc.validate()


# --------------------------------------------------------------------------- #
# What it refuses
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("field,bad", [
    ("press_server", "u25-nuremberg-9.frappe.cloud"),
    ("press_release_group", "bench-46810"),
    ("press_version", "Version 15"),
])
def test_a_name_frappe_cloud_does_not_have_is_refused(shard, make, monkeypatch, field, bad):
    _known(shard, monkeypatch)
    with pytest.raises(Exception) as caught:
        validate(make(**{field: bad}))

    # The message has to carry what *is* available, or an operator is left
    # guessing at the very moment they mistyped something.
    assert bad in str(caught.value)
    assert "Nightly" in str(caught.value) or "bench-46919" in str(caught.value) \
        or "nuremberg-3" in str(caught.value)


def test_the_stale_bench_group_is_caught(shard, make, monkeypatch):
    """The specific mistake this exists for: a group that was deleted and whose
    name is still in a runbook, a note, or muscle memory."""
    _known(shard, monkeypatch)
    with pytest.raises(Exception):
        validate(make(press_release_group="bench-46810"))


def test_a_correct_shard_saves(shard, make, monkeypatch):
    _known(shard, monkeypatch)
    validate(make())


# --------------------------------------------------------------------------- #
# What it must never refuse
# --------------------------------------------------------------------------- #

def test_an_unreachable_frappe_cloud_does_not_block_a_save(shard, make, monkeypatch):
    """`None` means "could not ask", which is not "there is nothing there".

    A shard that cannot be edited because Frappe Cloud is down would make an
    incident worse at exactly the wrong moment.
    """
    monkeypatch.setattr(shard, "press_inventory", lambda: None)
    validate(make(press_server="anything at all"))


def test_an_empty_inventory_does_not_block_a_save(shard, make, monkeypatch):
    """Press answering with nothing is more likely a permissions or shape
    change than a genuinely empty account, and guessing wrong locks the form."""
    _known(shard, monkeypatch, {"servers": [], "release_groups": [], "versions": []})
    validate(make(press_server="anything at all"))


def test_a_shard_naming_nothing_yet_is_left_alone(shard, make, monkeypatch):
    _known(shard, monkeypatch)
    validate(make(press_server="", press_release_group="",
                              press_version=""))


def test_blank_fields_are_skipped_individually(shard, make, monkeypatch):
    """Half-filled while somebody is still typing is not an error."""
    _known(shard, monkeypatch)
    validate(make(press_server=""))


@pytest.mark.parametrize("flag", ["in_install", "in_migrate", "in_patch",
                                  "in_test", "in_import"])
def test_installs_and_migrations_never_reach_the_network(shard, make, stub_frappe,
                                                         monkeypatch, flag):
    """A migration that made an HTTP call per shard would be slow, and would
    fail the whole migration when Frappe Cloud was unreachable."""
    def explode():
        raise AssertionError("press must not be consulted during " + flag)

    monkeypatch.setattr(shard, "press_inventory", explode)
    setattr(stub_frappe.flags, flag, True)

    validate(make(press_server="anything at all"))


# --------------------------------------------------------------------------- #
# The cache
# --------------------------------------------------------------------------- #

def test_press_is_asked_once_per_request(shard, stub_frappe, monkeypatch):
    """Three fields, one round trip. Without this a save is three calls, and a
    bulk edit is three per row."""
    calls = []

    class Client:
        def __init__(self):
            calls.append("built")

        def servers(self):
            return [{"name": "u25-nuremberg-3.frappe.cloud"}]

        def release_groups(self):
            calls.append("groups")
            return [{"name": "bench-46919", "version": "Nightly"}]

    monkeypatch.setitem(
        __import__("sys").modules,
        "oneapp_control.press.client",
        types.SimpleNamespace(PressClient=Client),
    )

    first = shard.press_inventory()
    second = shard.press_inventory()

    assert first == second
    assert calls.count("built") == 1, calls
    assert calls.count("groups") == 1, "release_groups was fetched twice"


# --------------------------------------------------------------------------- #
# What derives, and what refuses to guess
# --------------------------------------------------------------------------- #
# A shard is one choice and a handful of decisions. The bench group determines
# the version, the server determines the cluster, and a single-server account
# determines the server — none of those is a judgement, so none should be typed.

def test_the_group_supplies_the_version(shard, make, monkeypatch):
    _known(shard, monkeypatch)
    doc = make(press_version="")
    validate(doc)
    assert doc.press_version == "Nightly"


def test_the_server_supplies_the_cluster(shard, make, monkeypatch):
    _known(shard, monkeypatch, {
        "servers": [{"name": "u25-nuremberg-3.frappe.cloud", "cluster": "Nuremberg-3"}],
        "release_groups": [{"name": "bench-46919", "version": "Nightly"}],
        "versions": ["Nightly"],
    })
    doc = make(press_cluster="")
    validate(doc)
    assert doc.press_cluster == "Nuremberg-3"


def test_a_single_server_account_does_not_have_to_name_it(shard, make, monkeypatch):
    _known(shard, monkeypatch, {
        "servers": [{"name": "u25-nuremberg-3.frappe.cloud", "cluster": "Nuremberg-3"}],
        "release_groups": [{"name": "bench-46919", "version": "Nightly"}],
        "versions": ["Nightly"],
    })
    doc = make(press_server="", press_cluster="")
    validate(doc)
    assert doc.press_server == "u25-nuremberg-3.frappe.cloud"
    assert doc.press_cluster == "Nuremberg-3"


def test_two_servers_are_a_real_choice_and_are_not_guessed(shard, make, monkeypatch):
    """Guessing here puts somebody's tenants on a machine nobody picked."""
    _known(shard, monkeypatch, {
        "servers": [{"name": "a.frappe.cloud", "cluster": "X"},
                    {"name": "b.frappe.cloud", "cluster": "Y"}],
        "release_groups": [{"name": "bench-46919", "version": "Nightly"}],
        "versions": ["Nightly"],
    })
    doc = make(press_server="", press_cluster="")
    validate(doc)
    assert doc.press_server == ""


def test_a_value_already_set_is_never_overwritten(shard, make, monkeypatch):
    """A set value is a deliberate one — a shard pinned somewhere press would
    not have chosen, or one mid-migration between groups."""
    _known(shard, monkeypatch, {
        "servers": [{"name": "u25-nuremberg-3.frappe.cloud", "cluster": "Nuremberg-3"}],
        "release_groups": [{"name": "bench-46919", "version": "Nightly"}],
        "versions": ["Nightly"],
    })
    doc = make(press_cluster="Somewhere-Else")
    validate(doc)
    assert doc.press_cluster == "Somewhere-Else"


def test_filling_does_not_excuse_a_wrong_value(shard, make, monkeypatch):
    """Filling is the convenience; refusing is the guarantee. Both run."""
    _known(shard, monkeypatch)
    with pytest.raises(Exception):
        validate(make(press_version="", press_release_group="bench-46810"))


def test_an_empty_shard_fills_itself_when_the_account_leaves_no_choice(
    shard, make, monkeypatch
):
    """This used to assert the opposite — that naming nothing asked press
    nothing — which was true and unhelpful. One server and one bench group is
    not a decision anybody has to make, so the whole Frappe Cloud half of the
    form derives from an empty start."""
    _known(shard, monkeypatch, {
        "servers": [{"name": "u25-nuremberg-3.frappe.cloud", "cluster": "Nuremberg-3"}],
        "release_groups": [{"name": "bench-46919", "version": "Nightly"}],
        "versions": ["Nightly"],
    })
    doc = make(press_server="", press_release_group="", press_cluster="",
               press_version="")
    validate(doc)

    assert (doc.press_server, doc.press_release_group,
            doc.press_cluster, doc.press_version) == (
        "u25-nuremberg-3.frappe.cloud", "bench-46919", "Nuremberg-3", "Nightly")


def test_a_single_bench_group_does_not_have_to_be_named_either(shard, make,
                                                               monkeypatch):
    """The same rule as the server. Automating one and not the other was an
    inconsistency, not a principle."""
    _known(shard, monkeypatch, {
        "servers": [{"name": "u25-nuremberg-3.frappe.cloud", "cluster": "Nuremberg-3"}],
        "release_groups": [{"name": "bench-46919", "version": "Nightly"}],
        "versions": ["Nightly"],
    })
    doc = make(press_server="", press_release_group="", press_cluster="",
               press_version="")
    validate(doc)

    assert doc.press_server == "u25-nuremberg-3.frappe.cloud"
    assert doc.press_release_group == "bench-46919"
    assert doc.press_cluster == "Nuremberg-3"
    assert doc.press_version == "Nightly"


def test_two_bench_groups_are_a_real_choice(shard, make, monkeypatch):
    _known(shard, monkeypatch, {
        "servers": [{"name": "u25-nuremberg-3.frappe.cloud", "cluster": "Nuremberg-3"}],
        "release_groups": [{"name": "bench-1", "version": "Nightly"},
                           {"name": "bench-2", "version": "Version 16"}],
        "versions": ["Nightly", "Version 16"],
    })
    doc = make(press_release_group="", press_version="")
    validate(doc)
    assert doc.press_release_group == ""
    assert doc.press_version == ""
