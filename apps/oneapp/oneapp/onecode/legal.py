"""What OneCode adds to the agreements."""

from ..onelegal.registry import clause

M = "OneCode"

clause(
    document="terms", section="modules", key="code-execution", module=M,
    body="""
        OneCode is an editor. It highlights code and stores it; it does not run
        it. Nothing you write in it is executed by us.
    """,
)

clause(
    document="aup", section="modules", key="code-secrets", module=M,
    body="""
        Do not store credentials, private keys or other secrets in code files
        and then share them by link. A file shared by link is readable by
        whoever holds the link.
    """,
)
