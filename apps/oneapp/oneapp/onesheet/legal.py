"""What OneSheet adds to the agreements."""

from ..onelegal.registry import clause

M = "OneSheet"

clause(
    document="privacy", section="modules", key="sheet-book", module=M,
    body="""
        OneSheet holds each workbook — its cells, its formulas, its formatting
        and its version history — in the workspace's own database rather than as
        a file in the object store.
    """,
)

clause(
    document="terms", section="modules", key="sheet-formulas", module=M,
    body="""
        Formulas are evaluated in your browser and on our server. A sheet can
        read a range into a record and write one back, which is an instruction
        from you and is recorded as one.
    """,
)

clause(
    document="terms", section="modules", key="sheet-export", module=M,
    body="""
        Sheets export as CSV, one tab at a time, values rather than formulas.
    """, order=20,
)
