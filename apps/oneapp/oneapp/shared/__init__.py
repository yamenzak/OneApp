"""What more than one module needs and none of them owns.

Not a Frappe module — there is no `shared` in `modules.txt` and nothing here
has a doctype. It is a plain package, and the bar for putting something in it
is that two modules already import it *and* neither is the natural owner.

    paper     the page a document or a sheet sits on — size, margins, a letter
              head — for OneDoc and OneSheet alike
    versions  one version history over three stores, because a version of a
              workbook and a version of a document turned out to be the same
              five columns
"""
