/**
 * Bytes over a JSON transport.
 *
 * Yjs speaks `Uint8Array` and the relay speaks JSON, so every update and every
 * awareness frame crosses as base64. Chunked, because
 * `String.fromCharCode.apply` on a whole document's worth of bytes overflows
 * the argument stack — which shows up as a document that syncs fine until it
 * gets long.
 */

const CHUNK = 0x8000

export function toBase64(bytes) {
  let bin = ''
  for (let i = 0; i < bytes.length; i += CHUNK) {
    bin += String.fromCharCode.apply(null, bytes.subarray(i, i + CHUNK))
  }
  return btoa(bin)
}

export function fromBase64(b64) {
  const bin = atob(b64)
  const out = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i += 1) out[i] = bin.charCodeAt(i)
  return out
}
