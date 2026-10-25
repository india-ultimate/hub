import { A, useLocation, useNavigate, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { arrowLeft, home, share, trophy } from "solid-heroicons/solid";
import { createMemo, createSignal, For, Show } from "solid-js";

import { profileQueryKey } from "../../playerLinks";
import { fetchPlayerProfile } from "../../queries";
import ErrorAlert from "../alerts/Error";
import Breadcrumbs from "../Breadcrumbs";
import CareerStrip from "./CareerStrip";
import Hero from "./Hero";
import ProfileSkeleton from "./ProfileSkeleton";
import TournamentCard from "./TournamentCard";

const FIRST_SHOWN = 4;

const NotFound = () => (
  <div class="flex flex-col items-center px-6 py-16 text-center">
    <div class="bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-5xl font-extrabold text-transparent">
      404
    </div>
    <p class="mt-3 font-medium text-gray-800 dark:text-gray-100">
      We couldn&apos;t find that player
    </p>
    <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
      The link may be old or mistyped.
    </p>
    <A
      href="/tournaments"
      class="mt-5 inline-flex min-h-[44px] items-center rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900"
    >
      Browse tournaments
    </A>
  </div>
);

const ShareButton = props => {
  const [message, setMessage] = createSignal("");
  let timer;
  const say = text => {
    setMessage(text);
    clearTimeout(timer);
    timer = setTimeout(() => setMessage(""), 2000);
  };
  const onShare = async () => {
    const url = window.location.href;
    if (navigator.share) {
      try {
        await navigator.share({ title: props.name, url });
      } catch {
        // Dismissing the share sheet rejects; there is nothing to recover.
      }
      return;
    }
    try {
      await navigator.clipboard.writeText(url);
      say("Link copied");
    } catch {
      say("Couldn't copy link");
    }
  };
  return (
    <div class="mt-8 text-center">
      <button
        type="button"
        onClick={onShare}
        class="inline-flex min-h-[44px] items-center gap-2 rounded-lg bg-white px-3 py-2 text-sm font-medium text-gray-700 shadow-sm ring-1 ring-gray-200 transition duration-200 hover:bg-gray-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:bg-gray-700 dark:text-gray-200 dark:ring-gray-600 dark:hover:bg-gray-600"
      >
        <Icon class="h-4 w-4" path={share} />
        Share profile
      </button>
      <p
        role="status"
        aria-live="polite"
        class="mt-2 min-h-5 text-sm text-gray-600 dark:text-gray-300"
      >
        {message()}
      </p>
    </div>
  );
};

const PlayerProfile = () => {
  const params = useParams();
  const location = useLocation();
  const from = () => location.state?.from;

  const query = createQuery(
    () => profileQueryKey(params.slug),
    () => fetchPlayerProfile(params.slug)
  );

  const [showAll, setShowAll] = createSignal(false);
  const pinned = createMemo(() =>
    query.data?.tournaments.find(
      t => from()?.tournamentSlug && t.slug === from().tournamentSlug
    )
  );
  const rest = createMemo(() =>
    (query.data?.tournaments ?? []).filter(t => t !== pinned())
  );
  const visible = () => (showAll() ? rest() : rest().slice(0, FIRST_SHOWN));
  const years = () => {
    const groups = [];
    for (const t of visible()) {
      const year = Number(t.start_date.slice(0, 4));
      const last = groups[groups.length - 1];
      if (last?.year === year) last.items.push(t);
      else groups.push({ year, items: [t] });
    }
    return groups;
  };
  const hidden = () => rest().length - visible().length;

  const navigate = useNavigate();

  return (
    <Show
      when={!query.isError || query.error?.status !== 404}
      fallback={<NotFound />}
    >
      <Show
        when={query.data}
        fallback={
          <Show when={query.isError} fallback={<ProfileSkeleton />}>
            <div class="mx-auto max-w-xl py-10">
              <ErrorAlert text="We couldn't load this profile. Check your connection and try again." />
              <button
                type="button"
                onClick={() => query.refetch()}
                class="inline-flex min-h-[44px] items-center rounded-lg bg-blue-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-blue-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 dark:focus-visible:ring-offset-gray-900"
              >
                Try again
              </button>
            </div>
          </Show>
        }
      >
        {profile => (
          <div class="mx-auto max-w-5xl pb-10">
            <Show
              when={from()}
              fallback={
                <Breadcrumbs
                  icon={home}
                  pageList={[
                    { url: "/", name: "Home" },
                    { name: profile().full_name }
                  ]}
                />
              }
            >
              <button
                type="button"
                data-back-pill
                aria-label={`Back to ${from().label}`}
                onClick={() =>
                  history.length > 1 ? history.back() : navigate("/")
                }
                class="mb-4 inline-flex min-h-[44px] max-w-full items-center gap-2 rounded-full bg-gray-100 px-3 py-1.5 text-sm font-medium text-gray-700 transition duration-200 hover:bg-gray-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700"
              >
                <Icon class="h-4 w-4 flex-none" path={arrowLeft} />
                <span class="truncate">{from().label}</span>
              </button>
            </Show>

            <Hero profile={profile()} />
            <CareerStrip tournaments={profile().tournaments} />

            <Show
              when={profile().tournaments.length}
              fallback={
                <div class="mt-6 rounded-xl border border-dashed border-gray-300 p-6 text-center dark:border-gray-600">
                  <Icon
                    class="mx-auto h-8 w-8 text-gray-300 dark:text-gray-600"
                    path={trophy}
                  />
                  <p class="mt-2 font-medium text-gray-700 dark:text-gray-200">
                    No tournaments yet
                  </p>
                  <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Tournaments {profile().full_name.split(" ")[0]} plays on the
                    hub will show up here.
                  </p>
                </div>
              }
            >
              <Show when={pinned()}>
                <h2 class="mt-6 text-xs font-semibold uppercase tracking-wide text-blue-700 dark:text-blue-400">
                  At {pinned().title}
                </h2>
                <div class="mt-2 md:max-w-[calc(50%-0.5rem)]">
                  <TournamentCard tournament={pinned()} pinned />
                </div>
              </Show>

              <h2 class="mt-7 text-lg font-bold text-gray-900 dark:text-white">
                Tournament history
              </h2>
              <For each={years()}>
                {group => (
                  <>
                    <h3 class="mt-4 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
                      {group.year}
                    </h3>
                    <div class="mt-2 grid gap-3 md:grid-cols-2 md:gap-4">
                      <For each={group.items}>
                        {t => <TournamentCard tournament={t} />}
                      </For>
                    </div>
                  </>
                )}
              </For>
              <Show when={hidden() > 0}>
                <button
                  type="button"
                  onClick={() => setShowAll(true)}
                  class="mt-5 flex min-h-[44px] w-full items-center justify-center gap-1 rounded-xl border border-dashed border-gray-300 py-3 text-sm font-medium text-blue-700 transition duration-200 hover:bg-blue-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:border-gray-600 dark:text-blue-400 dark:hover:bg-gray-800"
                >
                  Show {hidden()} earlier{" "}
                  {hidden() === 1 ? "tournament" : "tournaments"}
                </button>
              </Show>
            </Show>

            <ShareButton name={profile().full_name} />
          </div>
        )}
      </Show>
    </Show>
  );
};

export default PlayerProfile;
