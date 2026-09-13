"""A small picture of a file, for the grid.

Derived from frappe/suite's `suite.drive.api.files.get_thumbnail` (AGPL-3.0,
Copyright (c) Frappe Technologies Pvt. Ltd. and contributors), which this
follows in the three things it gets right: the permission check comes *first*,
so the endpoint cannot be used to ask whether a file exists; nothing but an
image, a video or a PDF is ever looked at; and the answer is webp with a
private `Cache-Control`, because the browser is the only cache worth having
for something this small and this numerous.

What is ours is where the bytes come from — `r2.contents`, since a file here
may be an object in a bucket rather than a path on disk — and what happens when
a decoder is missing, which is the part that matters most in practice.

**A thumbnail is a nicety and never a failure.** Every path that cannot produce
one answers empty and the card draws the file's format mark instead, which is
the picture it was already showing. So a site without ffmpeg gets no video
stills and nothing else changes; installing ffmpeg turns them on with no code
change and no migration. This is why there are no exceptions raised below for
anything but permission.
"""

from io import BytesIO

import frappe
from frappe import _

from . import kinds, r2

#: The longest edge of a thumbnail, in pixels.
#:
#: The grid's card is 170px wide and a phone's is about the same, so 400 is a
#: little over two device pixels per CSS pixel — enough that a retina screen
#: does not see the resampling, small enough that the file is a few kilobytes.
#: Bigger was measured and is simply more bytes: at 800 the wall of cards cost
#: four times the transfer and looked identical.
EDGE = 400

#: How long a browser may keep one without asking again.
#:
#: An hour, and the URL carries no version, so a file replaced in place shows
#: its old picture for up to that long. The alternative is a cache key on
#: `modified`, which makes every listing's URLs change whenever anything about
#: a row changes — a rename would re-fetch every thumbnail on the screen. An
#: hour of a stale picture is the better of the two.
MAX_AGE = 3600

#: The kinds a thumbnail can exist for. The browser holds the same list —
#: `frontend/src/modules/onestorage/lib/art.js` — so that a card for a `.zip`
#: never makes the request at all, and `tests/test_thumbnails.py` reads the two
#: back against each other.
THUMBNAILED = (kinds.IMAGE, kinds.VIDEO, kinds.PDF)


@frappe.whitelist()
def thumbnail(file: str):
	"""The thumbnail for one file, as webp, or an empty answer.

	The permission check is first and is Frappe's own, which is the same one
	`r2.download` leans on: it already knows about a public file, the owner, a
	`DocShare` and a file that hangs off a document the reader may see. Asking
	it before looking at the row is what stops this endpoint answering "that is
	a video" about a file the caller may not read.
	"""
	# A file on a mounted host has no `File` row and no local bytes, and
	# pulling a whole remote object over the wire to draw a 170px card is the
	# one request this must never make. The rail's mounts show marks.
	from . import remote

	if remote.is_remote(file):
		return ""

	doc = frappe.get_cached_doc("File", file)

	if not frappe.has_permission("File", "read", doc=doc):
		frappe.throw(_("Not permitted."), frappe.PermissionError)

	if doc.is_folder or doc.get(kinds.KIND_FIELD) not in THUMBNAILED:
		return ""

	picture = render(doc)
	if not picture:
		return ""

	frappe.local.response.filename = f"{doc.name}.webp"
	frappe.local.response.filecontent = picture
	frappe.local.response.type = "download"
	# `inline`, or the browser downloads it instead of drawing it, which is what
	# `attachment` means and is `as_raw`'s default.
	frappe.local.response.display_content_as = "inline"
	frappe.local.response.content_type = "image/webp"
	# Private, because the file is: a shared proxy that kept one of these would
	# be handing somebody's drawings to the next reader through it.
	#
	# `response_headers` and not `response.headers` — the latter is not a thing
	# `as_raw` reads, so setting it there is setting a key nobody looks at.
	# `app.process_response` merges this one in, after defaulting every answer
	# to no-cache.
	frappe.local.response_headers["Cache-Control"] = f"private, max-age={MAX_AGE}"


def render(doc) -> bytes | None:
	"""The picture, or `None` for anything this site cannot decode.

	Wrapped whole rather than per-step: the failures here are a truncated
	upload, a format Pillow was built without, a PDF that is encrypted and a
	video whose container ffmpeg does not know, and there is nothing useful to
	tell them apart *for this purpose* — each one means "draw the mark". They
	are logged, because a site where every thumbnail fails is a site with a
	broken decoder and somebody should be able to find that out.
	"""
	kind = doc.get(kinds.KIND_FIELD)
	try:
		if kind == kinds.IMAGE:
			return _from_image(r2.contents(doc))
		if kind == kinds.PDF:
			return _from_pdf(r2.contents(doc))
		if kind == kinds.VIDEO:
			return _from_video(doc)
	except Exception:
		# Title only, so the traceback is the body: `log_error`'s first argument
		# is the *title*, and passing the sentence there filed three identical
		# logs that said what had happened and nothing about why.
		frappe.log_error(title=f"onestorage.thumbnails: no thumbnail for {doc.name}")
	return None


def _encode(image) -> bytes:
	"""One Pillow image, shrunk and encoded.

	`thumbnail` and not `resize`: it keeps the aspect ratio and, more to the
	point, it never enlarges — a 64px favicon asked to fill a 400px box is a
	blurry 400px file where the original was smaller than the request.

	`RGB` because webp has no palette and a paletted GIF or a 1-bit TIFF raises
	on save; the alpha channel goes with it, which is what the card wants — it
	sits on a grey panel and a transparent PNG rendered on it looked like a
	hole.
	"""
	from PIL import Image, ImageOps

	# The orientation a phone recorded rather than the one the sensor used,
	# or every photograph taken in portrait is a thumbnail lying on its side.
	image = ImageOps.exif_transpose(image)
	if image.mode != "RGB":
		image = image.convert("RGB")
	image.thumbnail((EDGE, EDGE), Image.LANCZOS)

	out = BytesIO()
	image.save(out, format="WEBP", quality=72, method=4)
	return out.getvalue()


def _from_image(content: bytes) -> bytes:
	from PIL import Image

	return _encode(Image.open(BytesIO(content)))


def _from_pdf(content: bytes) -> bytes | None:
	"""The first page, if this site can read a PDF at all.

	PyMuPDF rather than poppler: it is one wheel with no system package behind
	it, so a site that wants PDF thumbnails installs one thing. Absent, there
	are none — which is the state this repo ships in, deliberately. It is a
	60 MB dependency to draw a picture of page one, and that is a call for
	whoever runs the site rather than one to make for them.
	"""
	try:
		import pymupdf
	except ImportError:
		return None

	from PIL import Image

	with pymupdf.open(stream=content, filetype="pdf") as document:
		if not document.page_count:
			return None
		# Rendered at the size we want rather than at 72dpi and then shrunk:
		# rasterising a whole A4 page to throw nine tenths of it away is the
		# expensive half of this function.
		page = document.load_page(0)
		scale = EDGE / max(page.rect.width, page.rect.height)
		pixmap = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale))
		return _encode(Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples))


def _from_video(doc) -> bytes | None:
	"""A still from a few seconds in, if ffmpeg is on the path.

	Not frame zero: the first frame of a great many videos is black, a fade or
	a slate, and a grid of black cards is worse than a grid of marks. Three
	seconds is far enough in to be the picture and near enough that `-ss`
	before `-i` still seeks rather than decodes.

	Through a temporary file rather than a pipe because seeking a pipe is not a
	thing, and the file has to be local: the object may be in a bucket, and
	handing ffmpeg a presigned URL would be this server's credentials going out
	to a subprocess.
	"""
	import shutil
	import subprocess
	import tempfile

	ffmpeg = shutil.which("ffmpeg")
	if not ffmpeg:
		return None

	from PIL import Image

	with tempfile.NamedTemporaryFile(suffix=_suffix(doc.file_name)) as source:
		source.write(r2.contents(doc))
		source.flush()
		frame = subprocess.run(
			[
				ffmpeg, "-nostdin", "-loglevel", "error",
				"-ss", "3", "-i", source.name,
				"-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-",
			],
			capture_output=True,
			# A video this cannot decode should cost one second and not a
			# worker: without this an unusual container can hang a request.
			timeout=20,
			check=False,
		)

	if frame.returncode != 0 or not frame.stdout:
		return None

	return _encode(Image.open(BytesIO(frame.stdout)))


def _suffix(file_name: str) -> str:
	"""The extension, which is how ffmpeg picks a demuxer for a temporary file."""
	name = str(file_name or "")
	return f".{name.rsplit('.', 1)[-1]}" if "." in name else ""
