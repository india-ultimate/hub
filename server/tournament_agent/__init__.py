"""Staff tournament manager AI agent (OpenCode Go, propose/confirm, PII-masked).

Three root modules are shared, and anything may import them:

    models.py               ORM: sessions, messages, questions, proposals
    catalog.py              which models staff may pick, and their quotas
    schema.py               request/response bodies for the router

The rest is a one-way chain — each may import the next, never the reverse:

    api.py    ->  services/  ->  policy.py  ->  tools/  ->  domain/

    api.py                  the Ninja router; HTTP and SSE framing, nothing else
    services/               orchestration, and the only place anything is written
      agent.py                the turn loop: prompt, tool rounds, streaming events
      proposals.py            applying a proposal once staff hit Confirm
      skills.py               choosing which skill markdown goes in the prompt
    policy.py               which tools each phase may use, advertised and enforced
    tools/                  the surface the model is given — reads, proposals, ask_user
    domain/                 stage kinds, tournament state, phases, scheduling —
                            deterministic code that answers from the database

Two leaves sit off to the side, imported but importing nothing back:

    clients/                every outbound network call, and nothing else
    privacy/                the personal-data boundary, both directions

And two directories that are content rather than code:

    skills/                 the skill markdown itself (add a file, nothing else)
    evals/                  the offline scoring harness and its cases

`ArchitectureTests` in `server/tests/test_tournament_agent.py` enforces the chain,
so an import that breaks it fails the suite rather than rotting the layout.

Two rules worth knowing before extending:

- No tool writes to the tournament. A `propose_*` tool records an `AgentProposal`
  and returns; `services.proposals` is what applies it after a human confirms.
- Names never reach the model. `privacy.mask` guards what goes out to it,
  `privacy.display` turns ids back into names on the way to staff.
"""
