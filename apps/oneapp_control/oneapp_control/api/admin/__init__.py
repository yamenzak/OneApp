"""Everything the operator console can do, as whitelisted endpoints.

One 1,500-line module answering sixty-nine calls, split by subject. The layers,
in import order — a module may use the ones above it, never below:

    guard       the manager check every endpoint makes first
    press       Frappe Cloud, and degrading rather than failing when it is down
    tenants     creating a workspace, suspending it, entitlements
    fleet       shards and benches
    sites       one tenant's site: jobs, backups, domains, support login
    billing     what a tenant owes and was granted
    ai          models, features, spend
    screens     which screens a space offers
    lifecycle   the dunning ladder, cold storage, and the clock

Only `guard` and `press` are shared; the subject modules do not reach across to
each other, which is what makes them separable at all.
"""

# Shared so a test can stub it in the one place every module sees.
import frappe

from .guard import _require_manager
from .press import _degrade, _press, _site_of, _site_plans
from .tenants import (
	add_custom_domain,
	check_slug,
	create_tenant,
	grant_app,
	provision,
	resume,
	revoke_app,
	signups,
	standby_pool,
	suspend,
	tenant_app_access,
	tenant_apps,
)
from .fleet import (
	SHARD_EDITABLE,
	TENANTS_PER_GB_DISK,
	TENANTS_PER_GB_RAM,
	bench_apps,
	bench_environment,
	create_shard,
	press_capacity,
	recommended_capacity,
	shard,
	shards,
	update_shard,
)
from .sites import (
	backup_download,
	remove_domain,
	set_primary_domain,
	site_backups,
	site_domains,
	site_jobs,
	site_state,
	support_login,
	support_logins,
	take_backup,
)
from .billing import (
	_credit_summary,
	adopt_plan_terms,
	grant_credits,
	replay_webhook,
	set_tenant_plan,
	tenant_billing,
	webhook_events,
)
from .ai import (
	AI_FEATURE_EDITABLE,
	AI_MODEL_EDITABLE,
	_tally,
	ai_features,
	ai_models,
	ai_settings,
	ai_usage,
	reconcile_ai_usage,
	set_ai_markup,
	sync_ai_models,
	update_ai_feature,
	update_ai_model,
)
from .screens import APP_VIEW_FIELDS, app_views, set_app_views
from .lifecycle import (
	LIFECYCLE_DATES,
	advance_lifecycle_clock,
	hold_lifecycle,
	purge_tenant,
	release_lifecycle,
	restore_from_cold,
	run_lifecycle,
	take_cold_copy,
	tenant_lifecycle,
)

__all__ = [
	"AI_FEATURE_EDITABLE",
	"AI_MODEL_EDITABLE",
	"APP_VIEW_FIELDS",
	"LIFECYCLE_DATES",
	"SHARD_EDITABLE",
	"TENANTS_PER_GB_DISK",
	"TENANTS_PER_GB_RAM",
	"_credit_summary",
	"_degrade",
	"_press",
	"_require_manager",
	"_site_of",
	"_site_plans",
	"_tally",
	"add_custom_domain",
	"adopt_plan_terms",
	"advance_lifecycle_clock",
	"ai_features",
	"ai_models",
	"ai_settings",
	"ai_usage",
	"app_views",
	"backup_download",
	"bench_apps",
	"bench_environment",
	"check_slug",
	"create_shard",
	"create_tenant",
	"grant_app",
	"grant_credits",
	"hold_lifecycle",
	"press_capacity",
	"provision",
	"purge_tenant",
	"recommended_capacity",
	"reconcile_ai_usage",
	"release_lifecycle",
	"remove_domain",
	"replay_webhook",
	"restore_from_cold",
	"resume",
	"revoke_app",
	"run_lifecycle",
	"set_ai_markup",
	"set_app_views",
	"set_primary_domain",
	"set_tenant_plan",
	"shard",
	"shards",
	"signups",
	"site_backups",
	"site_domains",
	"site_jobs",
	"site_state",
	"standby_pool",
	"support_login",
	"support_logins",
	"suspend",
	"sync_ai_models",
	"take_backup",
	"take_cold_copy",
	"tenant_app_access",
	"tenant_apps",
	"tenant_billing",
	"tenant_lifecycle",
	"update_ai_feature",
	"update_ai_model",
	"update_shard",
	"webhook_events",
]
