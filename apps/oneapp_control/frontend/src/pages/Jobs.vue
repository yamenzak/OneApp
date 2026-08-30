<template>
  <PageHeader>
    <Breadcrumbs :items="[{ label: 'Provisioning' }]" />

    <div class="flex items-center gap-2">
      <!-- An icon, not the word "Refresh": it is the only action here, and a
           word competes with the tab labels below it for the same glance. -->
      <Button
        variant="ghost"
        icon="lucide-refresh-cw"
        label="Refresh"
        tooltip="Refresh"
        :loading="panel?.loading"
        @click="panel?.reload()"
      />
    </div>
  </PageHeader>

  <div class="p-5">
    <!--
      Four screens of the same question: what is the control plane doing, and what
      did it fail to do. They are tabs rather than four sidebar entries because
      an operator checking one usually checks the next — and because the desk,
      which is where three of these used to live, is not part of this product.
    -->
    <Tabs v-model="tab">
      <TabList variant="underline">
        <TabTrigger value="jobs" label="Jobs" icon-left="lucide-activity" />
        <TabTrigger value="signups" label="Signups" icon-left="lucide-user-plus" />
        <TabTrigger value="events" label="Billing events" icon-left="lucide-credit-card" />
        <TabTrigger value="standby" label="Standby" icon-left="lucide-server" />
      </TabList>

      <TabPanel value="jobs" class="pt-5">
        <JobsPanel v-if="tab === 'jobs'" ref="jobs" />
      </TabPanel>
      <TabPanel value="signups" class="pt-5">
        <SignupsPanel v-if="tab === 'signups'" ref="signups" />
      </TabPanel>
      <TabPanel value="events" class="pt-5">
        <WebhookEventsPanel v-if="tab === 'events'" ref="events" />
      </TabPanel>
      <TabPanel value="standby" class="pt-5">
        <StandbyPanel v-if="tab === 'standby'" ref="standby" />
      </TabPanel>
    </Tabs>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'
import { PageHeader, Breadcrumbs, Button, Tabs, TabList, TabTrigger, TabPanel } from '@/ui'
import JobsPanel from '../components/ops/JobsPanel.vue'
import SignupsPanel from '../components/ops/SignupsPanel.vue'
import WebhookEventsPanel from '../components/ops/WebhookEventsPanel.vue'
import StandbyPanel from '../components/ops/StandbyPanel.vue'

const tab = ref('jobs')

// Each panel owns its own fetch, so the header's refresh has to reach whichever
// one is showing rather than owning a resource of its own.
const jobs = ref(null)
const signups = ref(null)
const events = ref(null)
const standby = ref(null)

const panel = computed(
  () => ({ jobs, signups, events, standby })[tab.value]?.value || null,
)
</script>
