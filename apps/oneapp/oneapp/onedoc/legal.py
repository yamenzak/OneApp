"""What OneDoc adds to the agreements."""

from ..onelegal.registry import clause

M = "OneDoc"

clause(
    document="privacy", section="modules", key="doc-body", module=M,
    body="""
        OneDoc holds the text of every document, its formatting, and its version
        history. A document is a file, so what is said about files applies to it
        as well.
    """,
)

clause(
    document="privacy", section="keeping", key="doc-versions", module=M,
    body="""
        Version history is kept in full for a day, thinned to hourly, then
        daily, then weekly as it ages, and forgotten after ninety days. A
        version somebody has named is kept until they unname it.
    """, order=30,
)

clause(
    document="terms", section="modules", key="doc-export", module=M,
    body="""
        Documents export as self-contained HTML, which every word processor and
        every mail client opens. There is no proprietary format to be locked
        into.
    """,
)
