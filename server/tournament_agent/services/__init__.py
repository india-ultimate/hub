"""Orchestration: the agent turn loop, the proposal apply path, and skill selection.

These coordinate the other layers — `clients` for the model call, `tools` for what
the model may do, `domain` for tournament computation — and own the write path.
"""
