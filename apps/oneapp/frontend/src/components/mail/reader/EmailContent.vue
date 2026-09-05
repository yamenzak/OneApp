<!--
  Copyright (c) Frappe Technologies Pvt. Ltd. and contributors.
  Vendored from frappe/mail (0690fd5), frontend/src/components/EmailContent.vue,
  which is AGPL-3.0. OneSpace is AGPL-3.0 too and this file stays that way — see
  components/mail/reader/VENDORED.md before editing or moving it.

  Modified: TypeScript to JavaScript, `__()` removed, `useTheme` replaced with a
  local resolve of the app's own `data-theme`, and Button/Icon taken from `@/ui`.
  All four are listed in VENDORED.md with the reason.
-->
<template>
	<div
		v-if="showImagesBanner"
		class="text-ink-gray-6 mb-3 flex items-center gap-3 rounded border p-2.5 px-4"
	>
		<Icon name="lucide-image-off" class="size-4 shrink-0 text-ink-gray-5" />
		<span class="text-ink-gray-8 min-w-0 flex-1"> {{ blockedLabel }} </span>
		<Button
			v-if="canTrust"
			variant="ghost"
			label="Mark sender as trusted"
			@click="handleTrust"
		/>
		<Button label="Show images" class="w-28" @click="imagesLoaded = true" />
	</div>
	<div v-if="!isIframeReady" class="animate-pulse space-y-2 py-4">
		<div
			v-for="i in 5"
			:key="i"
			class="bg-surface-gray-3 h-2"
			:style="{ width: `${Math.floor(Math.random() * 40) + 60}%` }"
		/>
	</div>
	<IframeResizer
		v-show="isIframeReady"
		class="w-full"
		license="GPLv3"
		:scrolling="true"
		:srcdoc
		@on-ready="isIframeReady = true"
	/>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import iframeResizerChildScript from '@iframe-resizer/child/index.umd.js?raw'
// eslint-disable-next-line import/no-unresolved
import IframeResizer from '@iframe-resizer/vue/sfc'
import DOMPurify from 'dompurify'
import { Button, Icon } from '@/ui'

import { analyzeRemoteAssets, blockRemoteAssets } from './assets'

const { content, blockImages, canTrust } = defineProps({
	/** The message body, as it was received. Sanitised here, not before. */
	content: { type: String, default: '' },
	/** Hold remote images until the reader asks for them. */
	blockImages: { type: Boolean, default: false },
	/**
	 * Whether to offer "trust this sender". Off by default: their Screener
	 * decides who is trusted and we have no such model yet. See VENDORED.md.
	 */
	canTrust: { type: Boolean, default: false },
})
const emit = defineEmits(['trust'])

/**
 * The resolved theme — `light` or `dark`, never `system`.
 *
 * The app stamps `data-theme` on `<html>` only when somebody has chosen one;
 * the default follows the OS, so that is where the fallback looks. Same
 * contract the rest of our CSS follows.
 */
const dataTheme = ref(resolveTheme())
let watching = null
let scheme = null
let onScheme = null

function resolveTheme() {
	const stamped = document.documentElement.getAttribute('data-theme')
	if (stamped === 'light' || stamped === 'dark') return stamped
	return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

const isIframeReady = ref(false)

// Remote images are withheld until the reader opts in (per message), so a sender can't use them to track
// when their mail was opened.
const imagesLoaded = ref(false)
// Trusting dismisses the banner instantly (and reveals images) without waiting for the sender's accept to
// round-trip — otherwise the bar lingers before it disappears.
const trusted = ref(false)
const effectiveBlock = computed(() => blockImages && !imagesLoaded.value && !trusted.value)
const remoteAssets = computed(() => analyzeRemoteAssets(content))
// The banner is dismissed once the reader loads the images (or trusts the sender) — there's nothing
// left to act on after that.
const showImagesBanner = computed(
	() => blockImages && !imagesLoaded.value && !trusted.value && remoteAssets.value.hasRemote,
)
const blockedLabel = computed(() => {
	const n = remoteAssets.value.images
	if (n === 0) return 'Remote content hidden to protect your privacy.'
	return n === 1
		? '1 remote image hidden to protect your privacy.'
		: `${n} remote images hidden to protect your privacy.`
})

// Trusting reveals images and dismisses the banner now; the parent accepts the sender for future mail.
const handleTrust = () => {
	trusted.value = true
	emit('trust')
}

// Listen for keyboard events from iframe
const handleMessage = (event) => {
	if (event.data?.type !== 'keyboard') return

	// Create a synthetic keyboard event in the parent
	const keyboardEvent = new KeyboardEvent(event.data.eventType, {
		key: event.data.key,
		ctrlKey: event.data.ctrlKey,
		shiftKey: event.data.shiftKey,
		altKey: event.data.altKey,
		metaKey: event.data.metaKey,
		bubbles: true,
	})
	document.dispatchEvent(keyboardEvent)
}

onMounted(() => {
	window.addEventListener('message', handleMessage)
	// Both halves of the contract: the attribute when somebody chose a theme,
	// the media query when they left it on System.
	watching = new MutationObserver(() => { dataTheme.value = resolveTheme() })
	watching.observe(document.documentElement, { attributeFilter: ['data-theme'] })
	scheme = window.matchMedia?.('(prefers-color-scheme: dark)')
	onScheme = () => { dataTheme.value = resolveTheme() }
	scheme?.addEventListener('change', onScheme)
})

onUnmounted(() => {
	window.removeEventListener('message', handleMessage)
	watching?.disconnect()
	scheme?.removeEventListener('change', onScheme)
})

// Collapse each top-level quoted reply (gmail_quote / frappe_mail_quote) behind a "···" toggle. Done on
// the DOM, not regex: a quote with nested divs is wrapped as one unit, instead of the old regex stopping
// at the first </div> and collapsing the wrong region.
const collapseQuotes = (html) => {
	const doc = new DOMParser().parseFromString(html, 'text/html')
	doc.querySelectorAll('.gmail_quote, .frappe_mail_quote').forEach((quote) => {
		// Only the outermost quote gets a toggle — hiding it hides any quotes nested inside.
		if (quote.parentElement?.closest('.gmail_quote, .frappe_mail_quote')) return
		quote.classList.add('quote-hidden')
		const button = doc.createElement('button')
		button.textContent = '···'
		button.setAttribute(
			'style',
			`background:${colors.value.button};color:${colors.value.text};padding:0.5px 6px;border-radius:8px;cursor:pointer;transition:background .2s;margin:12px 0;`,
		)
		button.setAttribute('onmouseover', `this.style.background='${colors.value.buttonHover}'`)
		button.setAttribute('onmouseout', `this.style.background='${colors.value.button}'`)
		button.setAttribute('onclick', "this.nextElementSibling.classList.toggle('quote-hidden');")
		quote.parentNode?.insertBefore(button, quote)
	})
	return doc.documentElement.outerHTML
}

const srcdoc = computed(() => {
	let sanitized = DOMPurify.sanitize(content, DOMPURIFY_CONFIG)
	if (effectiveBlock.value) sanitized = blockRemoteAssets(sanitized)
	const transformedContent = collapseQuotes(sanitized).replace(
		/<([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})>/g,
		'<b>&lt;$1&gt;</b>',
	)

	/* eslint-disable no-useless-escape */
	return `
		<!DOCTYPE html>
		<html>
		<head>
			<meta name="viewport" content="width=device-width, initial-scale=1">
			<meta name="color-scheme" content="${dataTheme.value}">
			<meta charset="UTF-8">
			<style>
				body {
					font-family: InterVar, ui-sans-serif, system-ui, sans-serif, "Apple Color Emoji", "Segoe UI Emoji", "Segoe UI Symbol", "Noto Color Emoji";
					font-size: 14px;
					line-height: 1.25rem;
					background-color: ${colors.value.background};
					margin: 0;
				}

				blockquote {
					margin: 8px 0;
					padding-left: 12px;
					border-left: 1px solid ${colors.value.buttonHover};
				}

				table {
					color: inherit !important;
				}

				button {
					background: none;
					border: none;
					cursor: pointer;
					padding: 0;
				}

				.quote-hidden {
					display: none;
				}

				.email-pixel {
					display: none !important;
					visibility: hidden !important;
					width: 0 !important;
					height: 0 !important;
					overflow: hidden !important;
				}

				img[data-blocked-image] {
					display: none !important;
				}

				pre, code {
					font-family: 'Courier New', Courier, monospace;
					white-space: pre;
					overflow-x: auto;
				}

				@media (max-width: 640px) {
                    /* Only override specific problematic patterns */
                    table[width="600"], table[width="600px"] {
                        width: 100% !important;
                    }
                }
			</style>
			<script> ${iframeResizerChildScript} <\/script>
		</head>
		<body>
			${transformedContent}
			<script>
				// Forward keyboard events to parent
				['keydown', 'keyup', 'keypress'].forEach(eventType => {
					document.addEventListener(eventType, (e) => {
						window.parent.postMessage({
							type: 'keyboard',
							eventType: eventType,
							key: e.key,
							ctrlKey: e.ctrlKey,
							shiftKey: e.shiftKey,
							altKey: e.altKey,
							metaKey: e.metaKey,
						}, '*');
					});
				});

				// Forward link clicks to parent
				document.addEventListener('click', (e) => {
					const anchor = e.target.closest('a');
					if (anchor) {
						e.preventDefault();
						if (anchor.getAttribute('href')?.trim()) {
							window.open(anchor.href, '_blank');
						}
					}
				});
				${colors.value.script}
			<\/script>
		</body>
		</html>
	`
})

const colors = computed(() => THEME_CONFIG[dataTheme.value])

const DOMPURIFY_CONFIG = {
	ALLOWED_TAGS: [
		'html',
		'head',
		'body',
		'title',
		'meta',
		'style',
		'table',
		'tbody',
		'thead',
		'tfoot',
		'tr',
		'td',
		'th',
		'div',
		'span',
		'p',
		'br',
		'strong',
		'b',
		'em',
		'i',
		'u',
		'h1',
		'h2',
		'h3',
		'h4',
		'h5',
		'h6',
		'a',
		'img',
		'blockquote',
		'ul',
		'ol',
		'li',
		'pre',
		'code',
	],
	ALLOWED_ATTR: [
		'style',
		'class',
		'id',
		'width',
		'height',
		'align',
		'valign',
		'cellpadding',
		'cellspacing',
		'border',
		'bgcolor',
		'color',
		'href',
		'src',
		'alt',
		'title',
		'target',
		'data-type',
		'data-id',
		'data-label',
		'data-list',
		'data-email-footer',
		'xmlns',
		'content',
		'name',
		'http-equiv',
		'charset',
	],
	KEEP_CONTENT: true,
	ALLOW_UNKNOWN_PROTOCOLS: false,
	WHOLE_DOCUMENT: true,
	ADD_TAGS: ['meta', 'style', 'pre', 'code'],
	ADD_ATTR: ['cellpadding', 'cellspacing', 'border', 'bgcolor', 'xmlns', 'charset'],
	REMOVE_EMPTY: false,
}

const THEME_CONFIG = {
	light: {
		background: '#FFFFFF',
		text: '#383838',
		button: '#F3F3F3',
		buttonHover: '#EDEDED',
		script: '',
	},
	dark: {
		background: '#0F0F0F',
		text: '#D4D4D4',
		button: '#2B2B2B',
		buttonHover: '#343434',
		script: `
			function hasBackground(el) {
				while (el && el !== document.body) {
					const bg = getComputedStyle(el).backgroundColor;
					if (bg !== 'transparent' && bg !== 'rgba(0, 0, 0, 0)') {
						return true;
					}
					el = el.parentElement;
				}
				return false;
			}

			function walkAndWrapTextNodes(node) {
				for (let child of Array.from(node.childNodes)) {
					if (child.nodeType === 3) {
						const trimmed = child.textContent.trim();
						if (
							trimmed.length > 0 &&
							!hasBackground(child.parentElement) &&
							child.parentElement.tagName !== 'A' &&
							child.parentElement.tagName !== 'PRE' &&
							child.parentElement.tagName !== 'CODE'
						) {
							child.parentElement.style.setProperty('color', '#D4D4D4');
						}
					} else if (child.nodeType === 1) {
						walkAndWrapTextNodes(child);
					}
				}
			}

			walkAndWrapTextNodes(document.body);
		`,
	},
}
</script>
