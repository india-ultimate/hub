"""The two directions of the personal-data boundary.

`mask` guards what may travel *to* the model — ids yes, names and contact details
never. `display` turns the ids back into names on the way *out* to staff. Keeping
both here makes the boundary one thing to review rather than two.
"""
