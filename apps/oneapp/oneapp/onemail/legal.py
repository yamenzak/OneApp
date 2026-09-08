"""What OneMail adds to the agreements.

Mail is the part of the product that talks to people outside the workspace, and
the part with the most third parties in the path. Two things have to be said
plainly: who carries the message, and whose domain it is.
"""

from ..onelegal.registry import clause, subprocessor

M = "OneMail"

subprocessor(
    name="Cloudflare, Inc.",
    module=M,
    purpose="Email Routing for messages arriving, and Email Sending for "
            "messages leaving; a Worker on Cloudflare's network parses each "
            "inbound message",
    data="Message headers, bodies and attachments, and the addresses of "
         "everybody on them",
    where="The storage location chosen when the workspace was created",
    safeguard="Standard Contractual Clauses and Cloudflare's data processing "
              "addendum",
    url="https://www.cloudflare.com/cloudflare-customer-dpa/",
)

clause(
    document="terms", section="modules", key="mail-addresses", module=M,
    body="""
        A workspace is given addresses on a domain we operate. You may instead
        use a domain of your own: that domain, its registration and its DNS are
        yours, and so is the responsibility for keeping the records we ask you
        to publish in place. Mail stops when they are removed.
    """, order=10,
)

clause(
    document="terms", section="modules", key="mail-limits", module=M,
    body="""
        Sending is subject to rate limits and to the policies of the networks
        that accept our mail. We may hold or refuse a message that would put the
        deliverability of everybody else's mail at risk.
    """, order=20,
)

clause(
    document="privacy", section="modules", key="mail-what", module=M,
    body="""
        OneMail holds the messages a workspace sends and receives, with their
        headers, bodies, attachments and the addresses of everybody on them,
        including people who are not your users and never signed up to anything.
        Inbound mail reaches us through Cloudflare Email Routing and is parsed
        by a Worker before it is stored; outbound mail is handed to Cloudflare
        for delivery.
    """,
)

clause(
    document="dpa", section="modules", key="mail-thirdparty", module=M,
    body="""
        Messages contain the personal data of people who are not your users.
        Your organisation is the controller of that data as much as of anything
        else in the workspace, and is responsible for having a lawful basis to
        hold it.
    """,
)

clause(
    document="aup", section="modules", key="mail-spam", module=M,
    body="""
        Do not use OneMail to send unsolicited bulk mail, to send on behalf of a
        domain you do not control, to forge a sender, or to send anything you
        could not lawfully send from your own mail server. Marketing must
        identify you and offer a way to unsubscribe.
    """,
)

clause(
    document="cookies", section="modules", key="mail-remote", module=M,
    body="""
        Remote images in a message are blocked until you ask for them, because
        loading one tells the sender you opened it. That choice is remembered on
        your device for that message only.
    """,
)
