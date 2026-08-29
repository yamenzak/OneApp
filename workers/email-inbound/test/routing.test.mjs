/**
 * Recipient routing. This decides which tenant receives a message, so a bug
 * here delivers one customer's mail to another.
 *
 * Run: node --test workers/email-inbound/test/
 */

import { test } from 'node:test'
import assert from 'node:assert/strict'

import { parseRecipient } from '../src/routing.js'

const DOMAIN = 't.4dl.app'

test('routes a normal address', () => {
  assert.deepEqual(parseRecipient('ap@acme.t.4dl.app', DOMAIN), {
    tenant: 'acme',
    localPart: 'ap',
  })
})

test('is case insensitive', () => {
  assert.deepEqual(parseRecipient('AP@ACME.T.4DL.APP', DOMAIN), {
    tenant: 'acme',
    localPart: 'ap',
  })
})

test('accepts hyphenated tenants', () => {
  assert.equal(parseRecipient('support@acme-corp.t.4dl.app', DOMAIN).tenant, 'acme-corp')
})

test('rejects a different domain', () => {
  assert.equal(parseRecipient('ap@acme.evil.com', DOMAIN), null)
})

test('rejects a domain that merely ends with ours', () => {
  // notatt.4dl.app must not be read as tenant "nota"
  assert.equal(parseRecipient('ap@acme.nott.4dl.app', DOMAIN)?.tenant, undefined)
})

test('rejects multi-label tenants', () => {
  // "a.b" is not a slug we ever issued
  assert.equal(parseRecipient('ap@a.b.t.4dl.app', DOMAIN), null)
})

test('rejects the bare mail domain', () => {
  assert.equal(parseRecipient('ap@t.4dl.app', DOMAIN), null)
})

test('rejects slugs the control plane would never issue', () => {
  for (const bad of ['-acme', 'acme-', 'ac--me', 'a', 'ac_me']) {
    assert.equal(parseRecipient(`ap@${bad}.t.4dl.app`, DOMAIN), null, bad)
  }
})

test('rejects malformed input', () => {
  for (const bad of ['', null, undefined, 'noatsign', '@acme.t.4dl.app', 42]) {
    assert.equal(parseRecipient(bad, DOMAIN), null)
  }
})

test('rejects when no mail domain is configured', () => {
  assert.equal(parseRecipient('ap@acme.t.4dl.app', ''), null)
})

test('keeps plus addressing in the local part', () => {
  assert.equal(parseRecipient('ap+xyz@acme.t.4dl.app', DOMAIN).localPart, 'ap+xyz')
})
