import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import {
  createEffect,
  createMemo,
  createSignal,
  For,
  onCleanup,
  Show
} from "solid-js";

import {
  clearTournamentAgentHistory,
  confirmTournamentAgentProposal,
  fetchBrackets,
  fetchCrossPool,
  fetchFieldsByTournamentId,
  fetchMatches,
  fetchPools,
  fetchSwissRounds,
  fetchTeams,
  fetchTournamentAgentHistory,
  fetchTournamentAgentModels,
  fetchTournaments,
  rejectTournamentAgentProposal,
  setTournamentAgentModel,
  streamTournamentAgentAnswer,
  streamTournamentAgentMessage
} from "../../../queries";
import { useStore } from "../../../store";
import { filterManageableTournaments } from "../../../utils";
import StyledMarkdown from "../../StyledMarkdown";
import ModelPicker from "./ModelPicker";
import ProposalCard from "./ProposalCard";
import QuestionCard from "./QuestionCard";
import QuestionSnapshot from "./QuestionSnapshot";
import ToolEventTimeline from "./ToolEventTimeline";
import TournamentRail from "./TournamentRail";

/**
 * Chat-scale markdown classes for agent replies, all Tailwind. StyledMarkdown's
 * default map styles h1/h2 as large centered blue page titles (right for
 * rules/help pages, wrong inside a conversation); this map keeps a tight
 * inline-scale rhythm. Keys are CSS selectors applied via querySelectorAll, so
 * order matters: compound keys ("li > p", "pre code") run after their base tag
 * and override it — that "li > p" reset is what keeps loose (blank-line-
 * separated) bullet lists from gaining a full paragraph gap between items.
 *
 * Kept inline rather than in a sibling module: solid-hot-loader wraps every .js
 * under components/ as a component and drops named exports, so a constants-only
 * module can't be imported by name here.
 */
const agentClassMap = {
  a: "font-medium text-blue-700 underline underline-offset-2 hover:no-underline dark:text-blue-300",
  p: "mb-1.5 last:mb-0",
  h1: "text-base font-semibold mt-2.5 mb-1 first:mt-0",
  h2: "text-[0.9375rem] font-semibold mt-2.5 mb-1 first:mt-0",
  h3: "text-sm font-semibold mt-2 mb-0.5 first:mt-0",
  ol: "mb-1.5 ml-5 list-decimal space-y-0.5 last:mb-0",
  ul: "mb-1.5 ml-5 list-disc space-y-0.5 last:mb-0",
  li: "leading-snug",
  blockquote:
    "mb-1.5 border-l-2 pl-3 italic opacity-80 border-[color:var(--agent-line-strong)] last:mb-0",
  hr: "my-3 border-t border-[color:var(--agent-line)]",
  table:
    "mb-1.5 w-full table-auto border-collapse text-left text-[0.8125rem] last:mb-0",
  thead: "border-b border-[color:var(--agent-line-strong)]",
  th: "px-2 py-1 font-semibold",
  "tbody tr": "border-b border-[color:var(--agent-line)] last:border-0",
  "tbody td": "px-2 py-1 align-top",
  pre: "mb-1.5 overflow-x-auto rounded-lg bg-[color:var(--agent-user-chip)] p-3 text-[0.8125rem] leading-normal last:mb-0",
  code: "rounded bg-[color:var(--agent-user-chip)] px-1 py-0.5 text-[0.8125em]",
  "pre code": "bg-transparent p-0 text-[0.8125rem]",
  "li > p": "mb-0"
};

const EVENT_KIND = { MXD: "mixed", OPN: "open", WMN: "women's" };

const asList = data => (Array.isArray(data) ? data : []);

const ymd = value => (value ? String(value).slice(0, 10) : "");

const plural = (count, one, many = `${one}s`) =>
  `${count} ${count === 1 ? one : many}`;

const SCHEDULE_PLAN_TOOLS = new Set([
  "propose_recommended_schedule",
  "propose_bulk_schedule",
  "propose_shift_schedule"
]);

const assignmentMatchIds = payload =>
  new Set(
    (payload?.assignments || [])
      .map(row => row?.match_id)
      .filter(id => id != null)
  );

const keepLiveProposals = (prev, incoming) => {
  if (!SCHEDULE_PLAN_TOOLS.has(incoming.tool_name)) {
    return [...prev, incoming];
  }
  const newIds = assignmentMatchIds(incoming.payload);
  if (!newIds.size) return [...prev, incoming];
  return [
    ...prev.filter(proposal => {
      if (!SCHEDULE_PLAN_TOOLS.has(proposal.tool_name)) return true;
      const ids = assignmentMatchIds(proposal.payload);
      for (const id of ids) {
        if (newIds.has(id)) return false;
      }
      return true;
    }),
    incoming
  ];
};

const confirmFixPrompt = (proposal, error) =>
  [
    `Staff could not Confirm proposal #${proposal.id} (${proposal.tool_name}: ${
      proposal.summary || "untitled"
    }).`,
    `Apply error: ${error}`,
    "Call list_proposals, read current tournament state, then call the matching propose_* tool with a corrected payload.",
    "Re-proposing retires this card. Do not reuse the failed payload. Do not ask staff to reject it first."
  ].join(" ");

/**
 * Starter chips for an empty chat. Built from this tournament so we never
 * offer "16 mixed teams on 3 fields" when the event is 8 teams on 2.
 */
const buildStarterPrompts = s => {
  const kind = EVENT_KIND[s.eventType];
  const teamPhrase =
    s.teamCount > 0
      ? `the ${s.teamCount} registered${kind ? ` ${kind}` : ""} ${
          s.teamCount === 1 ? "team" : "teams"
        }`
      : "the registered teams";
  const fieldPhrase =
    s.fieldCount > 0 ? ` on ${plural(s.fieldCount, "field")}` : "";
  const datePhrase =
    s.startDate && s.endDate && s.startDate !== s.endDate
      ? ` from ${s.startDate} to ${s.endDate}`
      : s.startDate
      ? ` on ${s.startDate}`
      : "";

  if (s.status === "COM") {
    return [
      {
        title: "Summarise the event",
        prompt: "Summarise how this tournament was set up and how it finished"
      }
    ];
  }

  if (s.teamCount === 0) {
    return [
      {
        title: "What's in place?",
        prompt:
          "Summarise this tournament: teams, stages, fields, and what's still missing"
      }
    ];
  }

  const items = [];
  const live = s.status === "LIV";
  const hasFormat = s.poolCount > 0 || s.swissCount > 0;

  if (!live && !hasFormat) {
    if (s.fieldCount === 0) {
      items.push({
        title: "Add fields first",
        prompt: `This event has ${teamPhrase}${datePhrase} but no fields yet. Ask me how many fields to add (2, 3, or 4), then propose them.`
      });
    }
    items.push({
      title: `Set up ${plural(s.teamCount, "team")}`,
      prompt:
        s.fieldCount === 0
          ? `Set up this tournament for ${teamPhrase}${datePhrase}. Start with fields, then the format — don't schedule yet.`
          : `Set up this tournament for ${teamPhrase}${fieldPhrase}${datePhrase}. Recommend a format.`
    });
    items.push({
      title: "Recommend a format",
      prompt: `Recommend snake-seeded pools (or Swiss) for ${teamPhrase}`
    });
    return items;
  }

  if (!live && s.fieldCount === 0) {
    items.push({
      title: "Add a field",
      prompt: "Add a playing field so matches can be scheduled"
    });
  }

  if (s.unscheduledCount > 0 && s.fieldCount > 0) {
    items.push({
      title: `Schedule ${plural(s.unscheduledCount, "match", "matches")}`,
      prompt: `Recommend a schedule for the ${plural(
        s.unscheduledCount,
        "match",
        "matches"
      )} that don't have a time or field yet. Use 75 minute games${datePhrase}.`
    });
  }

  if (!live && s.poolCount > 0 && !s.hasCrossPool) {
    items.push({
      title: "Add cross pool",
      prompt: "Set up the cross pool stage and its matches after pools"
    });
  }

  if (!live && hasFormat && s.bracketCount === 0 && s.teamCount >= 4) {
    items.push({
      title: "Add brackets",
      prompt:
        "Set up 1-4 / 5-8 brackets with 3rd-place push-in games, not just semis and a final"
    });
  }

  if (s.status === "SCH" && s.matchCount > 0 && s.unscheduledCount === 0) {
    items.push({
      title: "Start the tournament",
      prompt: "Start the tournament and assign teams from seeding"
    });
  }

  if (live) {
    items.push({
      title: "Who still needs a score?",
      prompt: "Which matches still need a score?"
    });
    items.push({
      title: "Show standings",
      prompt: "Show the current standings"
    });
    if (s.unscheduledCount > 0) {
      items.push({
        title: "Unscheduled matches",
        prompt: "Show the matches that still have no time or field"
      });
    }
  }

  return items.slice(0, 4);
};

/** A flying disc seen in slight perspective — the sport's mark, not a star. */
const AgentMark = props => (
  <svg
    class={props.class}
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
    xmlns="http://www.w3.org/2000/svg"
  >
    <ellipse
      cx="12"
      cy="12"
      rx="9.5"
      ry="5.5"
      fill="currentColor"
      opacity="0.16"
    />
    <ellipse
      cx="12"
      cy="12"
      rx="9.5"
      ry="5.5"
      fill="none"
      stroke="currentColor"
      stroke-width="1.6"
    />
    <ellipse
      cx="12"
      cy="12"
      rx="5"
      ry="2.7"
      fill="none"
      stroke="currentColor"
      stroke-width="1.3"
      opacity="0.85"
    />
  </svg>
);

const EmptyState = props => {
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
  const fieldsQuery = query("fields", fetchFieldsByTournamentId);
  const matchesQuery = query("matches", fetchMatches);

  const prompts = createMemo(() => {
    const tournament = props.tournament;
    const teams = tournament?.teams;
    const teamCount =
      Array.isArray(teams) && teams.length
        ? teams.length
        : Object.keys(tournament?.current_seeding || {}).length;
    const matches = asList(matchesQuery.data);
    return buildStarterPrompts({
      teamCount,
      fieldCount: asList(fieldsQuery.data).length,
      poolCount: asList(poolsQuery.data).length,
      swissCount: asList(swissQuery.data).length,
      bracketCount: asList(bracketsQuery.data).length,
      hasCrossPool: !!crossPoolQuery.data?.id,
      matchCount: matches.length,
      unscheduledCount: matches.filter(m => !m.time || !m.field).length,
      status: tournament?.status,
      eventType: tournament?.event?.type,
      startDate: ymd(tournament?.event?.start_date),
      endDate: ymd(tournament?.event?.end_date)
    });
  });

  const teamCount = () => {
    const teams = props.tournament?.teams;
    if (Array.isArray(teams) && teams.length) return teams.length;
    return Object.keys(props.tournament?.current_seeding || {}).length;
  };

  const hasFormat = () =>
    asList(poolsQuery.data).length > 0 || asList(swissQuery.data).length > 0;

  return (
    <div class="flex h-full flex-col items-center justify-center px-6 py-10">
      <AgentMark
        class="mb-4 h-8 w-8"
        style={{ color: "var(--agent-accent)" }}
      />
      <h2
        class="mb-1 font-serif text-2xl"
        style={{ color: "var(--agent-ink)" }}
      >
        {hasFormat() ? "What should we do next?" : "What are we setting up?"}
      </h2>
      <p
        class="mb-6 max-w-sm text-center text-sm"
        style={{ color: "var(--agent-ink-muted)" }}
      >
        {teamCount() > 0
          ? `${plural(
              teamCount(),
              "team"
            )} registered. Nothing changes until you confirm a proposal.`
          : "Ask for pools, brackets, or a schedule. Nothing changes until you confirm a proposal."}
      </p>
      <div class="grid w-full max-w-lg grid-cols-1 gap-2 sm:grid-cols-2">
        <For each={prompts()}>
          {item => (
            <button
              type="button"
              class="cursor-pointer rounded-lg border p-2.5 text-left transition-colors duration-150 hover:border-[color:var(--agent-line-strong)] focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-40"
              style={{
                "border-color": "var(--agent-line)",
                "background-color": "var(--agent-raised)"
              }}
              disabled={props.disabled}
              onClick={() => props.onPick(item.prompt)}
            >
              <div
                class="text-xs font-medium leading-tight"
                style={{ color: "var(--agent-ink)" }}
              >
                {item.title}
              </div>
              <div
                class="mt-1 line-clamp-2 text-[11px] leading-tight"
                style={{ color: "var(--agent-ink-muted)" }}
              >
                {item.prompt}
              </div>
            </button>
          )}
        </For>
      </div>
    </div>
  );
};

const UserMessage = props => (
  <div class="flex justify-end">
    <div
      class="max-w-[85%] rounded-2xl rounded-br-sm px-3.5 py-2 text-sm"
      style={{
        "background-color": "var(--agent-user-chip)",
        color: "var(--agent-ink)"
      }}
    >
      <p class="whitespace-pre-wrap">{props.content}</p>
    </div>
  </div>
);

/** Bubbleless assistant turn: the reply is the page, not a chat bubble. */
const AssistantMessage = props => (
  <div class="flex gap-3">
    <AgentMark
      class="mt-0.5 h-4 w-4 shrink-0"
      style={{ color: "var(--agent-accent)" }}
    />
    <div class="min-w-0 flex-1">
      <Show when={(props.toolEvents || []).length > 0}>
        <ToolEventTimeline events={props.toolEvents} />
      </Show>
      <Show when={props.content}>
        <div
          class="text-[0.9375rem] leading-normal text-[color:var(--agent-ink)]"
          classList={{ "agent-caret": props.streaming }}
        >
          <StyledMarkdown
            markdown={props.content}
            classMap={agentClassMap}
            headingIds={false}
          />
        </div>
      </Show>
      <Show when={props.children}>
        <div class="mt-3">{props.children}</div>
      </Show>
    </div>
  </div>
);

const TournamentAgentTab = props => {
  const [store] = useStore();
  const queryClient = useQueryClient();
  const [localTournamentId, setLocalTournamentId] = createSignal(
    props.tournamentId || null
  );
  const [draft, setDraft] = createSignal("");
  const [modelId, setModelId] = createSignal("");
  const [optimisticUserMessages, setOptimisticUserMessages] = createSignal([]);
  const [isAwaitingAgent, setIsAwaitingAgent] = createSignal(false);
  const [streamingText, setStreamingText] = createSignal("");
  const [streamingTools, setStreamingTools] = createSignal([]);
  const [streamError, setStreamError] = createSignal("");
  const [confirmErrors, setConfirmErrors] = createSignal({});
  const [confirmingClear, setConfirmingClear] = createSignal(false);
  const [liveProposals, setLiveProposals] = createSignal([]);
  let messagesContainerRef;
  let messagesEndRef;
  let textareaRef;
  let abortController;
  let pinnedToBottom = true;

  createEffect(() => {
    if (props.tournamentId) setLocalTournamentId(props.tournamentId);
  });

  const tournamentsQuery = createQuery(() => ["tournaments"], fetchTournaments);
  const manageableTournaments = () =>
    filterManageableTournaments(tournamentsQuery.data, store?.data);
  const teamsQuery = createQuery(() => ["teams"], fetchTeams);
  const modelsQuery = createQuery(
    () => ["tournament-agent", "models"],
    fetchTournamentAgentModels
  );

  createEffect(() => {
    const data = modelsQuery.data;
    if (data?.default_model_id && !modelId()) setModelId(data.default_model_id);
  });

  const historyQuery = createQuery(
    () => ["tournament-agent", "history", localTournamentId()],
    () => fetchTournamentAgentHistory(localTournamentId()),
    {
      get enabled() {
        return !!localTournamentId();
      }
    }
  );

  createEffect(() => {
    const hist = historyQuery.data;
    if (hist?.model_id) setModelId(hist.model_id);
  });

  const tournament = createMemo(() =>
    (tournamentsQuery.data || []).find(t => t.id === localTournamentId())
  );

  const teamsMap = createMemo(() => {
    const map = {};
    for (const team of teamsQuery.data || []) map[team.id] = team.name;
    return map;
  });

  /** Seed -> team name, for reading proposals without decoding ids. */
  const seedToTeamName = seed => {
    const seeding = tournament()?.current_seeding || {};
    const teamId = seeding[String(seed)] ?? seeding[seed];
    return teamId ? teamsMap()[teamId] : undefined;
  };

  const fieldName = fieldId => {
    const fields = queryClient.getQueryData(["fields", localTournamentId()]);
    return (Array.isArray(fields) ? fields : []).find(f => f.id === fieldId)
      ?.name;
  };

  const invalidateTournamentQueries = () => {
    const tid = localTournamentId();
    if (!tid) return;
    for (const key of [
      "pools",
      "brackets",
      "matches",
      "swiss-rounds",
      "cross-pool",
      "position-pools",
      "fields"
    ]) {
      queryClient.invalidateQueries({ queryKey: [key, tid] });
    }
    queryClient.invalidateQueries({ queryKey: ["tournaments"] });
    queryClient.invalidateQueries({
      queryKey: ["tournament-agent", "history", tid]
    });
  };

  const confirmMutation = createMutation({
    mutationFn: proposalId => confirmTournamentAgentProposal(proposalId),
    onSuccess: (_data, proposalId) => {
      setConfirmErrors(prev => {
        const next = { ...prev };
        delete next[proposalId];
        return next;
      });
      setLiveProposals([]);
      invalidateTournamentQueries();
      historyQuery.refetch();
    },
    onError: (err, proposalId) => {
      // 400 means the plan cannot be applied. Retrying Confirm with the
      // same payload will fail the same way — keep the card and show why.
      setConfirmErrors(prev => ({
        ...prev,
        [proposalId]: err?.message || "Could not apply this proposal"
      }));
      historyQuery.refetch();
    }
  });

  const rejectMutation = createMutation({
    mutationFn: proposalId => rejectTournamentAgentProposal(proposalId),
    onSuccess: () => {
      setLiveProposals([]);
      historyQuery.refetch();
    }
  });

  const clearMutation = createMutation({
    mutationFn: () => clearTournamentAgentHistory(localTournamentId()),
    onSuccess: () => {
      setOptimisticUserMessages([]);
      setIsAwaitingAgent(false);
      setConfirmingClear(false);
      historyQuery.refetch();
    }
  });

  const setModelMutation = createMutation({
    mutationFn: mid =>
      setTournamentAgentModel({
        tournament_id: localTournamentId(),
        model_id: mid
      }),
    onSuccess: () => historyQuery.refetch()
  });

  const inputLocked = () => isAwaitingAgent() || clearMutation.isPending;

  const displayMessages = () => {
    const server = historyQuery.data?.messages || [];
    const optimistic = optimisticUserMessages();
    if (!optimistic.length) return server;
    const serverUserTexts = new Set(
      server.filter(m => m.role === "user").map(m => (m.content || "").trim())
    );
    return [
      ...server,
      ...optimistic.filter(m => !serverUserTexts.has((m.content || "").trim()))
    ];
  };

  const pendingProposals = () => {
    const fromHistory = historyQuery.data?.pending_proposals || [];
    const live = liveProposals();
    if (!live.length) return fromHistory;
    // A new turn's live cards must not hide still-pending cards from earlier
    // turns — staff need every Confirm in view at once.
    const byId = new Map(fromHistory.map(p => [p.id, p]));
    for (const p of live) byId.set(p.id, p);
    return [...byId.values()];
  };

  const proposalIdsOnMessage = msg => {
    const ids = [];
    for (const event of msg.payload?.tool_events || []) {
      if (event.proposal_id) ids.push(event.proposal_id);
    }
    for (const id of msg.payload?.proposal_ids || []) ids.push(id);
    return ids;
  };

  const proposalsForMessage = msg => {
    const ids = new Set(proposalIdsOnMessage(msg));
    return pendingProposals().filter(p => ids.has(p.id));
  };

  const unattachedProposals = () => {
    const attached = new Set();
    for (const msg of displayMessages()) {
      for (const id of proposalIdsOnMessage(msg)) attached.add(id);
    }
    // Live cards render on the in-flight assistant message.
    for (const proposal of liveProposals()) attached.add(proposal.id);
    return pendingProposals().filter(p => !attached.has(p.id));
  };

  const scrollToBottom = (behavior = "smooth") => {
    requestAnimationFrame(() => {
      if (messagesEndRef)
        messagesEndRef.scrollIntoView({ behavior, block: "end" });
    });
  };

  /** Streaming must not yank the view if staff scrolled up to read. */
  const onScroll = () => {
    if (!messagesContainerRef) return;
    const { scrollTop, scrollHeight, clientHeight } = messagesContainerRef;
    pinnedToBottom = scrollHeight - scrollTop - clientHeight < 60;
  };

  createEffect(() => {
    displayMessages().length;
    historyQuery.dataUpdatedAt;
    scrollToBottom("auto");
  });

  createEffect(() => {
    streamingText();
    streamingTools().length;
    if (pinnedToBottom) scrollToBottom("auto");
  });

  const autosize = () => {
    if (!textareaRef) return;
    textareaRef.style.height = "auto";
    textareaRef.style.height = `${Math.min(textareaRef.scrollHeight, 200)}px`;
  };

  const beginTurn = text => {
    setStreamError("");
    setStreamingText("");
    setStreamingTools([]);
    setLiveProposals([]);
    setOptimisticUserMessages(prev => [
      ...prev,
      {
        id: `opt-${Date.now()}`,
        role: "user",
        content: text,
        message_kind: "text",
        optimistic: true
      }
    ]);
    setIsAwaitingAgent(true);
    pinnedToBottom = true;
    scrollToBottom("auto");
  };

  const endTurn = async () => {
    try {
      await historyQuery.refetch();
      setOptimisticUserMessages([]);
    } finally {
      setIsAwaitingAgent(false);
      setStreamingText("");
      setStreamingTools([]);
      setLiveProposals([]);
      abortController = undefined;
    }
  };

  /** Apply one SSE event to the in-flight turn. */
  const handleEvent = ({ name, data }) => {
    if (name === "text_delta") {
      setStreamingText(prev => prev + data.text);
    } else if (name === "text_replace") {
      setStreamingText(data.text);
    } else if (name === "tool_start") {
      setStreamingTools(prev => [
        ...prev,
        {
          name: data.name,
          arguments: data.arguments,
          status: "running",
          summary: ""
        }
      ]);
    } else if (name === "tool_end") {
      setStreamingTools(prev =>
        prev.map((t, i) => (i === data.index ? { ...t, ...data } : t))
      );
    } else if (name === "proposal") {
      setLiveProposals(prev => keepLiveProposals(prev, data.proposal));
    } else if (name === "error") {
      setStreamError(data.message || "The agent failed");
    }
  };

  const runStream = async (starter, fallbackText) => {
    abortController = new AbortController();
    try {
      await starter(abortController.signal);
      await endTurn();
    } catch (err) {
      const aborted = err?.name === "AbortError";
      setOptimisticUserMessages(prev =>
        prev.filter(m => !(m.optimistic && m.content === fallbackText))
      );
      setIsAwaitingAgent(false);
      abortController = undefined;
      if (aborted) {
        // The turn ran server-side regardless; show whatever it committed.
        await historyQuery.refetch();
        setOptimisticUserMessages([]);
      } else {
        setStreamError(err?.message || "Failed to reach the agent");
        if (fallbackText) setDraft(fallbackText);
      }
      setStreamingText("");
      setStreamingTools([]);
    }
  };

  /** Server-derived next move. Deliberately hidden when anything else is
   *  already asking for the user's attention, or when they are mid-thought. */
  const nextStep = createMemo(() => {
    const step = historyQuery.data?.next_step;
    if (!step) return null;
    if (inputLocked() || isAwaitingAgent()) return null;
    if (draft().trim()) return null;
    if (pendingProposals().length > 0) return null;
    if (historyQuery.data?.pending_question) return null;
    return step;
  });

  const handleSend = async message => {
    if (inputLocked()) return;
    const text = (message ?? draft()).trim();
    if (!text || !localTournamentId()) return;

    setDraft("");
    autosize();
    beginTurn(text);
    await runStream(
      signal =>
        streamTournamentAgentMessage({
          tournament_id: localTournamentId(),
          message: text,
          model_id: modelId() || undefined,
          signal,
          onEvent: handleEvent
        }),
      text
    );
  };

  const proposalCardProps = proposal => {
    const error = confirmErrors()[proposal.id] || proposal.last_error || "";
    return {
      proposal,
      confirming: confirmMutation.isPending,
      rejecting: rejectMutation.isPending,
      disabled: inputLocked(),
      error,
      seedToTeamName,
      fieldName,
      onConfirm: () => {
        setConfirmErrors(prev => {
          const next = { ...prev };
          delete next[proposal.id];
          return next;
        });
        confirmMutation.mutate(proposal.id);
      },
      onReject: () => rejectMutation.mutate(proposal.id),
      onAskFix: error
        ? () => handleSend(confirmFixPrompt(proposal, error))
        : undefined
    };
  };

  const handleAnswer = async body => {
    if (inputLocked()) return;
    const q = historyQuery.data?.pending_question;
    if (!q) return;

    const labels = (q.options || [])
      .filter(o => (body.selected_ids || []).includes(o.id))
      .map(o => o.label);
    const answerText = body.skip
      ? "(skipped)"
      : [labels.join(", "), body.other_text].filter(Boolean).join(" — ") ||
        "Answered";

    beginTurn(answerText);
    await runStream(
      signal =>
        streamTournamentAgentAnswer({
          questionId: q.id,
          body,
          signal,
          onEvent: handleEvent
        }),
      answerText
    );
  };

  const handleStop = () => {
    abortController?.abort();
  };

  const handleModelChange = mid => {
    if (inputLocked()) return;
    setModelId(mid);
    if (localTournamentId()) setModelMutation.mutate(mid);
  };

  onCleanup(() => {
    abortController?.abort();
    setIsAwaitingAgent(false);
  });

  const isStreamingReply = () =>
    isAwaitingAgent() && (streamingText() || streamingTools().length > 0);

  return (
    <div
      class="agent-surface flex h-full min-h-0 flex-col gap-3 overflow-hidden rounded-2xl border p-4 leading-snug sm:p-5 lg:flex-row lg:gap-5"
      style={{
        "background-color": "var(--agent-canvas)",
        "border-color": "var(--agent-line)"
      }}
    >
      <div class="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        {/* Quiet chrome: identity and controls, no card frame. */}
        <div
          class="flex shrink-0 flex-wrap items-center gap-2 border-b px-0.5 pb-3.5"
          style={{ "border-color": "var(--agent-line)" }}
        >
          <select
            id="tournament-agent-tournament"
            aria-label="Tournament"
            class="h-9 min-w-[10rem] max-w-full flex-1 cursor-pointer rounded-lg border-0 bg-transparent px-2 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
            style={{ color: "var(--agent-ink)" }}
            value={localTournamentId() || ""}
            disabled={inputLocked()}
            onChange={e => {
              const id = e.target.value ? parseInt(e.target.value) : null;
              setLocalTournamentId(id);
              setOptimisticUserMessages([]);
              setIsAwaitingAgent(false);
              setLiveProposals([]);
              props.onSelectTournament?.(id);
            }}
          >
            <option value="">Select a tournament…</option>
            <For each={manageableTournaments()}>
              {t => <option value={t.id}>{t.event?.title || t.id}</option>}
            </For>
          </select>

          <div class="ml-auto flex items-center gap-1">
            <ModelPicker
              models={modelsQuery.data?.models || []}
              value={modelId()}
              disabled={inputLocked()}
              onChange={handleModelChange}
            />
            <Show
              when={!confirmingClear()}
              fallback={
                <div class="flex items-center gap-1">
                  <button
                    type="button"
                    class="cursor-pointer rounded-md bg-red-700 px-2 py-1 text-xs font-medium text-white transition-colors duration-150 hover:bg-red-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500"
                    onClick={() => clearMutation.mutate()}
                  >
                    Clear chat?
                  </button>
                  <button
                    type="button"
                    class="cursor-pointer rounded-md px-2 py-1 text-xs transition-colors duration-150 hover:bg-black/[0.04] dark:hover:bg-white/[0.06]"
                    style={{ color: "var(--agent-ink-muted)" }}
                    onClick={() => setConfirmingClear(false)}
                  >
                    Cancel
                  </button>
                </div>
              }
            >
              <button
                type="button"
                class="cursor-pointer rounded-md px-2 py-1 text-xs transition-colors duration-150 hover:bg-black/[0.04] focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 disabled:cursor-not-allowed disabled:opacity-40 dark:hover:bg-white/[0.06]"
                style={{ color: "var(--agent-ink-muted)" }}
                disabled={!localTournamentId() || inputLocked()}
                onClick={() => setConfirmingClear(true)}
              >
                Clear
              </button>
            </Show>
          </div>
        </div>

        <Show
          when={localTournamentId()}
          fallback={
            <div class="flex flex-1 items-center justify-center p-8">
              <p class="text-sm" style={{ color: "var(--agent-ink-muted)" }}>
                Select a tournament to start.
              </p>
            </div>
          }
        >
          <div
            ref={messagesContainerRef}
            onScroll={onScroll}
            class="min-h-0 flex-1 overflow-y-auto overscroll-contain px-1 py-4"
          >
            <Show
              when={displayMessages().length > 0 || isAwaitingAgent()}
              fallback={
                <EmptyState
                  tournament={tournament()}
                  tournamentId={localTournamentId()}
                  onPick={handleSend}
                  disabled={inputLocked()}
                />
              }
            >
              <div class="mx-auto max-w-3xl space-y-5">
                <For each={displayMessages()}>
                  {msg => (
                    <Show
                      when={msg.role !== "user"}
                      fallback={<UserMessage content={msg.content} />}
                    >
                      <AssistantMessage
                        content={msg.content}
                        toolEvents={msg.payload?.tool_events}
                      >
                        <Show
                          when={
                            msg.message_kind === "question" &&
                            msg.payload?.question_id
                          }
                        >
                          <Show
                            when={
                              historyQuery.data?.pending_question?.id ===
                                msg.payload.question_id && !inputLocked()
                            }
                            fallback={
                              <Show when={msg.payload?.question_snapshot}>
                                <QuestionSnapshot
                                  question={msg.payload.question_snapshot}
                                />
                              </Show>
                            }
                          >
                            <QuestionCard
                              question={historyQuery.data.pending_question}
                              disabled={inputLocked()}
                              onSubmit={handleAnswer}
                            />
                          </Show>
                        </Show>
                        <For each={proposalsForMessage(msg)}>
                          {proposal => (
                            <div class="mt-3">
                              <ProposalCard {...proposalCardProps(proposal)} />
                            </div>
                          )}
                        </For>
                      </AssistantMessage>
                    </Show>
                  )}
                </For>

                <Show when={isStreamingReply()}>
                  <AssistantMessage
                    content={streamingText()}
                    toolEvents={streamingTools()}
                    streaming
                  >
                    <For each={liveProposals()}>
                      {proposal => (
                        <div class="mt-3">
                          <ProposalCard {...proposalCardProps(proposal)} />
                        </div>
                      )}
                    </For>
                  </AssistantMessage>
                </Show>

                <Show when={isAwaitingAgent() && !isStreamingReply()}>
                  <div class="flex items-center gap-3">
                    <AgentMark
                      class="h-4 w-4 shrink-0 animate-pulse"
                      style={{ color: "var(--agent-accent)" }}
                    />
                    <span
                      class="text-sm"
                      style={{ color: "var(--agent-ink-muted)" }}
                      aria-live="polite"
                    >
                      Thinking…
                    </span>
                  </div>
                </Show>

                <Show when={unattachedProposals().length > 0}>
                  <div class="space-y-2">
                    <h3
                      class="text-xs font-semibold uppercase tracking-wide"
                      style={{ color: "var(--agent-ink-muted)" }}
                    >
                      Awaiting your confirmation
                    </h3>
                    <For each={unattachedProposals()}>
                      {proposal => (
                        <ProposalCard {...proposalCardProps(proposal)} />
                      )}
                    </For>
                  </div>
                </Show>
              </div>
            </Show>
            <div ref={messagesEndRef} />
          </div>

          <div class="shrink-0 px-1 pb-1 pt-2">
            <div class="mx-auto max-w-3xl">
              <Show when={streamError()}>
                <div
                  class="mb-2 flex items-center gap-2 rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-xs text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-300"
                  role="alert"
                >
                  <span class="flex-1">{streamError()}</span>
                  <button
                    type="button"
                    class="cursor-pointer font-medium underline-offset-2 hover:underline"
                    onClick={() => setStreamError("")}
                  >
                    Dismiss
                  </button>
                </div>
              </Show>

              <Show when={nextStep()}>
                {step => (
                  <div class="mb-2 flex items-center gap-2">
                    <span
                      class="text-[11px] font-medium uppercase tracking-wide"
                      style={{ color: "var(--agent-ink-muted)" }}
                    >
                      Next
                    </span>
                    <button
                      type="button"
                      title={step().why}
                      class="cursor-pointer rounded-full border px-3 py-1 text-xs font-medium transition-colors duration-150 hover:border-[color:var(--agent-line-strong)] focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500"
                      style={{
                        "border-color": "var(--agent-line)",
                        "background-color": "var(--agent-raised)",
                        color: "var(--agent-ink)"
                      }}
                      onClick={() => {
                        setDraft(step().prompt);
                        autosize();
                        textareaRef?.focus();
                      }}
                    >
                      {step().label}
                    </button>
                  </div>
                )}
              </Show>

              <form
                class="flex items-end rounded-xl border p-2 transition-shadow duration-150 focus-within:ring-2 focus-within:ring-blue-500/40"
                style={{
                  "border-color": "var(--agent-line-strong)",
                  "background-color": "var(--agent-raised)"
                }}
                onSubmit={e => {
                  e.preventDefault();
                  handleSend();
                }}
              >
                <textarea
                  id="tournament-agent-chat"
                  ref={textareaRef}
                  rows="1"
                  aria-label="Message the agent"
                  class="max-h-[200px] min-h-[32px] min-w-0 flex-1 resize-none border-0 bg-transparent px-2 py-1.5 text-left text-sm focus:outline-none focus:ring-0 disabled:cursor-not-allowed disabled:opacity-50"
                  style={{ color: "var(--agent-ink)" }}
                  placeholder={
                    historyQuery.data?.placeholder ||
                    "Ask for pools, a bracket, or a schedule…"
                  }
                  value={draft()}
                  disabled={inputLocked()}
                  onInput={e => {
                    setDraft(e.target.value);
                    autosize();
                  }}
                  onKeyDown={e => {
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      handleSend();
                    }
                  }}
                />
                <Show
                  when={!isAwaitingAgent()}
                  fallback={
                    <button
                      type="button"
                      class="inline-flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg transition-colors duration-150 hover:bg-black/[0.06] focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:hover:bg-white/[0.08]"
                      style={{ color: "var(--agent-ink)" }}
                      onClick={handleStop}
                      title="Stop"
                    >
                      <span class="h-2.5 w-2.5 rounded-[2px] bg-current" />
                      <span class="sr-only">Stop</span>
                    </button>
                  }
                >
                  <button
                    type="submit"
                    class="inline-flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-lg bg-blue-700 text-white transition-colors duration-150 hover:bg-blue-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-1 disabled:cursor-not-allowed disabled:opacity-30 dark:bg-blue-600 dark:hover:bg-blue-700"
                    disabled={!draft().trim()}
                  >
                    <svg
                      class="h-4 w-4"
                      viewBox="0 0 20 20"
                      fill="currentColor"
                      aria-hidden="true"
                    >
                      <path d="M3.4 2.6a1 1 0 0 0-1.3 1.2l1.8 5.5a1 1 0 0 0 .8.7l7 .9-7 .9a1 1 0 0 0-.8.7l-1.8 5.5a1 1 0 0 0 1.4 1.2l14-7a1 1 0 0 0 0-1.8l-14-7Z" />
                    </svg>
                    <span class="sr-only">Send</span>
                  </button>
                </Show>
              </form>
              <p
                class="mt-1.5 px-1 text-[10px]"
                style={{ color: "var(--agent-ink-muted)" }}
              >
                AI-generated. Enter to send, Shift+Enter for a new line. Nothing
                is saved until you confirm a proposal.
              </p>
            </div>
          </div>
        </Show>
      </div>

      {/* Right rail: pending proposals over live tournament state. */}
      <Show when={localTournamentId()}>
        <aside
          class="hidden min-h-0 shrink-0 flex-col gap-2 overflow-y-auto border-l pl-3 lg:flex lg:w-[22rem] xl:w-[24rem]"
          style={{ "border-color": "var(--agent-line)" }}
        >
          <Show when={pendingProposals().length > 0}>
            <section>
              <h3
                class="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide"
                style={{ color: "var(--agent-ink-muted)" }}
              >
                Awaiting your confirmation
                <span class="min-w-4 inline-flex h-4 items-center justify-center rounded-full bg-blue-600 px-1 text-[10px] font-semibold text-white">
                  {pendingProposals().length}
                </span>
              </h3>
              <div class="space-y-2">
                <For each={pendingProposals()}>
                  {proposal => (
                    <ProposalCard {...proposalCardProps(proposal)} />
                  )}
                </For>
              </div>
            </section>
          </Show>

          <Show when={pendingProposals().length > 0}>
            <hr class="my-2" style={{ "border-color": "var(--agent-line)" }} />
          </Show>

          <TournamentRail
            tournamentId={localTournamentId()}
            tournament={tournament()}
            teamsMap={teamsMap()}
            busy={inputLocked()}
            nextStep={historyQuery.data?.next_step}
            onPrompt={text => handleSend(text)}
          />
        </aside>
      </Show>
    </div>
  );
};

export default TournamentAgentTab;
