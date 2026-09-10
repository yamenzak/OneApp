/**
 * Two people in one file at once, over the socket the bench already runs.
 *
 * Frappe's socketio process loads `apps/<app>/realtime/handlers.js` from every
 * installed app and calls it once per connection (`frappe/realtime/index.js`).
 * That is the whole reason live editing costs nothing to deploy here: this
 * file runs *inside* the node process that is already serving `list_update`
 * and `doc_viewers`, so there is no second service, no Hocuspocus, no Redis
 * fan-out of our own, and nothing new for an operator to watch.
 *
 * What Frappe's own handlers do not have is the thing collaboration needs: a
 * client may join a room but may not *say* anything into one. Every message in
 * the framework originates in Python and arrives through the `events` channel.
 * Routing a keystroke that way would be an HTTP round trip into a GIL-bound
 * worker per keystroke, which is the cost `docs/SHEETS.md` was really objecting
 * to. Here a message goes browser → node → browsers and never touches Python.
 *
 * Python is asked exactly one question, once per room per socket: `admit`,
 * which says who this person is and whether they may write. Everything after
 * that is memory in this process.
 *
 * Three refusals worth naming, because each is the hole this would otherwise
 * be:
 *
 *   * **A room is not a doctype.** `admit` takes a kind from a fixed list and
 *     answers with the room name itself, so a client cannot name the room it
 *     lands in. Letting it would make this an unauthenticated pub/sub bus for
 *     every row on the site.
 *   * **A reader may not send.** The write flag comes back from `admit` and is
 *     kept here, not on the client. Somebody with read access to a shared sheet
 *     can watch other people's cursors and cannot move their cells.
 *   * **A message has a size.** One client holding a socket open can otherwise
 *     push a room's worth of memory through this process. Anything over the cap
 *     is dropped rather than relayed.
 */

// Kinds a client may ask to join. The value is only a prefix for the room
// name; what a kind *means* is decided in `oneapp/onespace/live.py`.
const KINDS = new Set(["file"]);

// Bytes in one relayed message. A Yjs update for a paragraph is a few hundred;
// a whole document's initial state is the big one, and 512KB carries a novel.
const MAX_BYTES = 512 * 1024;

// Messages per socket per window, across every room it is in. A keystroke in a
// document is one update, so a fast typist is around 15/s; a paste that
// reflows a page is a burst. This is a ceiling on abuse, not a rate limit on
// typing.
const BURST = 240;
const WINDOW_MS = 5000;

const roomName = (kind, name) => `oneapp:${kind}/${name}`;

function oneapp_handlers(socket) {
	// Which rooms this socket is in, and whether it may write to each.
	const joined = new Map();
	let sent = 0;
	let windowStarted = Date.now();

	function allowed() {
		const now = Date.now();
		if (now - windowStarted > WINDOW_MS) {
			windowStarted = now;
			sent = 0;
		}
		return ++sent <= BURST;
	}

	/**
	 * Everyone in this room, as the roster the presence strip draws.
	 *
	 * Read off the adapter rather than kept in a variable, the way Frappe's own
	 * `notify_subscribed_doc_users` does it: a socket that died without saying
	 * goodbye is gone from the adapter and would still be in our variable.
	 *
	 * One entry per *person*, not per socket — the same person with the file
	 * open in two tabs is one face, and their cursor is whichever tab moved
	 * last.
	 */
	function roster(room) {
		const ids = socket.nsp.adapter.rooms.get(room) || new Set();
		const people = new Map();
		socket.nsp.sockets.forEach((sock) => {
			if (!ids.has(sock.id) || !sock.oneapp_who) return;
			people.set(sock.oneapp_who.user, sock.oneapp_who);
		});
		return [...people.values()];
	}

	function announce(room) {
		socket.nsp.to(room).emit("oneapp_here", { room, people: roster(room) });
	}

	socket.on("oneapp_join", async (kind, name, ack) => {
		const reply = typeof ack === "function" ? ack : () => {};
		if (!KINDS.has(kind) || !name) {
			reply({ ok: false });
			return;
		}
		try {
			// The link, if this socket was opened by a page at
			// `/one/link/<secret>`. It is the only credential a guest has, so
			// it travels in the handshake — a browser cannot set headers on a
			// websocket, and the secret is already in that page's URL.
			const link = socket.handshake.query.oneapp_link || "";
			const res = await socket.frappe_request(
				"/api/method/oneapp.onespace.live.admit",
				{ kind, name, link }
			);
			const { message } = await res.json();
			if (!message || !message.ok) {
				reply({ ok: false });
				return;
			}

			// The room the *server* named, not the one the client asked for.
			const room = roomName(kind, message.name);
			// Two strangers on one link are two people. Python cannot tell
			// them apart — they are the same session and the same link — and
			// this can, because a socket is a connection. Only for guests:
			// a signed-in person with two tabs is deliberately one face.
			socket.oneapp_who = message.guest
				? { ...message.who, user: `${message.who.user}#${socket.id}` }
				: message.who;
			joined.set(room, { write: !!message.write });
			socket.join(room);

			// Whether this socket is the first one in. The document editor needs
			// it: a Yjs room has to be seeded from the stored HTML by exactly one
			// joiner, and two people opening the same document at the same moment
			// would otherwise seed it twice and merge two copies of the prose.
			const first = roster(room).length <= 1;

			reply({
				ok: true, room, write: !!message.write,
				who: socket.oneapp_who, guest: !!message.guest, first,
			});
			announce(room);
		} catch (err) {
			console.warn("oneapp_join failed", err);
			reply({ ok: false });
		}
	});

	socket.on("oneapp_send", (room, event, payload) => {
		const seat = joined.get(room);
		if (!seat || !seat.write || !event) return;
		if (!allowed()) return;

		let body;
		try {
			body = JSON.stringify(payload ?? null);
		} catch {
			return;
		}
		if (body.length > MAX_BYTES) return;

		// `socket.to` and not `nsp.to`: the sender already has its own change,
		// and echoing it back is how a cursor jumps and an undo stack doubles.
		socket.to(room).emit("oneapp_said", {
			room,
			event,
			from: socket.oneapp_who ? socket.oneapp_who.user : socket.user,
			payload,
		});
	});

	/**
	 * "I have just arrived — somebody tell me what this file looks like."
	 *
	 * A reader may do this and may not `oneapp_send`, and the difference is
	 * the whole of why it is a separate event: an ask carries **no payload at
	 * all**, so there is nothing in it that could be a disguised update. The
	 * answer comes back through `oneapp_tell`, from somebody who may write.
	 *
	 * Without it a read-only person joining a room that already has somebody
	 * in it received nothing, and sat looking at whatever the server last
	 * stored while the other person typed — which is the exact case live
	 * editing exists to fix. Found by a stranger on a read link watching an
	 * empty page.
	 */
	socket.on("oneapp_ask", (room) => {
		const seat = joined.get(room);
		if (!seat) return;
		if (!allowed()) return;

		socket.to(room).emit("oneapp_asked", {
			room,
			from: socket.oneapp_who ? socket.oneapp_who.user : socket.user,
		});
	});

	/**
	 * The same fan-out, addressed to one person in the room.
	 *
	 * What it is for: a joiner asks the room for the document as it stands, and
	 * one person answers. Sending that answer to everybody would push a whole
	 * document at every open tab each time somebody new arrives.
	 */
	socket.on("oneapp_tell", (room, to, event, payload) => {
		const seat = joined.get(room);
		if (!seat || !event || !to) return;
		if (!allowed()) return;

		let body;
		try {
			body = JSON.stringify(payload ?? null);
		} catch {
			return;
		}
		if (body.length > MAX_BYTES) return;

		const ids = socket.nsp.adapter.rooms.get(room) || new Set();
		socket.nsp.sockets.forEach((sock) => {
			if (!ids.has(sock.id)) return;
			if (!sock.oneapp_who || sock.oneapp_who.user !== to) return;
			sock.emit("oneapp_said", {
				room,
				event,
				from: socket.oneapp_who ? socket.oneapp_who.user : socket.user,
				payload,
			});
		});
	});

	socket.on("oneapp_leave", (room) => {
		if (!joined.has(room)) return;
		joined.delete(room);
		socket.leave(room);
		announce(room);
	});

	socket.on("disconnect", () => {
		// `leave` has already happened by the time this fires, so the roster is
		// right — this only has to tell the people still in the room.
		for (const room of joined.keys()) announce(room);
		joined.clear();
	});
}

module.exports = oneapp_handlers;
