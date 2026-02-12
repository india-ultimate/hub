import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { createEffect, createSignal, For, Show } from "solid-js";

import { ChevronRight } from "../../icons";
import { fetchTournaments } from "../../queries";

const TournamentSection = () => {
  const tournamentsQuery = createQuery(() => ["tournaments"], fetchTournaments);
  const [upcoming, setUpcoming] = createSignal([]);
  const [past, setPast] = createSignal([]);
  const [live, setLive] = createSignal([]);

  createEffect(() => {
    let pastTournaments = [];
    let upcomingTournaments = [];
    let liveTournaments = [];
    const today = new Date();

    tournamentsQuery.data?.forEach(tournament => {
      const startDate = new Date(Date.parse(tournament.event.start_date));
      const endDate = new Date(Date.parse(tournament.event.end_date));

      if (endDate < today) {
        pastTournaments.push(tournament);
      } else if (startDate > today) {
        upcomingTournaments.push(tournament);
      } else if (startDate <= today && endDate >= today) {
        liveTournaments.push(tournament);
      }
    });

    pastTournaments.sort(
      (a, b) => new Date(b.event.end_date) - new Date(a.event.end_date)
    );

    const lastThreeMonthTournaments = pastTournaments.filter(
      tournament =>
        tournament.event.end_date > today.setMonth(today.getMonth() - 3)
    );

    if (lastThreeMonthTournaments.length > 0) {
      setPast(lastThreeMonthTournaments);
    } else {
      setPast(pastTournaments.slice(0, 2));
    }

    upcomingTournaments.sort(
      (a, b) => new Date(a.event.end_date) - new Date(b.event.end_date)
    );

    setUpcoming(upcomingTournaments);

    liveTournaments.sort(
      (a, b) => new Date(a.event.end_date) - new Date(b.event.end_date)
    );

    setLive(liveTournaments);
  });

  return (
    <>
      <div class="mt-2 flex items-center justify-between">
        <h2 class="text-lg font-bold text-gray-700">Tournaments</h2>
        <A href="/tournaments" class="text-sm text-blue-600 md:text-base">
          <span class="inline-flex items-center">
            View all <ChevronRight height={16} width={16} />
          </span>
        </A>
      </div>
      <Show when={live().length > 0}>
        <h2 class="mt-2 text-sm">Live Tournaments</h2>
        <For each={live()}>
          {tournament => <TournamentCard tournament={tournament} />}
        </For>
      </Show>
      <Show when={upcoming().length > 0}>
        <h2 class="mt-2 text-sm">Upcoming Tournaments</h2>
        <For each={upcoming()}>
          {tournament => <TournamentCard tournament={tournament} />}
        </For>
      </Show>
      <Show when={past().length > 0}>
        <h2 class="mt-2 text-sm">Past Tournaments</h2>
        <For each={past()}>
          {tournament => <TournamentCard tournament={tournament} />}
        </For>
      </Show>
    </>
  );
};

const TournamentCard = props => (
  <A
    class="my-2 flex items-center gap-3 rounded-md bg-gray-100 p-3 md:gap-6"
    href={
      props.tournament.status === "SCH"
        ? `/tournament/${props.tournament.event.slug}/register`
        : `/tournament/${props.tournament.event.slug}`
    }
  >
    <Show when={props.tournament.logo_light}>
      <img src={props.tournament.logo_light} class="w-12 rounded-sm md:w-24" />
    </Show>

    <div>
      <h3 class="text-sm font-bold text-gray-700 md:text-base">
        {props.tournament.event.title}
      </h3>
      <h4 class="mt-1 text-xs">{props.tournament.event.location}</h4>
      <h4 class="mt-1 text-xs">
        {new Date(
          Date.parse(props.tournament.event.start_date)
        ).toLocaleDateString("en-US", {
          year: "numeric",
          month: "short",
          day: "numeric",
          timeZone: "UTC"
        })}
        <Show
          when={
            props.tournament.event.start_date !==
            props.tournament.event.end_date
          }
        >
          {" "}
          to{" "}
          {new Date(
            Date.parse(props.tournament.event.end_date)
          ).toLocaleDateString("en-US", {
            year: "numeric",
            month: "short",
            day: "numeric",
            timeZone: "UTC"
          })}
        </Show>
      </h4>
    </div>
  </A>
);

export default TournamentSection;
