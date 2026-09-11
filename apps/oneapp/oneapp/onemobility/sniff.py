"""What is this, actually.

A customer declaring their own format is a customer being asked a question
they may not be able to answer. "VDV 452" is a phrase from a specification;
what they have is a nightly drop from a supplier, called `export_2026-09-11.dat`
and documented by nobody. Getting it wrong fails late and reads like our bug.

So the format is a *hint* and this is the answer. A delivery is opened, looked
at, and identified from what is inside it — never from the extension, which is
the field most likely to be wrong. Extensions and MIME types are consulted only
to break a tie.

**The grace part.** Recognition is graded rather than binary, and every answer
carries the evidence it was reached on. A delivery that matches a format
exactly is loaded. One that matches loosely — the right tables under the wrong
names, an encoding nobody declared, a zip with the feed one directory down — is
loaded too, and the source says what had to be forgiven. One that matches
nothing is refused with what was found, which is the one outcome a customer can
act on: "this contains agency.txt and stops.txt but no routes.txt" beats
"could not read".

Nothing here parses a feed. It reads enough of one to say which reader should,
which is a few kilobytes for every format in the list — a GTFS zip is
identified from its member names without inflating a single entry.
"""

import csv
import gzip
import io
import re
import tarfile
import zipfile

#: How much of a stream is enough to recognise it. Every signature below lives
#: in the first few kilobytes: an XML root element, a protobuf field tag, a CSV
#: header row. Reading more to be certain would mean reading the whole feed.
PEEK = 64 * 1024

#: The member names GTFS is made of, and how much of a set has to be there.
#: `agency` and `stops` alone are a stop export somebody made in a spreadsheet;
#: with `routes` and `trips` it is a feed.
GTFS_CORE = {"agency.txt", "stops.txt", "routes.txt", "trips.txt", "stop_times.txt"}
GTFS_ENOUGH = 3

#: VDV 452's own table names, which appear as `tbl; REC_ORT` inside the file
#: rather than as a filename. Any two of these and it is a planning delivery.
VDV452_TABLES = {
	"REC_ORT", "REC_HP", "LINIE", "REC_LID", "LID_VERLAUF", "REC_FRT",
	"SEL_FZT_FELD", "ORT_HZTF", "FIRMENKALENDER", "MENGE_FZG",
	"MENGE_UNTERNEHMEN", "UMLAUF", "REC_UMLAUF",
}
VDV452_ENOUGH = 2

#: Root elements, by the format they belong to. Matched on the local name, so a
#: namespace nobody agrees on does not decide the answer — the same reason
#: `streaming._local` exists.
ROOTS = {
	"OccupancyMessage": "VDV 457-2",
	"PassengerCountingServiceBGS_457-3.GetAllDataResponse": "VDV 457-3",
	"AUSNachricht": "VDV 454",
	"IstFahrtSammlung": "VDV 454",
	"DatenAbrufenAntwort": "VDV 454",
	"Siri": "SIRI",
	"ServiceDelivery": "SIRI",
	"PublicationDelivery": "NeTEx",
}

#: Extensions worth believing when nothing inside the file settles it. Never on
#: their own — a `.xml` says nothing about which XML — but a `.pb` beside bytes
#: that look like protobuf is a second vote for the same answer.
HINTS = {
	".pb": "GTFS Realtime", ".pbf": "GTFS Realtime", ".protobuf": "GTFS Realtime",
	".x10": "VDV 452", ".vdv": "VDV 452",
}


class Guess:
	"""What this is, how sure, and what had to be forgiven to say so.

	`certainty` is `exact` when the delivery matched a format's own structure,
	`likely` when it matched with something forgiven, and `none` when it did
	not. `notes` is what a customer reads on the source, so every entry is
	written for somebody who has never read a specification.
	"""

	def __init__(self, format: str = "", certainty: str = "none",
	             notes: list[str] | None = None, found: list[str] | None = None):
		self.format = format
		self.certainty = certainty
		self.notes = notes or []
		self.found = found or []

	def __bool__(self) -> bool:
		return bool(self.format)

	def __repr__(self) -> str:
		return f"<Guess {self.format or 'unknown'} {self.certainty}>"

	def as_dict(self) -> dict:
		return {
			"format": self.format,
			"certainty": self.certainty,
			"notes": self.notes,
			"found": self.found[:40],
		}


def _unwrap(content: bytes, notes: list[str]) -> bytes:
	"""Through one layer of compression that is not an archive.

	A supplier who gzips an XML document has not changed what it is, and a
	reader that refuses it is refusing for a reason the customer cannot see.
	One layer only: a gzip of a gzip is somebody's script run twice and worth
	saying out loud rather than unwrapping quietly for ever.
	"""
	if content[:2] == b"\x1f\x8b":
		try:
			opened = gzip.decompress(content)
		except OSError:
			return content
		notes.append("Unpacked a gzip wrapper.")
		return opened
	return content


def _members(content: bytes, notes: list[str]) -> list[str] | None:
	"""The names inside an archive, or None if it is not one.

	Zip and tar both, because an SFTP drop is as likely to be a `.tar.gz` as a
	`.zip` and the difference is not the customer's problem. Directory prefixes
	are kept in `found` and stripped for matching: a GTFS feed one folder down
	is the commonest packaging mistake there is, and it is not an error.
	"""
	if content[:2] == b"PK":
		try:
			with zipfile.ZipFile(io.BytesIO(content)) as bundle:
				return [n for n in bundle.namelist() if not n.endswith("/")]
		except zipfile.BadZipFile:
			notes.append("Looks like a zip but could not be opened.")
			return None
	if content[:2] == b"\x1f\x8b" or content[257:262] == b"ustar":
		try:
			with tarfile.open(fileobj=io.BytesIO(content)) as bundle:
				return [m.name for m in bundle.getmembers() if m.isfile()]
		except tarfile.TarError:
			return None
	return None


def _basenames(names: list[str]) -> set[str]:
	return {n.rsplit("/", 1)[-1].lower() for n in names}


def _looks_like_protobuf(head: bytes) -> bool:
	"""A GTFS-Realtime body, which carries no name of its own.

	Every `FeedMessage` opens with field 1 — `header` — as a length-delimited
	value, so the first byte is 0x0a. That is a weak signal on its own and a
	strong one with the rest: the header's own first field is the version
	string "2.0", which lands within the first handful of bytes.
	"""
	if not head or head[0] != 0x0A:
		return False
	return b"2.0" in head[:24] or head[1] < 0x40


def _xml_root(head: bytes) -> str:
	"""The local name of the first element, whatever it is wrapped in."""
	text = head.lstrip()[:PEEK]
	if not text[:1] == b"<":
		return ""
	found = re.search(rb"<\s*(?!\?|!)([A-Za-z_][\w.\-]*)(?::([\w.\-]+))?", text)
	if not found:
		return ""
	local = found.group(2) or found.group(1)
	return local.decode("ascii", "replace")


def _vdv452_tables(head: bytes) -> set[str]:
	"""Table names out of a VDV 452 delivery's own `tbl;` lines.

	Read off the bytes rather than a decoded string: the specification says
	ISO-8859-1, real deliveries arrive in UTF-8 and in cp1252, and the table
	names are ASCII in all three.
	"""
	return {
		name.decode("ascii", "replace").upper()
		for name in re.findall(rb"(?im)^\s*tbl\s*;\s*([A-Za-z0-9_]+)", head)
	}


def _csv_header(head: bytes) -> list[str]:
	try:
		text = head.decode("utf-8-sig")
	except UnicodeDecodeError:
		text = head.decode("cp1252", "replace")
	line = text.splitlines()[0] if text.splitlines() else ""
	if not line:
		return []
	try:
		dialect = csv.Sniffer().sniff(line, delimiters=",;\t|")
	except csv.Error:
		return []
	return [c.strip().lower() for c in next(csv.reader([line], dialect), [])]


def identify(content: bytes, filename: str = "", declared: str = "") -> Guess:
	"""What this delivery is. Structure first, names only to break a tie.

	`declared` is what the source says it is, and it is deliberately not
	trusted: it is used to choose between two equally good answers and to note
	a disagreement, never to override what is actually in the file. A customer
	who picked the wrong item from a dropdown two months ago should not have
	their feed refused for it.
	"""
	notes: list[str] = []
	if not content:
		return Guess(notes=["The delivery was empty."])

	lower = (filename or "").lower()
	members = _members(content, notes)

	# --- an archive, identified by what is in it ---------------------------
	if members is not None:
		found = sorted(members)[:40]
		names = _basenames(members)
		hits = GTFS_CORE & names
		if len(hits) >= GTFS_ENOUGH:
			if not names & {"stop_times.txt"}:
				notes.append("No stop_times.txt, so this feed has no timetable.")
			nested = {n for n in members if "/" in n}
			if nested and len(nested) == len(members):
				notes.append("The feed is inside a folder rather than at the "
				             "top of the zip. Read it from there.")
			exact = hits >= GTFS_CORE and not notes
			return Guess("GTFS", "exact" if exact else "likely", notes, found)

		xml = [n for n in members if n.lower().endswith(".xml")]
		if xml:
			notes.append(f"An archive of {len(xml)} XML documents.")
			inner = _peek_member(content, xml[0])
			guess = identify(inner, xml[0], declared)
			if guess:
				guess.notes = notes + guess.notes
				guess.found = found
				guess.certainty = "likely"
				return guess

		tables = set()
		for name in members[:20]:
			tables |= _vdv452_tables(_peek_member(content, name))
		if len(tables) >= VDV452_ENOUGH:
			notes.append("A VDV 452 delivery, packed as an archive.")
			return Guess("VDV 452", "likely", notes, found)

		return Guess(notes=notes + ["Nothing in this archive looks like a feed."],
		             found=found)

	content = _unwrap(content, notes)
	head = content[:PEEK]

	# --- one document ------------------------------------------------------
	root = _xml_root(head)
	if root:
		if root in ROOTS:
			return Guess(ROOTS[root], "exact" if not notes else "likely",
			             notes, [root])
		notes.append(f"XML whose root element is <{root}>, which is not one "
		             "this reads.")
		return Guess(notes=notes, found=[root])

	tables = _vdv452_tables(head)
	if len(tables) >= VDV452_ENOUGH:
		return Guess("VDV 452", "exact" if not notes else "likely", notes,
		             sorted(tables))
	if tables:
		notes.append(f"One VDV 452 table ({sorted(tables)[0]}) and no others, "
		             "so this is part of a delivery rather than one.")
		return Guess(notes=notes, found=sorted(tables))

	if _looks_like_protobuf(head):
		notes.append("Protocol buffers, which only GTFS-Realtime uses here.")
		return Guess("GTFS Realtime", "likely", notes)

	header = _csv_header(head)
	if header:
		notes.append("A single CSV, where GTFS is a zip of several.")
		return Guess(notes=notes, found=header)

	for suffix, format in HINTS.items():
		if lower.endswith(suffix):
			notes.append(f"Nothing inside this says what it is; going on the "
			             f"{suffix} extension.")
			return Guess(format, "likely", notes)

	return Guess(notes=notes + ["This does not look like any feed format."])


def _peek_member(content: bytes, name: str) -> bytes:
	"""The first `PEEK` bytes of one entry, without inflating the rest."""
	try:
		if content[:2] == b"PK":
			with zipfile.ZipFile(io.BytesIO(content)) as bundle:
				with bundle.open(name) as entry:
					return entry.read(PEEK)
		with tarfile.open(fileobj=io.BytesIO(content)) as bundle:
			handle = bundle.extractfile(name)
			return handle.read(PEEK) if handle else b""
	except (KeyError, OSError, tarfile.TarError, zipfile.BadZipFile):
		return b""


def reconcile(guess: Guess, declared: str) -> Guess:
	"""What to do when the file and the dropdown disagree.

	The file wins, and the disagreement is written down. A source declared
	`GTFS` that has been sending VDV 452 for a month is a source that has been
	working or a source that has been failing, and either way the customer
	should be told which — not have one of the two silently preferred.
	"""
	if not declared or declared == "Detect" or not guess:
		return guess
	if guess.format != declared:
		guess.notes.append(
			f"This source is set to {declared}, but the delivery is "
			f"{guess.format}. Read as {guess.format}."
		)
		guess.certainty = "likely"
	return guess
