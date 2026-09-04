"""Resolving a space's declared screen against this site's own metadata.

A space declares a screen as little more than a doctype and a list of fieldnames.
Everything a screen actually needs to render — what each field is called, what
type it is, what a Select offers, whether this user may create or edit — comes
from the tenant site, because that is where the doctype and the permissions
live. The control plane could not know any of it without keeping a copy that
would be wrong the first time a field changed.

Two rules make it safe to hand a customer:

  * **The manifest is the allowlist, twice over.** A screen can only be reached
    through a space the workspace is entitled to, and can only name a doctype
    that space's permission manifest already granted. So a screen is not a way to
    read something the entitlement did not include.

  * **Permission is Frappe's, not ours.** Every read and write goes through the
    ordinary DocPerms `sync_permissions` writes from that same manifest. This
    reports what the user may do so the UI can hide what it must; it does not
    decide it.

## The layers

This was one 4,000-line module. It is a package now, and the order below is the
import order: a module may use the ones above it and never the ones below, which
is what stops it becoming one module again.

    meta        what a doctype's metadata says a screen may show
    viewtypes   the ways a screen can be looked at, and what each needs
    actions     the actions a space declares for a screen
    filters     what a reader asked for, as a query the framework accepts
    saved       reading saved layouts, and picking which one applies
    views       per-view-type shaping: board columns, cards, widgets
    applied     folding a saved layout, then the live controls, onto a screen
    resolve     one screen resolved: which doctype, columns, views
    people      users as the UI needs them
    links       Link fields: searching a target, and creating into one
    records     reading and writing the records a screen is over
    guard       the one check every record-scoped endpoint makes first
    surround    a record's timeline, files, comments, likes
    mail        the correspondence about a record, and writing more
    assign      who a record is assigned to
    sharing     tags and shares
    docstate    submit, cancel, amend, workflow
    printing    print formats, reached from a record
    layouts     writing a saved view
    run         running a declared action

Everything is re-exported below, because the whitelisted paths the SPA calls are
`oneapp.oneapp_core.spaceview.rows` and always have been. That re-export is an
address, not a seam: import from the layer that owns a thing when you are inside
the package.
"""

# The modules the package shares, re-exported so a test can stub one in the one
# place every layer sees. A name imported into a submodule is a copy — patching
# `spaceview._resolve` reaches nobody — but a *module* is the same object
# everywhere, so `spaceview.frappe.db` is still the db every layer calls.
import frappe

from oneapp.oneapp_core import fieldtypes

from .meta import (
	ALWAYS,
	CHILD_COLUMNS,
	DEFAULT_TAB,
	EDITABLE_TYPES,
	HIDDEN,
	MAX_PAGE,
	MAX_WIDTH,
	META_COLUMN,
	META_FIELDS,
	MIN_WIDTH,
	PAGE,
	PAGE_SIZES,
	PINS,
	RECORD_META,
	TAGS_COLUMN,
	UNIT_WIDTH,
	_child,
	_columns,
	_default_fields,
	_default_order,
	_default_width,
	_fetch_fields,
	_filter_rows,
	_form,
	_json,
	_json_list,
	_meta_column,
	_naming,
	_number,
	_offerable,
	_placed,
	_quick_filters,
	_status_field,
	_tags_column,
	presentation,
)
from .viewtypes import (
	BUILT_VIEW_TYPES,
	DEFAULT_VIEW_TYPE,
	NEEDS_STATUS,
	NEEDS_WIDGETS,
	PLURALS,
	VIEW_TYPES,
	_has_column_field,
	_has_widgets,
	_singular,
	_view_types,
)
from .actions import ACTION_FIELDS, ACTION_SCOPES, _action, actions
from .filters import (
	MAX_DELETE,
	MAX_FILTERS,
	MAX_IN_VALUES,
	_all_filters,
	_as_query_filters,
	_asked_filter,
	_asked_filters,
	_favourite_filter,
	_filterable,
	_group_by,
	_grouped_order,
	_not_a_value,
	_page_length,
	_safe_order,
)
from .saved import (
	LAYOUT_FIELDS,
	MAX_EMOJI,
	VIEW_ICONS,
	_can_share,
	_chosen_layout,
	_default_layout,
	_hidden,
	_layouts,
	_of_type,
	_saved,
	_view_icon,
)
from .views import (
	BOARDABLE,
	CARD_VIEW_TYPES,
	MAX_CARD_FIELDS,
	SHOWCASE,
	_board,
	_boardable,
	_cards,
	_resolve_views,
	_view_settings,
	_widgets,
)
from .applied import _apply_overrides, _apply_saved
from .resolve import _granted_doctypes, _resolve, _space, visible
from .people import _ids, _people, _users, _with_people
from .links import (
	LINK_PAGE,
	_link_column,
	_link_row,
	_link_shape,
	_link_target,
	_preview_shape_fields,
	_quick_entry,
	_search,
	link_new,
	link_new_spec,
	link_options,
	link_preview,
)
from .records import (
	_child_changes,
	_link_groups,
	_total,
	_with_authors,
	_with_children,
	_with_links,
	_with_meta,
	_with_state,
	_writable,
	count,
	dashboard_data,
	record,
	remove,
	rows,
	save,
	spec,
)
from .guard import _reachable
from .surround import (
	FILE_FIELDS,
	MARKUP_TYPES,
	TIMELINE_PAGE,
	_attachable,
	_change,
	_gallery_filters,
	_names,
	_said,
	attachments,
	comment,
	remove_attachment,
	rename,
	timeline,
	toggle_follow,
	toggle_like,
)
from .mail import (
	PAGE,
	_addresses,
	_by,
	_linked,
	attach,
	correspondence,
	detach,
	screen_doctype,
	write,
)
from .assign import ASSIGNEE_PAGE, _assignable, _colleagues, assign, assignees
from .sharing import set_share, set_tag, shareable, shares, tag_options, tags, unshare
from .docstate import amend, cancel, submit, workflow_action
from .printing import print_options, print_pdf, print_preview
from .layouts import (
	_layout_doc,
	_may_write,
	_only_default,
	default_layout,
	delete_layout,
	hide_layout,
	reset_layout,
	save_layout,
	show_layouts,
	space_layouts,
)
from .run import fetched, run_action

__all__ = [
	"ACTION_FIELDS",
	"ACTION_SCOPES",
	"ALWAYS",
	"ASSIGNEE_PAGE",
	"BOARDABLE",
	"BUILT_VIEW_TYPES",
	"CARD_VIEW_TYPES",
	"CHILD_COLUMNS",
	"DEFAULT_TAB",
	"DEFAULT_VIEW_TYPE",
	"EDITABLE_TYPES",
	"FILE_FIELDS",
	"HIDDEN",
	"LAYOUT_FIELDS",
	"LINK_PAGE",
	"MARKUP_TYPES",
	"MAX_CARD_FIELDS",
	"MAX_DELETE",
	"MAX_EMOJI",
	"MAX_FILTERS",
	"MAX_IN_VALUES",
	"MAX_PAGE",
	"MAX_WIDTH",
	"META_COLUMN",
	"META_FIELDS",
	"MIN_WIDTH",
	"NEEDS_STATUS",
	"NEEDS_WIDGETS",
	"PAGE",
	"PAGE_SIZES",
	"PINS",
	"PLURALS",
	"RECORD_META",
	"SHOWCASE",
	"TAGS_COLUMN",
	"TIMELINE_PAGE",
	"UNIT_WIDTH",
	"VIEW_ICONS",
	"VIEW_TYPES",
	"_action",
	"_addresses",
	"_all_filters",
	"_apply_overrides",
	"_apply_saved",
	"_as_query_filters",
	"_asked_filter",
	"_asked_filters",
	"_assignable",
	"_attachable",
	"_board",
	"_boardable",
	"_by",
	"_can_share",
	"_cards",
	"_change",
	"_child",
	"_child_changes",
	"_chosen_layout",
	"_colleagues",
	"_columns",
	"_default_fields",
	"_default_layout",
	"_default_order",
	"_default_width",
	"_favourite_filter",
	"_fetch_fields",
	"_filter_rows",
	"_filterable",
	"_form",
	"_gallery_filters",
	"_granted_doctypes",
	"_group_by",
	"_grouped_order",
	"_has_column_field",
	"_has_widgets",
	"_hidden",
	"_ids",
	"_json",
	"_json_list",
	"_layout_doc",
	"_layouts",
	"_link_column",
	"_link_groups",
	"_link_row",
	"_link_shape",
	"_link_target",
	"_linked",
	"_may_write",
	"_meta_column",
	"_names",
	"_naming",
	"_not_a_value",
	"_number",
	"_of_type",
	"_offerable",
	"_only_default",
	"_page_length",
	"_people",
	"_placed",
	"_preview_shape_fields",
	"_quick_entry",
	"_quick_filters",
	"_reachable",
	"_resolve",
	"_resolve_views",
	"_safe_order",
	"_said",
	"_saved",
	"_search",
	"_singular",
	"_space",
	"_status_field",
	"_tags_column",
	"_total",
	"_users",
	"_view_icon",
	"_view_settings",
	"_view_types",
	"_widgets",
	"_with_authors",
	"_with_children",
	"_with_links",
	"_with_meta",
	"_with_people",
	"_with_state",
	"_writable",
	"actions",
	"amend",
	"assign",
	"assignees",
	"attach",
	"attachments",
	"cancel",
	"comment",
	"correspondence",
	"count",
	"dashboard_data",
	"default_layout",
	"delete_layout",
	"detach",
	"fetched",
	"hide_layout",
	"link_new",
	"link_new_spec",
	"link_options",
	"link_preview",
	"presentation",
	"print_options",
	"print_pdf",
	"print_preview",
	"record",
	"remove",
	"remove_attachment",
	"rename",
	"reset_layout",
	"rows",
	"run_action",
	"save",
	"save_layout",
	"screen_doctype",
	"set_share",
	"set_tag",
	"shareable",
	"shares",
	"show_layouts",
	"space_layouts",
	"spec",
	"submit",
	"tag_options",
	"tags",
	"timeline",
	"toggle_follow",
	"toggle_like",
	"unshare",
	"visible",
	"workflow_action",
	"write",
]
