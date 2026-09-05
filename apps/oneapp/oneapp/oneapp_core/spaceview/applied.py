"""Folding a saved layout, then the live controls, onto a resolved screen."""

import frappe
from .meta import PAGE, _fetch_fields, _placed
from .filters import _asked_filters, _filterable, _group_by, _page_length, _safe_order
from .saved import _can_share, _chosen_layout, _default_layout, _layouts
from .views import _resolve_views, _view_settings


def _apply_saved(resolved: dict, layout: str | None = None) -> dict:
	"""Fold a layout's saved answers into a resolved screen."""
	saved = None
	resolved["layouts"] = []
	resolved["can_share"] = False
	resolved["hidden"] = 0
	if resolved.get("screen"):
		# Asked for with the hidden ones in, then split here: the count of what
		# somebody turned off comes from the same pair of queries rather than
		# from a second pair.
		offered = _layouts(resolved["space"], resolved["screen"],
		                   resolved.get("view_type"), include_hidden=True)
		rows = [row for row in offered if not row.get("hidden")]
		resolved["hidden"] = len(offered) - len(rows)
		# `opens` rather than `is_default`: two rows can both be marked — one
		# personal, one shared — and only one of them actually opens the screen.
		# A menu that pins both is telling the reader something untrue.
		opens = _default_layout(rows)
		resolved["layouts"] = [
			{"name": row["name"], "label": row["label"] or "",
			 "icon": row.get("icon") or "", "shared": row["shared"],
			 "mine": row["mine"], "is_default": bool(row["is_default"]),
			 "view_type": row["view_type"],
			 "opens": bool(opens and opens["name"] == row["name"])}
			for row in rows
		]
		resolved["can_share"] = _can_share()
		saved = _chosen_layout(rows, layout)
	resolved["layout"] = saved["name"] if saved else ""
	resolved["layout_label"] = (saved.get("label") or "") if saved else ""
	resolved["layout_icon"] = (saved.get("icon") or "") if saved else ""
	resolved["saved"] = None
	# Always present, so nothing downstream has to ask whether a saved view
	# exists before reading it.
	resolved["asked"] = []
	resolved["favourites"] = False
	resolved["group_by"] = ""
	if not saved or not resolved.get("doctype"):
		return resolved
	kept_settings: dict = {}

	offered = {c["fieldname"]: c for c in resolved.get("all_columns") or resolved["columns"]}
	# Intersected, not substituted: a saved column list that names something the
	# screen no longer offers quietly drops it rather than reintroducing it.
	kept = _placed(offered, saved.get("columns"))
	if kept:
		resolved["columns"] = kept
		resolved["fields"] = _fetch_fields(kept)

	# Bounded again on the way out, not only when it was saved: the row is a
	# doctype an operator can write, and a filter that reached the table another
	# way is still a filter this screen never offered.
	resolved["asked"] = _asked_filters(_filterable(resolved), saved.get("filters"))

	if saved.get("order_by"):
		resolved["order_by"] = _safe_order(resolved, saved["order_by"])

	resolved["favourites"] = bool(saved.get("favourites"))
	resolved["group_by"] = _group_by(resolved, saved.get("group_by"))

	# The reader's own answer to "columns of what, and what does a card say".
	#
	# Stored by `save_layout` since saved views shipped and read by nothing
	# until now, which is why a board only ever drew the status field. Merged
	# over the screen's rather than replacing it: a view that names a column
	# field and no card fields should keep the manifest's card.
	kept_settings = _view_settings(resolved, saved.get("view_settings"))
	if kept_settings:
		merged = {**(resolved.get("view_settings") or {})}
		for view_type, settings in kept_settings.items():
			merged[view_type] = {**(merged.get(view_type) or {}), **settings}
		resolved["view_settings"] = merged
		_resolve_views(resolved)
	resolved["page_length"] = (
		_page_length(saved.get("page_length")) or resolved.get("page_length") or PAGE
	)

	resolved["saved"] = {
		"filters": resolved["asked"],
		"favourites": resolved["favourites"],
		"group_by": resolved["group_by"],
		"view_settings": kept_settings,
		"order_by": saved.get("order_by") or "",
		"columns": [
			{"fieldname": c["fieldname"], "width": c["width"], "pin": c["pin"],
			 "align": c.get("align") or ""}
			for c in kept
		],
		"page_length": saved.get("page_length") or 0,
	}
	return resolved


def _apply_overrides(resolved: dict, overrides) -> dict:
	"""Fold in what the controls are currently asking for."""
	if isinstance(overrides, str):
		overrides = frappe.parse_json(overrides or "null")
	if not overrides or not resolved.get("doctype"):
		return resolved

	offered = {c["fieldname"]: c for c in resolved.get("all_columns") or resolved["columns"]}

	chosen = _placed(offered, overrides.get("columns"))
	if chosen:
		resolved["columns"] = chosen
		resolved["fields"] = _fetch_fields(chosen)

	# Set whenever the payload mentions filters at all, empty list included:
	# clearing the filters in the controls has to clear them in the list, and a
	# truthiness check would leave the saved ones standing.
	if "filters" in overrides:
		resolved["asked"] = _asked_filters(_filterable(resolved), overrides.get("filters"))

	if "favourites" in overrides:
		resolved["favourites"] = bool(overrides.get("favourites"))

	if "group_by" in overrides:
		resolved["group_by"] = _group_by(resolved, overrides.get("group_by"))

	# A board's field changed and not yet saved, through the same door a filter
	# uses — narrowing only, and re-checked here rather than trusted because it
	# was checked when it was saved.
	if "view_settings" in overrides:
		asked = _view_settings(resolved, overrides.get("view_settings"))
		merged = {**(resolved.get("view_settings") or {})}
		for view_type, settings in asked.items():
			merged[view_type] = {**(merged.get(view_type) or {}), **settings}
		resolved["view_settings"] = merged
		_resolve_views(resolved)

	if overrides.get("order_by"):
		resolved["order_by"] = _safe_order(resolved, overrides["order_by"])

	return resolved
