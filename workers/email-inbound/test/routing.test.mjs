/**
 * Recipient routing. This decides which tenant receives a message, so a bug
 * here delivers one customer's mail to another.
 *
 * Run: node --test workers/email-inbound/test/
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'

import { parseRecipient } from '../src/routing.js'

const DOMAIN = '4dl.app'

test('routes a normal address', () => {
  assert.deepEqual(parseRecipient('acme.ap@4dl.app', DOMAIN), {
    tenant: 'acme',
    localPart: 'ap',
    bounce: false,
  })
})

test('is case insensitive', () => {
  assert.deepEqual(parseRecipient('ACME.AP@4DL.APP', DOMAIN), {
    tenant: 'acme',
    localPart: 'ap',
    bounce: false,
  })
})

test('accepts hyphenated tenants', () => {
  assert.equal(parseRecipient('acme-corp.support@4dl.app', DOMAIN).tenant, 'acme-corp')
})

test('a local part may hold further dots', () => {
  // `acme.first.last` is the workspace `acme` and the person `first.last`.
  assert.deepEqual(parseRecipient('acme.first.last@4dl.app', DOMAIN), {
    tenant: 'acme',
    localPart: 'first.last',
    bounce: false,
  })
})

test('a bounce comes back to the tenant that sent it', () => {
  assert.deepEqual(parseRecipient('t-acme@4dl.app', DOMAIN), {
    tenant: 'acme',
    localPart: '',
    bounce: true,
  })
})

test('rejects a different domain', () => {
  assert.equal(parseRecipient('acme.ap@evil.com', DOMAIN), null)
})

test('rejects a domain that merely ends with ours', () => {
  assert.equal(parseRecipient('acme.ap@not4dl.app', DOMAIN), null)
})

test('rejects a subdomain of ours', () => {
  // We onboard exactly one domain; anything under it was never issued here.
  assert.equal(parseRecipient('acme.ap@mail.4dl.app', DOMAIN), null)
})

test('rejects an address with no tenant on the front', () => {
  assert.equal(parseRecipient('ap@4dl.app', DOMAIN), null)
})

test('rejects an empty local part after the tenant', () => {
  assert.equal(parseRecipient('acme.@4dl.app', DOMAIN), null)
})

test('rejects slugs the control plane would never issue', () => {
  for (const bad of ['-acme', 'acme-', 'ac--me', 'a', 'ac_me']) {
    assert.equal(parseRecipient(`${bad}.ap@4dl.app`, DOMAIN), null, bad)
  }
  for (const bad of ['-acme', 'ac--me', 'a']) {
    assert.equal(parseRecipient(`t-${bad}@4dl.app`, DOMAIN), null, bad)
  }
})

test('rejects malformed input', () => {
  for (const bad of ['', null, undefined, 'noatsign', '@4dl.app', 42]) {
    assert.equal(parseRecipient(bad, DOMAIN), null)
  }
})

test('rejects when no mail domain is configured', () => {
  assert.equal(parseRecipient('acme.ap@4dl.app', ''), null)
})

test('keeps plus addressing in the local part', () => {
  assert.equal(parseRecipient('acme.ap+xyz@4dl.app', DOMAIN).localPart, 'ap+xyz')
})
