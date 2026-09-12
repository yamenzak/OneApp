"""What a date, a time, a number and an amount of money read as.

One module answers all four — `lib/runtime/format.js` — and these run it,
rather than a Python restatement of it. The point of the section it came from
is that the answers follow *the workspace's* settings and not the reader's
browser, so every test here says what the workspace set and reads back what a
column then says. `docs/UNIFICATION.md` §D1.
"""

import json

from spa_js import call, needs_node

pytestmark = needs_node

FORMAT = "@/shared/lib/runtime/format"

#: Germany: day first, dots for thousands, comma for the decimal.
GERMAN = {"date_format": "dd.mm.yyyy", "time_format": "HH:mm",
          "number_format": "#.###,##", "float_precision": 2}
#: What a fresh site has.
PLAIN = {"date_format": "yyyy-mm-dd", "time_format": "HH:mm:ss",
         "number_format": "#,###.##", "float_precision": 3}


def ask(expressions, **kwargs):
	body = "console.log(JSON.stringify([%s]))" % ", ".join(expressions)
	return call(FORMAT, body, **kwargs)


def test_a_workspace_that_writes_dates_its_own_way_gets_them():
	"""The whole finding in one assertion: the setting existed, wrote through
	to System Settings, and was read by nothing."""
	assert ask(['m.date("2026-09-12")'], formats=PLAIN) == ["2026-09-12"]
	assert ask(['m.date("2026-09-12")'], formats=GERMAN) == ["12.09.2026"]


def test_a_workspace_that_writes_numbers_its_own_way_gets_them():
	assert ask(['m.number(1234.5, 2)'], formats=PLAIN) == ["1,234.50"]
	assert ask(['m.number(1234.5, 2)'], formats=GERMAN) == ["1.234,50"]


def test_the_separators_do_not_follow_the_reader():
	"""`toLocaleString(undefined, …)` follows the *browser's* language, so two
	colleagues reading the same invoice saw different separators and neither
	could tell. Same workspace, two readers, one answer."""
	one = ask(['m.number(1234.5, 2)'], formats=GERMAN, local_tz="Europe/Berlin")
	two = ask(['m.number(1234.5, 2)'], formats=GERMAN, local_tz="America/New_York")
	assert one == two == ["1.234,50"]


def test_a_stored_datetime_is_converted_from_the_site_s_timezone():
	"""Frappe writes a wall clock in the site's zone. A version saved at 09:00
	in Dubai is 05:00 in London, and reading the string as local says 09:00."""
	assert ask(['m.moment("2026-09-12 09:00:00")'], formats=PLAIN,
	           system_tz="Asia/Dubai", local_tz="Europe/London") == ["2026-09-12 06:00:00"]
	assert ask(['m.moment("2026-09-12 09:00:00")'], formats=PLAIN,
	           system_tz="Asia/Dubai", local_tz="Asia/Dubai") == ["2026-09-12 09:00:00"]


def test_an_instant_is_not_converted():
	"""A `Date.now()` from this browser is an absolute moment with no zone to
	convert *from*. Running it through the site-zone conversion would say a
	reply posted a second ago arrived four hours ago."""
	assert ask(['m.ago(Date.now() - 5000)'], formats=PLAIN,
	           system_tz="Asia/Dubai", local_tz="Europe/London") == ["a few seconds ago"]


def test_relative_under_a_week_and_a_date_over_it():
	"""One rule, so the same column is not relative on one surface and
	absolute on another."""
	answers = ask([
		'm.ago(new Date(Date.now() - 2 * 86400000))',
		'm.ago(new Date(Date.now() - 30 * 86400000))',
		'm.RELATIVE_DAYS',
	], formats=PLAIN)
	assert answers[0] == "2 days ago"
	assert answers[1].count("-") == 2, f"older than a week should be a date: {answers[1]}"
	assert answers[2] == 7


def test_bare_drops_the_suffix():
	assert ask(['m.ago(new Date(Date.now() - 2 * 86400000), true)'],
	           formats=PLAIN) == ["2 days"]


def test_money_takes_the_currency_s_own_precision():
	"""JPY has no minor unit and KWD has three. The symbol and the decimal
	count were deliberately separated, which left the second to every caller —
	so nobody did it."""
	assert ask([
		'm.money(1234.5, "USD")',
		'm.money(1234.5, "JPY")',
		'm.money(1234.5, "KWD")',
	], formats=PLAIN) == ["$ 1,234.50", "¥ 1,235", "KWD 1,234.500"]


def test_money_falls_back_to_the_workspace_s_currency():
	formats = dict(PLAIN, currency="EUR")
	assert ask(['m.money(10)'], formats=formats) == ["€ 10.00"]


def test_a_currency_nobody_has_heard_of_still_renders():
	"""A workspace's own unit, a ticker. `Intl` throws on an unknown code, and
	a thrown formatter is a blank cell."""
	assert ask(['m.money(1234.5, "ZZZ")'], formats=dict(PLAIN, currency_precision=2)) \
		== ["ZZZ 1,234.50"]


def test_the_indian_grouping_is_lakhs():
	"""`#,##,###.##` is one of the formats Frappe ships, and grouping it in
	threes is wrong for every workspace that picks it."""
	indian = dict(PLAIN, number_format="#,##,###.##")
	assert ask(['m.number(1234567, 2)'], formats=indian) == ["12,34,567.00"]
	assert ask(['m.number(1234567, 2)'], formats=PLAIN) == ["1,234,567.00"]


def test_a_format_nobody_could_have_chosen_still_answers():
	"""A string outside the Select's options — a hand-edited System Settings
	row — falls back rather than rendering nothing."""
	assert ask(['m.number(1234.5, 2)'], formats=dict(PLAIN, number_format="??")) \
		== ["1,234.50"]


def test_nothing_renders_as_nothing():
	"""Emptiness is the caller's to draw: a column that says `0.00` where
	there is no value is a number somebody plans around."""
	assert ask([
		'm.date("")', 'm.date(null)', 'm.number(null)', 'm.money("")', 'm.ago(undefined)',
	], formats=PLAIN) == ["", "", "", "", ""]


def test_a_negative_keeps_its_sign_outside_the_grouping():
	assert ask(['m.number(-1234.5, 2)'], formats=GERMAN) == ["-1.234,50"]


def test_the_list_s_own_formatter_writes_them_the_same_way():
	"""`screen/format.js` decides how many decimals a column wants — a
	question about a docfield — and hands the writing to this module. Both
	halves, through the real code."""
	body = (
		'const site = {float_precision: 3, currency_precision: 2};'
		'console.log(JSON.stringify(['
		'  m.formatNumber(1234.5678, {cell: "number"}, site),'
		'  m.formatNumber(1234.5678, {cell: "currency"}, site),'
		'  m.formatNumber(1234, {fieldtype: "Int"}, site),'
		']))'
	)
	assert call("@/modules/onespace/lib/screen/format", body, formats=GERMAN) == [
		"1.234,568", "1.234,57", "1.234",
	]


def test_the_stub_matches_the_library():
	"""`tests/js/hooks.mjs` stands in for `@/ui`, and a stub that has drifted
	from what it stands for is a test passing about the wrong thing.

	`dayjsLocal` is the one piece of behaviour it reimplements, so its shape
	is compared against frappe-ui's own source.
	"""
	from pathlib import Path

	ROOT = Path(__file__).resolve().parent.parent
	library = (ROOT / "apps/oneapp/frontend/node_modules/frappe-ui/src/utils/dayjs.ts").read_text()
	assert "_dayjs.tz(dateTimeString, systemTimezone).tz(localTimezone)" in library, (
		"frappe-ui's dayjsLocal changed shape — tests/js/hooks.mjs is now a "
		"different function from the one that ships"
	)
	stub = (ROOT / "tests/js/hooks.mjs").read_text()
	assert "_dayjs.tz(value," in stub and ".tz(" in stub
