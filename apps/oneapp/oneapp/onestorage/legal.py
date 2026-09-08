"""What OneStorage adds to the agreements.

Files are the part of the product that leaves our database: the bytes go to an
object store, in a region the workspace chose, under somebody else's roof. That
is the one fact this file exists to make sure the documents say.
"""

from ..onelegal.registry import clause, subprocessor

M = "OneStorage"

subprocessor(
    name="Cloudflare, Inc.",
    module=M,
    purpose="Object storage (R2) for every file, document image and backup",
    data="File contents and their names, and whatever personal data those files "
         "happen to contain",
    where="The storage location chosen when the workspace was created",
    safeguard="Standard Contractual Clauses and Cloudflare's data processing "
              "addendum",
    url="https://www.cloudflare.com/cloudflare-customer-dpa/",
)

clause(
    document="terms", section="modules", key="storage-quota", module=M,
    body="""
        A workspace's plan includes an amount of storage. Files, documents,
        sheets and mail all count towards it, each object counted once however
        many places it appears. What is in the bin still counts until the bin is
        emptied.
    """,
)

clause(
    document="privacy", section="modules", key="storage-what", module=M,
    body="""
        OneStorage holds the files your organisation uploads and the ones the
        product makes — a document's images, an exported sheet, a message's
        attachments. The bytes are kept in Cloudflare R2 in the region chosen
        for the workspace; the record of what a file is called, who owns it and
        who it is shared with stays in the workspace's own database.
    """,
)

clause(
    document="privacy", section="keeping", key="storage-bin", module=M,
    body="""
        A deleted file goes to the workspace's bin, where anybody who could see
        it can put it back, and is destroyed when the bin is emptied or after
        the bin's own retention period, whichever is first.
    """, order=20,
)

clause(
    document="dpa", section="modules", key="storage-links", module=M,
    body="""
        A file can be shared by a link that carries its own secret and expires.
        A link is an instruction from you to make that file readable by whoever
        holds it, for as long as it lasts — up to ninety days — and we act on
        it. Links can be revoked at any time.
    """,
)

clause(
    document="aup", section="modules", key="storage-content", module=M,
    body="""
        Do not use OneStorage as a public file-distribution service or a backup
        target for material unrelated to your work in the workspace.
    """,
)
