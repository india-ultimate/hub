"""A cache, shared by every app machine, for the public tournament pages.

Each page belongs to one tournament, or to the lists of all of them, and is
kept for 30 s under that tournament's version.

- Request path: `middleware` resolves the URL, `routes` says which
  tournament the page belongs to (if it's allowlisted at all), and `store`
  gives that tournament's version, read once before the view runs. A page
  stored under that version is served without touching the database;
  otherwise the view runs and a 200 GET is stored.
- Write path: `invalidation` hooks every model a public page shows. A write
  bumps its tournaments' versions in `store` once the transaction commits,
  so the next GET is fresh.
- Fail-open: every call to Redis goes through `store.safe`. An error logs
  once, counts as a miss, and skips the cache for 5 s; with Redis
  unreachable, or not configured, every page comes from the database.

Dependencies run one way: middleware -> routes -> store, and
invalidation -> store. Only `store` talks to the cache backend.
"""
