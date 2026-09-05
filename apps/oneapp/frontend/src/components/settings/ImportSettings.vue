<template>
  <!--
    Bringing everything with you from the system you are leaving.

    The engine behind this is in `oneapp_core/importer.py` and it is the reason
    this panel is two buttons rather than a wizard: it is idempotent, so running
    it twice is safe, and incremental, so running it again brings only what has
    changed since. That turns a migration from an event into a habit — rehearse
    it a month out, run it whenever, run it once more the morning you switch and
    it catches the night's work.

    So the buttons are honest about which is which: **Rehearse** writes nothing
    and reports exactly what the real one would do, and the real one says "bring
    across" the first time and "bring across what has changed" every time after.
  -->
  <SettingsHeader
    title="Import"
    description="Bring your records over from the system you are leaving — as often as you like."
    :class="PANEL_HEADER"
  />
  <SettingsBody :class="PANEL_BODY">
    <LoadingText v-if="loading" class="py-8" text="Loading" />

    <EmptyState
      v-else-if="!sources.length && !plans.length && !shipped.length"
      icon="lucide-import"
      title="Nothing to import"
      description="This workspace has nothing set up to import from."
    />

    <div v-else class="flex flex-col gap-6 py-4">
      <!--
        Where it is coming from. A key and a secret the customer makes on their
        own old site — the secret goes out and never comes back: the server
        keeps it where Frappe keeps passwords, so this box is blank on every
        visit and filling it in is what changes it.
      -->
      <div v-for="one in sources" :key="one.name" class="flex flex-col gap-3">
        <div class="flex items-center gap-2">
          <span class="text-p-base font-medium text-ink-gray-8">{{ one.name }}</span>
          <StateBadge v-if="one.status" :label="one.status" />
          <span v-if="one.verified_as" class="text-p-sm text-ink-gray-5">
            as {{ one.verified_as }}
          </span>
        </div>

        <FormControl
          v-model="draft[one.name].base_url"
          type="text"
          label="Address"
          placeholder="https://old.example.com"
        />
        <div class="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <FormControl v-model="draft[one.name].api_key" type="text" label="API key" />
          <FormControl
            v-model="draft[one.name].api_secret"
            type="password"
            label="API secret"
            :description="'Kept encrypted. Leave blank to keep the one already saved.'"
          />
        </div>

        <!--
          "Save connection" and not "Save": this is one card's own action, not
          the panel's, and there can be more than one card. The pinned-footer
          rule is about a panel whose single Save scrolls out of reach — a
          button that scrolls with the thing it saves is where it belongs.
        -->
        <div class="flex items-center gap-2">
          <Button label="Save connection" :loading="saving === one.name" @click="save(one)" />
          <Button
            label="Check the connection"
            :loading="checking === one.name"
            @click="check(one)"
          />
          <span v-if="one.last_error" class="text-p-sm text-ink-red-5">{{ one.last_error }}</span>
        </div>
      </div>

      <!--
        Adding the first one. Without this the panel's first state is a dead
        end: nowhere to type an address, and a shipped plan that cannot be set
        up because it has nothing to point at.
      -->
      <div>
        <Button label="Add a connection" icon-left="plus" @click="add" />
      </div>

      <!--
        What this app ships and this workspace has not set up. Pressing it
        writes the plan and the records its maps write against — which is the
        difference between a migration somebody runs and a migration somebody
        first has to assemble. The `custom_` fields its maps name are not here:
        those belong to the space and arrive with the entitlement.
      -->
      <div
        v-for="one in shipped"
        :key="one.key"
        data-slot="import-offer"
        class="flex flex-col gap-3 rounded-6 border border-dashed border-outline-gray-2 p-4"
      >
        <div class="flex items-center gap-2">
          <span class="text-p-base font-medium text-ink-gray-8">{{ one.title }}</span>
          <span class="ms-auto text-p-sm text-ink-gray-5">
            {{ one.steps }} steps · {{ one.fields }} fields it adds
          </span>
        </div>
        <p class="text-p-sm text-ink-gray-6">
          Not set up yet. Setting it up writes the plan and the records its steps
          write against; it reads nothing and moves nothing.
        </p>
        <ErrorMessage v-if="error && installing === one.key" :message="error" />
        <div class="flex items-center gap-2">
          <Button
            data-slot="import-setup"
            label="Set this up"
            :loading="installing === one.key"
            :disabled="!into[one.key]"
            @click="setUp(one)"
          />
          <!--
            One connection is the ordinary case and picking from a list of one
            is a question with an answer already, so it is a sentence until
            there is a second.
          -->
          <span v-if="sources.length < 2" class="text-p-sm text-ink-gray-5">
            {{ into[one.key] ? `from ${into[one.key]}` : 'add a connection first' }}
          </span>
          <FormControl
            v-else
            v-model="into[one.key]"
            type="select"
            label="From"
            :options="sources.map((s) => ({ label: s.name, value: s.name }))"
          />
        </div>
      </div>

      <!--
        What will come across, and the two buttons. The step list is the plan in
        the order it runs — parties before the invoices that point at them —
        and each row says when it last saw anything, which is what makes "up to
        the last second" something you can read rather than something to trust.
      -->
      <div
        v-for="plan in plans"
        :key="plan.name"
        data-slot="import-plan"
        class="flex flex-col gap-3 rounded-6 border border-outline-gray-1 p-4"
      >
        <div class="flex items-center gap-2">
          <span class="text-p-base font-medium text-ink-gray-8">{{ plan.name }}</span>
          <StateBadge v-if="plan.carried" label="Carried across" />
          <span class="ms-auto text-p-sm text-ink-gray-5">
            {{ plan.steps.length }} steps
          </span>
        </div>

        <div class="flex flex-col divide-y divide-outline-gray-1">
          <div
            v-for="step in plan.steps"
            :key="step.source_doctype"
            class="flex items-center gap-2 py-1.5 text-p-sm"
          >
            <Icon name="lucide-arrow-right" class="size-3.5 shrink-0 text-ink-gray-4" />
            <span class="min-w-0 truncate text-ink-gray-7">{{ step.source_doctype }}</span>
            <span class="text-ink-gray-4">→</span>
            <span class="min-w-0 truncate text-ink-gray-8">{{ step.target_doctype }}</span>
            <span class="ms-auto shrink-0 text-p-xs text-ink-gray-5">
              {{ step.watermark ? `up to ${when(step.watermark)}` : 'not yet' }}
            </span>
          </div>
        </div>

        <ErrorMessage v-if="error" :message="error" />

        <div class="flex items-center gap-2">
          <!--
            Before either of the other two, and it touches nothing at all: it
            reads both schemas — the old system's over the wire, this site's
            locally — and says what the plan gets wrong. A field renamed since
            somebody wrote the map drops a column silently; a value map that
            covers four of five values lets the fifth through untouched. Those
            are found here or they are found in a report a week later.
          -->
          <Button
            data-slot="import-check"
            label="Check the plan"
            :loading="checkingPlan === plan.name"
            @click="checkPlan(plan)"
          />
          <Button
            label="Rehearse"
            :loading="starting === `${plan.name}:dry`"
            :disabled="Boolean(running)"
            tooltip="Read everything, change nothing, and say what would happen"
            @click="run(plan, true)"
          />
          <Button
            variant="solid"
            theme="green"
            data-slot="import-run"
            :label="plan.carried ? 'Bring across what has changed' : 'Bring everything across'"
            :loading="starting === `${plan.name}:live`"
            :disabled="Boolean(running)"
            @click="run(plan, false)"
          />
        </div>

        <!--
          What the check found, per step, until something else is pressed. Green
          is worth saying out loud: a plan that reads clean against both ends is
          the difference between running a migration and hoping.
        -->
        <div
          v-if="checked[plan.name]"
          data-slot="import-checked"
          class="flex flex-col gap-2 rounded-6 border border-outline-gray-1 p-3"
        >
          <div class="flex items-center gap-2 text-p-sm">
            <StateBadge :label="checked[plan.name].problems ? 'Problems' : 'Ready'" />
            <span class="text-ink-gray-6">
              {{ checked[plan.name].problems }} to fix ·
              {{ checked[plan.name].warnings }} worth reading
            </span>
          </div>
          <div
            v-for="step in checked[plan.name].steps.filter((s) => s.problems.length || s.warnings.length)"
            :key="step.source_doctype"
            class="flex flex-col gap-0.5 text-p-sm"
          >
            <span class="text-ink-gray-8">
              {{ step.source_doctype }} → {{ step.target_doctype }}
            </span>
            <span v-for="one in step.problems" :key="one" class="text-ink-red-5">{{ one }}</span>
            <span v-for="one in step.warnings" :key="one" class="text-ink-amber-5">{{ one }}</span>
          </div>
        </div>

        <!-- What is happening, or what happened last time. The same block
             either way: a finished run is a live one that stopped. -->
        <div v-if="shown(plan)" class="flex flex-col gap-2 rounded-4 bg-surface-gray-1 p-3">
          <div class="flex items-center gap-2 text-p-sm">
            <StateBadge :label="shown(plan).status" />
            <span v-if="shown(plan).dry_run" class="text-ink-gray-5">rehearsal</span>
            <span class="ms-auto tabular-nums text-ink-gray-6">
              {{ shown(plan).total_seen ?? total(shown(plan), 'seen') }} read ·
              {{ shown(plan).total_created ?? total(shown(plan), 'created') }} new ·
              {{ shown(plan).total_updated ?? total(shown(plan), 'updated') }} updated ·
              {{ shown(plan).total_failed ?? total(shown(plan), 'failed') }} refused
            </span>
          </div>
          <p v-if="shown(plan).error" class="text-p-sm text-ink-red-5">
            {{ shown(plan).error }}
          </p>
          <Button
            v-if="(shown(plan).issues || shown(plan).total_failed) && shown(plan).name !== undefined"
            label="See what was refused"
            @click="openIssues(shown(plan).name)"
          />
        </div>
      </div>
    </div>

    <!--
      Every row that would not come across, with what the old system said about
      it. Kept whole on purpose: by the time anybody reads this the source has
      moved on, and an error with no row attached is a question nobody can
      answer.
    -->
    <Dialog v-model="showingIssues" title="Rows that were refused" size="3xl">
      <div class="flex flex-col gap-3">
        <LoadingText v-if="loadingIssues" text="Loading" />
        <EmptyState
          v-else-if="!issues.length"
          icon="lucide-circle-check"
          title="Nothing was refused"
          description="Every row came across."
        />
        <div
          v-for="issue in issues"
          :key="issue.name"
          class="flex flex-col gap-1 rounded-6 border border-outline-gray-1 p-3"
        >
          <div class="flex items-center gap-2 text-p-sm">
            <span class="text-ink-gray-8">{{ issue.source_doctype }}</span>
            <span class="text-ink-gray-5">{{ issue.source_name }}</span>
          </div>
          <p class="text-p-sm text-ink-red-5">{{ issue.error }}</p>
          <pre
            class="max-h-44 overflow-auto rounded-4 bg-surface-gray-1 p-2 text-p-xs text-ink-gray-7"
          >{{ issue.payload }}</pre>
        </div>
      </div>
    </Dialog>
  </SettingsBody>
</template>

<script setup>
import { onBeforeUnmount, reactive, ref } from 'vue'
import {
  Button,
  Dialog,
  ErrorMessage,
  FormControl,
  Icon,
  LoadingText,
  SettingsBody,
  SettingsHeader,
  dayjsLocal,
} from '@/ui'
import EmptyState from '../EmptyState.vue'
import StateBadge from '../screen/fields/StateBadge.vue'
import { PANEL_BODY, PANEL_HEADER } from './geometry'
import { workspace } from '../../lib/workspace'
import { errorText } from '../../lib/errors'

const loading = ref(true)
const sources = ref([])
const plans = ref([])
const shipped = ref([])
const draft = reactive({})
// Which connection each offered plan would be set up against. A separate map
// rather than a field on the offer, because the offer is the server's answer
// and this is what somebody picked.
const into = reactive({})
const error = ref('')

const installing = ref('')
const saving = ref('')
const checking = ref('')
const starting = ref('')
const checkingPlan = ref('')
const checked = reactive({})

// The run being watched, and where its progress is kept. One at a time,
// because `start` refuses a second run of a plan already going.
const running = ref('')
const live = reactive({})
let ticking = null

const when = (value) => (value ? dayjsLocal(value).fromNow() : '')

const total = (run, key) =>
  (run?.steps || []).reduce((sum, step) => sum + (Number(step[key]) || 0), 0)

/** The live run if this plan has one, else what it did last time. */
const shown = (plan) => (live[plan.name] ? live[plan.name] : plan.last_run)

const load = async () => {
  loading.value = true
  try {
    const found = await workspace.importConsole()
    sources.value = found?.sources || []
    plans.value = found?.plans || []
    shipped.value = found?.shipped || []
    for (const one of shipped.value) {
      // The one connection there is, where there is only one: picking from a
      // list of one is a question with an answer already.
      into[one.key] = into[one.key] || sources.value[0]?.name || ''
    }
    for (const one of sources.value) {
      draft[one.name] = {
        base_url: one.base_url || '',
        api_key: one.api_key || '',
        // Never seeded. The server does not send it back and a box that looked
        // filled would be a box lying about what it holds.
        api_secret: '',
      }
    }
  } finally {
    loading.value = false
  }
}

/**
 * A blank card to fill in.
 *
 * Local until Save connection: the server names an Import Source after what
 * somebody typed, so a row cannot exist before there is a name for it.
 */
const add = () => {
  const taken = new Set(sources.value.map((one) => one.name))
  let name = 'The old system'
  for (let n = 2; taken.has(name); n += 1) name = `The old system ${n}`
  // No status: the badge says what the last check found, and nothing has
  // checked a card that has not been saved.
  draft[name] = { base_url: '', api_key: '', api_secret: '' }
  sources.value = [...sources.value, { name, status: '' }]
}

const setUp = async (one) => {
  installing.value = one.key
  error.value = ''
  try {
    await workspace.installImportPlan(one.key, into[one.key])
    await load()
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    installing.value = ''
  }
}

const save = async (one) => {
  saving.value = one.name
  error.value = ''
  try {
    const said = draft[one.name]
    await workspace.saveImportSource(one.name, said.base_url, said.api_key, said.api_secret)
    said.api_secret = ''
    await load()
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    saving.value = ''
  }
}

const check = async (one) => {
  checking.value = one.name
  error.value = ''
  try {
    await workspace.verifyImportSource(one.name)
    await load()
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    checking.value = ''
  }
}

const checkPlan = async (plan) => {
  checkingPlan.value = plan.name
  error.value = ''
  try {
    checked[plan.name] = await workspace.checkImportPlan(plan.name)
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    checkingPlan.value = ''
  }
}

const run = async (plan, dry) => {
  starting.value = `${plan.name}:${dry ? 'dry' : 'live'}`
  error.value = ''
  try {
    const name = await workspace.startImport(plan.name, dry)
    running.value = name
    live[plan.name] = { name, status: 'Queued', dry_run: dry ? 1 : 0, steps: [] }
    watch(plan.name, name)
  } catch (raised) {
    error.value = errorText(raised)
  } finally {
    starting.value = ''
  }
}

/**
 * Poll, because the job is on a worker and nothing pushes.
 *
 * A socket would be nicer and is not worth it here: an import is watched by one
 * person for a few minutes, once, and a two-second poll of one small answer is
 * cheaper than a room and a subscription that then have to be torn down
 * correctly on every path out of this panel.
 */
const watch = (planName, runName) => {
  clearInterval(ticking)
  ticking = setInterval(async () => {
    try {
      const found = await workspace.importProgress(runName)
      live[planName] = { ...found, name: runName }
      if (['Done', 'Failed', 'Cancelled'].includes(found.status)) {
        clearInterval(ticking)
        running.value = ''
        // The watermarks moved, so the step list is now saying something else.
        await load()
      }
    } catch {
      clearInterval(ticking)
      running.value = ''
    }
  }, 2000)
}

onBeforeUnmount(() => clearInterval(ticking))

const showingIssues = ref(false)
const loadingIssues = ref(false)
const issues = ref([])

const openIssues = async (runName) => {
  showingIssues.value = true
  loadingIssues.value = true
  try {
    issues.value = await workspace.importIssues(runName)
  } finally {
    loadingIssues.value = false
  }
}

load()
</script>
