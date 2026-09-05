<!--
  Take a photograph, and hand it back as a file.

  A file manager on a phone that cannot use the camera is a file manager that
  makes people photograph a delivery note, find it in their gallery, and upload
  it — three steps for what is one. Frappe's desk has had this for years
  (`frappe/public/js/frappe/ui/capture.js`) and every surface we built to
  replace the desk quietly did not.

  Two ways to reach a camera and this uses both, in this order:

  * **`getUserMedia`**, which gives a live preview inside the dialog, a shutter,
    a retake, and a front/back toggle. It needs a secure context — HTTPS or
    localhost — and permission.
  * **A `capture` input**, which hands the whole thing to the phone's own camera
    app. Worse in that the person leaves the page, better in that it has focus,
    flash and every other thing a native camera has. It is the fallback rather
    than the default because leaving the page is a real cost, and it is a
    fallback rather than nothing because `getUserMedia` fails for four ordinary
    reasons and "the camera does not work" is not an acceptable answer to any
    of them.

  What comes out is a `File`, a JPEG, named for the moment it was taken. The
  caller uploads it like any other — this component knows nothing about where a
  photograph goes.
-->
<template>
  <div class="flex min-h-96 flex-col items-center justify-center gap-4 py-4">
    <!-- The live view. Kept in the DOM while streaming so the element the
         stream is attached to is not torn down under it. -->
    <div
      v-show="streaming && !shot"
      class="relative w-full overflow-hidden rounded-6 bg-surface-gray-7"
    >
      <video
        ref="preview"
        data-slot="camera-preview"
        class="max-h-96 w-full object-contain"
        autoplay
        playsinline
        muted
      ></video>
    </div>

    <!-- What was taken, before it is kept. A photograph nobody looked at
         before it was filed is how a workspace fills with pictures of the
         inside of a pocket. -->
    <img
      v-if="shot"
      :src="shot.url"
      data-slot="camera-shot"
      alt="The photograph just taken"
      class="max-h-96 rounded-6"
    >

    <div
      v-if="!streaming && !shot"
      class="flex flex-col items-center gap-3 rounded-6 border border-dashed border-outline-gray-2 px-6 py-12 text-center"
    >
      <Icon name="lucide-camera" class="size-8 text-ink-gray-4" />
      <p class="text-p-sm text-ink-gray-6">
        {{ refused || 'Use the camera to take a photograph.' }}
      </p>
      <div class="flex flex-wrap justify-center gap-2">
        <Button
          v-if="!refused"
          variant="solid"
          label="Turn the camera on"
          :loading="starting"
          @click="start"
        />
        <!-- The phone's own camera app. Always offered, because it is the only
             thing that works when the page is not on a secure origin. -->
        <!-- eslint-disable-next-line vue/no-restricted-html-elements -->
        <input
          ref="native"
          name="camera-native"
          type="file"
          accept="image/*"
          capture="environment"
          class="hidden"
          @change="fromNative"
        >
        <Button label="Use the phone's camera" @click="native?.click()" />
      </div>
    </div>

    <div v-if="streaming || shot" class="flex flex-wrap justify-center gap-2">
      <template v-if="shot">
        <Button variant="solid" label="Use this photo" @click="keep" />
        <Button label="Take another" @click="again" />
      </template>
      <template v-else>
        <Button variant="solid" icon-left="lucide-circle" label="Take photo" @click="snap" />
        <Button
          v-if="cameras > 1"
          icon="lucide-switch-camera"
          tooltip="Switch camera"
          @click="flip"
        />
        <Button label="Stop the camera" @click="stop" />
      </template>
    </div>

    <ErrorMessage :message="error" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { Button, ErrorMessage, Icon } from '@/ui'

const props = defineProps({
  /** Whether the camera tab is the one being looked at. */
  active: { type: Boolean, default: false },
})

const emit = defineEmits(['taken'])

const preview = ref(null)
const native = ref(null)
const streaming = ref(false)
const starting = ref(false)
const error = ref('')
const refused = ref('')
const cameras = ref(0)
const facing = ref('environment')
/** `{ file, url }` — the object URL is revoked when it stops being shown. */
const shot = ref(null)

let stream = null

/**
 * Why the camera could not be opened, in words somebody can act on.
 *
 * `getUserMedia` reports four failures that mean four different things, and
 * "Could not start video source" — which is what the browser's own message
 * says when another tab already holds the camera — sends people to look for a
 * driver problem that is not there.
 */
function reason(raised) {
  if (!navigator.mediaDevices?.getUserMedia) {
    return window.isSecureContext
      ? 'This browser has no camera support.'
      : 'A camera needs a secure connection. Use the phone’s camera instead.'
  }
  const name = raised?.name || ''
  if (name === 'NotAllowedError') return 'Permission for the camera was refused.'
  if (name === 'NotFoundError') return 'No camera was found on this device.'
  if (name === 'NotReadableError') return 'Something else is already using the camera.'
  return raised?.message || 'The camera could not be opened.'
}

async function start() {
  if (streaming.value) return
  error.value = ''
  refused.value = ''
  starting.value = true
  try {
    if (!navigator.mediaDevices?.getUserMedia) throw new Error('unsupported')
    stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: facing.value },
    })
    streaming.value = true
    // After the flag, so the element is no longer `v-show`-hidden — a video
    // attached while its container is display:none reports a zero-sized frame,
    // and the photograph comes out as a 0×0 canvas.
    await Promise.resolve()
    if (preview.value) preview.value.srcObject = stream

    // Only worth asking once the stream exists: before permission is granted,
    // `enumerateDevices` returns entries with no labels and, on some browsers,
    // one entry whatever the hardware. The toggle appears when there is
    // genuinely something to toggle to.
    try {
      const devices = await navigator.mediaDevices.enumerateDevices()
      cameras.value = devices.filter((one) => one.kind === 'videoinput').length
    } catch {
      cameras.value = 0
    }
  } catch (raised) {
    refused.value = reason(raised)
    streaming.value = false
  } finally {
    starting.value = false
  }
}

function stop() {
  // Every track, not the stream: a stream whose tracks are still live keeps the
  // camera's indicator light on after the dialog has closed, which is alarming
  // and is also true — it is still recording.
  stream?.getTracks?.().forEach((track) => track.stop())
  stream = null
  streaming.value = false
  if (preview.value) preview.value.srcObject = null
}

async function flip() {
  facing.value = facing.value === 'environment' ? 'user' : 'environment'
  stop()
  await start()
}

function snap() {
  const video = preview.value
  if (!video?.videoWidth) {
    error.value = 'The camera is not ready yet.'
    return
  }

  const canvas = document.createElement('canvas')
  canvas.width = video.videoWidth
  canvas.height = video.videoHeight
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height)

  // JPEG rather than PNG, and it matters: a 12-megapixel photograph is about
  // 700 KB as a JPEG and eleven megabytes as a PNG, and nothing about a
  // photograph benefits from being lossless.
  canvas.toBlob(
    (blob) => {
      if (!blob) {
        error.value = 'The photograph could not be saved.'
        return
      }
      release()
      shot.value = { file: named(blob), url: URL.createObjectURL(blob) }
      stop()
    },
    'image/jpeg',
    0.92,
  )
}

/** A name with the moment in it, because "image.jpg" ×40 is not a file list. */
function named(blob) {
  const now = new Date()
  const pad = (value) => String(value).padStart(2, '0')
  const stamp =
    `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}` +
    ` ${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  return new File([blob], `Photo ${stamp}.jpg`, { type: 'image/jpeg' })
}

function fromNative(event) {
  const file = event.target?.files?.[0]
  if (!file) return
  release()
  shot.value = { file, url: URL.createObjectURL(file) }
  // So choosing the same photograph twice in a row still fires `change`.
  if (native.value) native.value.value = ''
}

function release() {
  if (shot.value?.url) URL.revokeObjectURL(shot.value.url)
  shot.value = null
}

function again() {
  release()
  start()
}

function keep() {
  const file = shot.value?.file
  if (!file) return
  emit('taken', file)
  release()
}

// The camera is only ever on while its own tab is in front. Leaving it running
// behind another tab is a light on somebody's laptop for a dialog they are not
// looking at.
watch(
  () => props.active,
  (showing) => {
    if (!showing) {
      stop()
      release()
    }
  },
)

onBeforeUnmount(() => {
  stop()
  release()
})
</script>
