import { createQuery } from "@tanstack/solid-query";
import { createMemo, createSignal, For, Show } from "solid-js";

import {
  fetchBrackets,
  fetchCrossPool,
  fetchFieldsByTournamentId,
  fetchMatches,
  fetchPools,
  fetchPositionPools,
  fetchSwissRounds
} from "../../../queries";

const STATUS_LABELS = {
  DFT: "Draft",
  SCH: "Scheduling",
  LIV: "Live",
  COM: "Completed"
};

const STATUS_TONE = {
  DFT: "bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300",
  SCH: "bg-amber-100 text-amber-800 dark:bg-amber-900/60 dark:text-amber-300",
  LIV: "bg-emerald-100 text-emerald-800 dark:bg-emerald-900/60 dark:text-emerald-300",
  COM: "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400"
};

/** One visual language for the five stage types, reused by the grid + legend. */
const STAGE = {
  pool: {
    label: "Pool",
    dot: "bg-blue-500",
    chip: "bg-blue-50 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200"
  },
  swiss: {
    label: "Swiss",
    dot: "bg-violet-500",
    chip: "bg-violet-50 text-violet-800 dark:bg-violet-900/40 dark:text-violet-200"
  },
  cross: {
    label: "Cross pool",
    dot: "bg-teal-500",
    chip: "bg-teal-50 text-teal-800 dark:bg-teal-900/40 dark:text-teal-200"
  },
  bracket: {
    label: "Bracket",
    dot: "bg-amber-500",
    chip: "bg-amber-50 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200"
  },
  position: {
    label: "Position",
    dot: "bg-rose-500",
    chip: "bg-rose-50 text-rose-800 dark:bg-rose-900/40 dark:text-rose-200"
  }
};

const stageOf = m => {
  if (m.pool) return { ...STAGE.pool, code: `Pool ${m.pool.name}` };
  if (m.swiss_round)
    return { ...STAGE.swiss, code: `Swiss ${m.swiss_round.name}` };
  if (m.cross_pool) return { ...STAGE.cross, code: "Cross pool" };
  if (m.bracket) return { ...STAGE.bracket, code: `Bracket ${m.bracket.name}` };
  if (m.position_pool)
    return { ...STAGE.position, code: `Position ${m.position_pool.name}` };
  return null;
};

/** Timestamps are serialized with a Z suffix but are naive IST wall-clock. */
const wallClock = iso => (iso ? String(iso).slice(11, 16) : "");
const wallDate = iso => (iso ? String(iso).slice(0, 10) : "");

const Arrow = () => (
  <svg
    class="h-3 w-3 shrink-0"
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    viewBox="0 0 12 12"
  >
    <path
      stroke-linecap="round"
      stroke-linejoin="round"
      d="M2 6h8M6.5 2.5 10 6l-3.5 3.5"
    />
  </svg>
);

/** A button that hands a ready-made prompt to the agent (never mutates itself). */
const ActionButton = props => (
  <button
    type="button"
    disabled={props.disabled}
    class="inline-flex cursor-pointer items-center gap-1 rounded-md border px-2 py-1 text-[11px] font-medium transition-colors duration-150 hover:bg-black/[0.04] focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-white/[0.06]"
    style={{
      "border-color": "var(--agent-line-strong)",
      color: "var(--agent-accent)"
    }}
    onClick={() => props.onClick?.()}
  >
    {props.children}
    <Arrow />
  </button>
);

const Section = props => {
  const [open, setOpen] = createSignal(props.defaultOpen ?? true);
  return (
    <section
      class="rounded-lg border"
      style={{
        "border-color": "var(--agent-line)",
        "background-color": "var(--agent-raised)"
      }}
    >
      <button
        type="button"
        class="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
        onClick={() => setOpen(!open())}
        aria-expanded={open()}
      >
        <h3
          class="text-xs font-semibold uppercase tracking-wide"
          style={{ color: "var(--agent-ink-muted)" }}
        >
          {props.title}
        </h3>
        <Show when={props.count != null}>
          <span
            class="rounded px-1.5 text-[10px] font-semibold tabular-nums"
            style={{
              "background-color": "var(--agent-user-chip)",
              color: "var(--agent-ink-muted)"
            }}
          >
            {props.count}
          </span>
        </Show>
        <Show when={props.pill}>
          <span
            class={`rounded px-1.5 text-[10px] font-medium ${
              props.pillClass || ""
            }`}
            style={
              props.pillClass ? undefined : { color: "var(--agent-ink-muted)" }
            }
          >
            {props.pill}
          </span>
        </Show>
        <Show when={props.flag}>
          <span
            class="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500"
            aria-label="Needs attention"
          />
        </Show>
        <svg
          class={`ml-auto h-3 w-3 shrink-0 transition-transform duration-200 ${
            open() ? "rotate-180" : ""
          }`}
          style={{ color: "var(--agent-ink-muted)" }}
          aria-hidden="true"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 10 6"
        >
          <path
            stroke="currentColor"
            stroke-linecap="round"
            stroke-linejoin="round"
            stroke-width="2"
            d="m1 1 4 4 4-4"
          />
        </svg>
      </button>
      <Show when={open()}>
        <div class="px-3 pb-3">{props.children}</div>
      </Show>
    </section>
  );
};

/** A stage that isn't set up yet: one muted line + the prompt to create it. */
const NotSetUp = props => (
  <div class="flex flex-wrap items-center gap-2">
    <span class="text-xs italic" style={{ color: "var(--agent-ink-muted)" }}>
      Not set up
    </span>
    <Show when={props.action}>
      <ActionButton disabled={props.disabled} onClick={props.onAction}>
        {props.action}
      </ActionButton>
    </Show>
  </div>
);

/** seed -> team name table from a seeding map ({"1": team_id, …}). */
const SeedTable = props => (
  <table class="w-full text-left text-[11px]">
    <tbody>
      <For each={Object.keys(props.seeding || {}).sort((a, b) => a - b)}>
        {seed => (
          <tr>
            <td
              class="w-6 py-0.5 tabular-nums"
              style={{ color: "var(--agent-ink-muted)" }}
            >
              {seed}
            </td>
            <td class="truncate py-0.5" style={{ color: "var(--agent-ink)" }}>
              {props.teamsMap?.[props.seeding[seed]] ||
                `Team ${props.seeding[seed]}`}
            </td>
          </tr>
        )}
      </For>
    </tbody>
  </table>
);

/** A scheduled match in the grid, tinted + tagged by its stage. */
const MatchCell = props => {
  const st = () => stageOf(props.m);
  const cls = () =>
    "block truncate rounded px-1 py-0.5 text-[10px] " + (st()?.chip || "");
  const title = () =>
    `${st() ? st().code + " · " : ""}${props.m.name}` +
    (props.m.field?.name ? ` · ${props.m.field.name}` : "");
  return (
    <span class={cls()} title={title()}>
      {props.m.name}
    </span>
  );
};

/**
 * Read-only live view of the tournament, ordered to follow the setup workflow
 * and showing every stage type present-or-not (like the classic tab), so staff
 * see the whole structure at once. It never mutates: where a step is incomplete
 * it hands the agent a ready-made prompt, so the agent proposes and staff confirm.
 */
const TournamentRail = props => {
  const tid = () => props.tournamentId;
  const enabled = () => !!tid();
  const query = (key, fn) =>
    createQuery(
      () => [key, tid()],
      () => fn(tid()),
      {
        get enabled() {
          return enabled();
        }
      }
    );

  const poolsQuery = query("pools", fetchPools);
  const swissQuery = query("swiss-rounds", fetchSwissRounds);
  const bracketsQuery = query("brackets", fetchBrackets);
  const crossPoolQuery = query("cross-pool", fetchCrossPool);
  const positionPoolsQuery = query("position-pools", fetchPositionPools);
  const fieldsQuery = query("fields", fetchFieldsByTournamentId);
  const matchesQuery = query("matches", fetchMatches);

  // These endpoints answer with {message} instead of a list when empty.
  const listOf = q => (Array.isArray(q.data) ? q.data : []);

  const pools = () => listOf(poolsQuery);
  const swissRounds = () => listOf(swissQuery);
  const brackets = () => listOf(bracketsQuery);
  const positionPools = () => listOf(positionPoolsQuery);
  const fields = () => listOf(fieldsQuery);
  const matches = () => listOf(matchesQuery);
  const hasCrossPool = () => !!crossPoolQuery.data?.id;
  const crossPoolMatches = () => matches().filter(m => m.cross_pool);

  const scheduled = () => matches().filter(m => m.time && m.field);
  const unscheduled = () => matches().filter(m => !m.time || !m.field);
  const teamCount = () =>
    Object.keys(props.tournament?.current_seeding || {}).length;
  const tournamentSeeding = () =>
    props.tournament?.current_seeding ||
    props.tournament?.initial_seeding ||
    {};
  const status = () => props.tournament?.status;
  const hasFormat = () => pools().length > 0 || swissRounds().length > 0;

  const formatLabel = () => {
    if (swissRounds().length) return `${swissRounds().length} swiss`;
    if (pools().length)
      return `${pools().length} pool${pools().length === 1 ? "" : "s"}`;
    return "no format";
  };

  const prompt = text => props.onPrompt?.(text);

  /** The next move, derived by the server from the same phase the tool gate uses.
   *  This used to be computed here from separately fetched queries, which meant
   *  the rail could suggest a format on a tournament with no fields — something
   *  the agent now declines, because stage tools are not offered in NO_FIELDS. */
  const nextStep = createMemo(() => {
    const step = props.nextStep;
    return step
      ? { label: step.label, text: step.prompt, why: step.why }
      : null;
  });

  /** Stage types actually present in the schedule, for the legend. */
  const scheduleStages = () => {
    const seen = {};
    for (const m of scheduled()) {
      const s = stageOf(m);
      if (s) seen[s.label] = s;
    }
    return Object.values(seen);
  };

  /** Scheduled matches as one field x time grid per day. */
  const scheduleDays = () => {
    const byDay = {};
    for (const m of scheduled()) {
      const day = wallDate(m.time);
      (byDay[day] = byDay[day] || []).push(m);
    }

    let cols = fields();
    if (!cols.length) {
      const seen = {};
      for (const m of scheduled()) {
        if (m.field) seen[m.field.id] = m.field;
      }
      cols = Object.values(seen);
    }

    return Object.keys(byDay)
      .sort()
      .map(day => {
        const dayMatches = byDay[day];
        const times = [
          ...new Set(dayMatches.map(m => wallClock(m.time)))
        ].sort();
        // Indexed once per day: the grid asks for every time x field cell, and
        // scanning the day's matches for each of them is quadratic in the size
        // of the schedule.
        const bySlot = new Map();
        for (const m of dayMatches) {
          bySlot.set(`${wallClock(m.time)}|${m.field?.id}`, m);
        }
        const cellAt = (time, fieldId) => bySlot.get(`${time}|${fieldId}`);
        return { day, times, cols, cellAt };
      });
  };

  return (
    <div class="space-y-2">
      <Section title="Snapshot">
        <div class="mb-2 flex items-center gap-2">
          <span
            class={`rounded px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${
              STATUS_TONE[status()] || STATUS_TONE.DFT
            }`}
          >
            {STATUS_LABELS[status()] || status()}
          </span>
          <span
            class="truncate text-xs"
            style={{ color: "var(--agent-ink-muted)" }}
          >
            {props.tournament?.event?.title}
          </span>
        </div>

        <div class="text-xs" style={{ color: "var(--agent-ink)" }}>
          <span class="font-semibold tabular-nums">{teamCount()}</span> teams
          <span style={{ color: "var(--agent-line-strong)" }}> · </span>
          <span class="font-semibold">{formatLabel()}</span>
          <span style={{ color: "var(--agent-line-strong)" }}> · </span>
          <span class="font-semibold">CP {hasCrossPool() ? "on" : "off"}</span>
          <span style={{ color: "var(--agent-line-strong)" }}> · </span>
          <span class="font-semibold tabular-nums">{fields().length}</span>{" "}
          fields
          <span style={{ color: "var(--agent-line-strong)" }}> · </span>
          <span class="font-semibold tabular-nums">
            {matches().length}
          </span>{" "}
          matches
        </div>

        <Show when={unscheduled().length > 0}>
          <p class="mt-2 text-xs" style={{ color: "var(--agent-ink-muted)" }}>
            {unscheduled().length} of {matches().length} not scheduled
          </p>
        </Show>

        <Show when={nextStep()}>
          <div
            class="mt-3 rounded-lg border p-2.5"
            style={{
              "border-color": "rgb(37 99 235 / 0.35)",
              "background-color": "var(--agent-canvas)"
            }}
          >
            <div
              class="mb-1.5 text-[10px] font-semibold uppercase tracking-wide"
              style={{ color: "var(--agent-ink-muted)" }}
            >
              Next step
            </div>
            <ActionButton
              disabled={props.busy}
              onClick={() => prompt(nextStep().text)}
            >
              {nextStep().label}
            </ActionButton>
          </div>
        </Show>
      </Section>

      <Section
        title="Seeding"
        count={teamCount() || undefined}
        defaultOpen={teamCount() > 0}
      >
        <Show
          when={teamCount() > 0}
          fallback={
            <NotSetUp
              disabled={props.busy}
              action="Set seeding"
              onAction={() =>
                prompt("Propose seeding for the registered teams")
              }
            />
          }
        >
          <SeedTable seeding={tournamentSeeding()} teamsMap={props.teamsMap} />
        </Show>
      </Section>

      <Section
        title="Initial stage"
        pill={
          hasFormat() ? (swissRounds().length ? "Swiss" : "Pools") : undefined
        }
        flag={!hasFormat() && teamCount() > 0}
      >
        <Show
          when={hasFormat()}
          fallback={
            <NotSetUp
              disabled={props.busy}
              action={teamCount() > 0 ? "Recommend a format" : undefined}
              onAction={() =>
                prompt(
                  "Recommend pools or Swiss groups for the registered teams"
                )
              }
            />
          }
        >
          <Show when={pools().length > 0}>
            <div class="grid grid-cols-2 gap-3">
              <For each={pools()}>
                {pool => (
                  <div>
                    <div
                      class="mb-1 text-xs font-semibold"
                      style={{ color: "var(--agent-ink)" }}
                    >
                      Pool {pool.name}
                    </div>
                    <SeedTable
                      seeding={pool.initial_seeding}
                      teamsMap={props.teamsMap}
                    />
                  </div>
                )}
              </For>
            </div>
          </Show>
          <Show when={swissRounds().length > 0}>
            <For each={swissRounds()}>
              {round => (
                <div class="mb-2 last:mb-0">
                  <div
                    class="mb-1 text-xs font-semibold"
                    style={{ color: "var(--agent-ink)" }}
                  >
                    Swiss {round.name}
                    <span
                      class="ml-1 font-normal"
                      style={{ color: "var(--agent-ink-muted)" }}
                    >
                      · round {round.current_round}/{round.num_rounds}
                    </span>
                  </div>
                  <SeedTable
                    seeding={round.initial_seeding}
                    teamsMap={props.teamsMap}
                  />
                </div>
              )}
            </For>
          </Show>
        </Show>
      </Section>

      <Section
        title="Cross pool"
        pill={hasCrossPool() ? "On" : "Off"}
        pillClass={
          hasCrossPool()
            ? "bg-teal-50 text-teal-800 dark:bg-teal-900/40 dark:text-teal-200"
            : "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400"
        }
        count={hasCrossPool() ? crossPoolMatches().length : undefined}
        defaultOpen={hasCrossPool()}
      >
        <Show
          when={hasCrossPool()}
          fallback={
            <NotSetUp
              disabled={props.busy}
              action={pools().length > 1 ? "Set up cross pool" : undefined}
              onAction={() =>
                prompt("Set up the cross pool matches after pools")
              }
            />
          }
        >
          <p class="text-xs" style={{ color: "var(--agent-ink)" }}>
            {crossPoolMatches().length} cross-pool match
            {crossPoolMatches().length === 1 ? "" : "es"}
          </p>
        </Show>
      </Section>

      <Section
        title="Brackets"
        count={brackets().length || undefined}
        defaultOpen={brackets().length > 0}
      >
        <Show
          when={brackets().length > 0}
          fallback={
            <NotSetUp
              disabled={props.busy}
              action={hasFormat() ? "Draw a bracket" : undefined}
              onAction={() =>
                prompt(
                  "Set up a 1-4 (or 1-8) bracket that includes the 3rd-place push-in, not just two semis and a final"
                )
              }
            />
          }
        >
          <div class="space-y-2">
            <For each={brackets()}>
              {b => (
                <div>
                  <div
                    class="mb-1 text-xs font-semibold"
                    style={{ color: "var(--agent-ink)" }}
                  >
                    Bracket {b.name}
                  </div>
                  <Show when={b.initial_seeding}>
                    <SeedTable
                      seeding={b.initial_seeding}
                      teamsMap={props.teamsMap}
                    />
                  </Show>
                </div>
              )}
            </For>
          </div>
        </Show>
      </Section>

      <Section
        title="Position pools"
        count={positionPools().length || undefined}
        defaultOpen={positionPools().length > 0}
      >
        <Show
          when={positionPools().length > 0}
          fallback={
            <NotSetUp
              disabled={props.busy}
              action={hasFormat() ? "Add position pools" : undefined}
              onAction={() =>
                prompt("Set up position pools for final rankings")
              }
            />
          }
        >
          <div class="space-y-2">
            <For each={positionPools()}>
              {pp => (
                <div>
                  <div
                    class="mb-1 text-xs font-semibold"
                    style={{ color: "var(--agent-ink)" }}
                  >
                    Position pool {pp.name}
                  </div>
                  <Show when={pp.initial_seeding}>
                    <SeedTable
                      seeding={pp.initial_seeding}
                      teamsMap={props.teamsMap}
                    />
                  </Show>
                </div>
              )}
            </For>
          </div>
        </Show>
      </Section>

      <Section
        title="Fields"
        count={fields().length || undefined}
        flag={fields().length === 0 && matches().length > 0}
      >
        <Show
          when={fields().length > 0}
          fallback={
            <NotSetUp
              disabled={props.busy}
              action="Add a field"
              onAction={() => prompt("Add a field to this tournament")}
            />
          }
        >
          <ul class="space-y-1">
            <For each={fields()}>
              {f => (
                <li class="flex items-center gap-2 text-xs">
                  <span style={{ color: "var(--agent-ink)" }}>{f.name}</span>
                  <Show when={f.is_broadcasted}>
                    <span class="rounded bg-blue-100 px-1 text-[10px] font-medium text-blue-800 dark:bg-blue-900/60 dark:text-blue-300">
                      Broadcast
                    </span>
                  </Show>
                </li>
              )}
            </For>
          </ul>
        </Show>
      </Section>

      <Section
        title="Schedule"
        count={`${scheduled().length}/${matches().length}`}
        flag={unscheduled().length > 0}
        defaultOpen={scheduled().length > 0}
      >
        <Show when={unscheduled().length > 0}>
          <div class="mb-3 flex flex-wrap items-center gap-2">
            <span class="text-xs" style={{ color: "var(--agent-ink-muted)" }}>
              {unscheduled().length} not scheduled
            </span>
            <Show when={fields().length > 0}>
              <ActionButton
                disabled={props.busy}
                onClick={() =>
                  prompt(
                    "Recommend a schedule for the matches that aren't scheduled yet"
                  )
                }
              >
                Schedule them
              </ActionButton>
            </Show>
          </div>
        </Show>

        <Show
          when={scheduled().length > 0}
          fallback={
            <Show when={unscheduled().length === 0}>
              <p
                class="text-xs italic"
                style={{ color: "var(--agent-ink-muted)" }}
              >
                Nothing to schedule yet.
              </p>
            </Show>
          }
        >
          <div class="space-y-3">
            <Show when={scheduleStages().length > 0}>
              <div class="flex flex-wrap gap-x-3 gap-y-1">
                <For each={scheduleStages()}>
                  {s => (
                    <span
                      class="flex items-center gap-1 text-[10px]"
                      style={{ color: "var(--agent-ink-muted)" }}
                    >
                      <span class={`h-2 w-2 rounded-full ${s.dot}`} />
                      {s.label}
                    </span>
                  )}
                </For>
              </div>
            </Show>

            <For each={scheduleDays()}>
              {day => (
                <div>
                  <div
                    class="mb-1 text-[11px] font-semibold"
                    style={{ color: "var(--agent-ink-muted)" }}
                  >
                    {day.day}
                  </div>
                  <div class="overflow-x-auto">
                    <table class="w-full border-collapse text-[11px]">
                      <thead>
                        <tr>
                          <th class="w-10" />
                          <For each={day.cols}>
                            {f => (
                              <th
                                class="border-b px-1.5 py-1 text-left font-medium"
                                style={{
                                  "border-color": "var(--agent-line)",
                                  color: "var(--agent-ink-muted)"
                                }}
                              >
                                {f.name}
                              </th>
                            )}
                          </For>
                        </tr>
                      </thead>
                      <tbody>
                        <For each={day.times}>
                          {time => (
                            <tr>
                              <td
                                class="py-1 pr-1.5 align-top tabular-nums"
                                style={{ color: "var(--agent-ink-muted)" }}
                              >
                                {time}
                              </td>
                              <For each={day.cols}>
                                {f => (
                                  <td
                                    class="border-t px-1 py-1 align-top"
                                    style={{
                                      "border-color": "var(--agent-line)"
                                    }}
                                  >
                                    <Show
                                      when={day.cellAt(time, f.id)}
                                      fallback={
                                        <span
                                          style={{
                                            color: "var(--agent-line-strong)"
                                          }}
                                        >
                                          ·
                                        </span>
                                      }
                                    >
                                      <MatchCell m={day.cellAt(time, f.id)} />
                                    </Show>
                                  </td>
                                )}
                              </For>
                            </tr>
                          )}
                        </For>
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </For>
          </div>
        </Show>
      </Section>

      <Show when={status() === "LIV" || status() === "COM"}>
        <Section title="Standings" defaultOpen={false}>
          <Show
            when={pools().length > 0}
            fallback={
              <p
                class="text-xs italic"
                style={{ color: "var(--agent-ink-muted)" }}
              >
                No pool standings yet.
              </p>
            }
          >
            <For each={pools()}>
              {pool => (
                <div class="mb-2 last:mb-0">
                  <div
                    class="mb-1 text-xs font-semibold"
                    style={{ color: "var(--agent-ink)" }}
                  >
                    Pool {pool.name}
                  </div>
                  <table class="w-full text-left text-[11px]">
                    <tbody>
                      <For
                        each={Object.entries(pool.results || {}).sort(
                          (a, b) => (a[1].rank || 99) - (b[1].rank || 99)
                        )}
                      >
                        {([teamId, res]) => (
                          <tr>
                            <td
                              class="w-5 py-0.5 tabular-nums"
                              style={{ color: "var(--agent-ink-muted)" }}
                            >
                              {res.rank}
                            </td>
                            <td
                              class="truncate py-0.5"
                              style={{ color: "var(--agent-ink)" }}
                            >
                              {props.teamsMap?.[teamId] || `Team ${teamId}`}
                            </td>
                            <td
                              class="w-10 py-0.5 text-right tabular-nums"
                              style={{ color: "var(--agent-ink-muted)" }}
                            >
                              {res.wins}-{res.losses}
                            </td>
                          </tr>
                        )}
                      </For>
                    </tbody>
                  </table>
                </div>
              )}
            </For>
          </Show>
        </Section>
      </Show>
    </div>
  );
};

export default TournamentRail;
