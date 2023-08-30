import clsx from "clsx";
import { For, createSignal, createEffect, Show, Match, Switch } from "solid-js";
import { onMount } from "solid-js";
import { fetchUserData, fetchUrl, getAge } from "../utils";
import { useStore } from "../store";
import { Icon } from "solid-heroicons";
import { minAge } from "../constants";
import {
  noSymbol,
  currencyRupee,
  handThumbUp,
  handThumbDown,
  shieldCheck,
  shieldExclamation
} from "solid-heroicons/solid-mini";
import { A } from "@solidjs/router";

const groupByTeam = registrations => {
  const teamsMap = registrations?.reduce(
    (acc, r) => ({ ...acc, [r.team.id]: r.team }),
    {}
  );
  const teams = Object.values(teamsMap || {}).sort((a, b) =>
    a.name.toLowerCase() == b.name.toLowerCase()
      ? 0
      : a.name.toLowerCase() < b.name.toLowerCase()
      ? -1
      : 1
  );
  const registrationsByTeam = registrations?.reduce((acc, r) => {
    const team = acc[r.team.id] || [];
    return { ...acc, [r.team.id]: [...team, r] };
  }, {});
  return { teams, registrationsByTeam };
};

const isPlayer = registration => {
  return registration?.roles?.indexOf("player") > -1;
};

const ValidationLegend = () => (
  <ul class="w-80 text-sm font-medium text-gray-900 bg-white border border-gray-200 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white">
    <li class="w-full px-4 py-2 border-b border-gray-200 rounded-t-lg dark:border-gray-600">
      <Icon
        path={noSymbol}
        style={{
          width: "20px",
          display: "inline"
        }}
      />{" "}
      — Ultimate Central profile not linked to the Hub
    </li>
    <li class="w-full px-4 py-2 border-b border-gray-200 dark:border-gray-600">
      <Icon
        path={currencyRupee}
        style={{
          width: "20px",
          display: "inline"
        }}
      />
      — Membership Fee status
    </li>
    <li class="w-full px-4 py-2 border-b border-gray-200 dark:border-gray-600">
      <Icon
        path={handThumbUp}
        style={{
          width: "20px",
          display: "inline"
        }}
      />{" "}
      — Liability Waiver Signed
    </li>
    <li class="w-full px-4 py-2 border-b border-gray-200 dark:border-gray-600">
      <Icon
        path={handThumbDown}
        style={{
          width: "20px",
          display: "inline"
        }}
      />{" "}
      — Liability Waiver Not Signed
    </li>
    <li class="w-full px-4 py-2 border-b border-gray-200 dark:border-gray-600">
      <Icon
        path={shieldCheck}
        style={{
          width: "20px",
          display: "inline"
        }}
      />{" "}
      — Player Vaccinated
    </li>
    <li class="w-full px-4 py-2 rounded-b-lg">
      <Icon
        path={shieldExclamation}
        style={{
          width: "20px",
          display: "inline"
        }}
      />{" "}
      — Player Not Vaccinated
    </li>
  </ul>
);

const ValidateRoster = () => {
  const [store, { setLoggedIn, setData }] = useStore();
  const [event, setEvent] = createSignal();
  const [eventData, setEventData] = createSignal();
  const [events, setEvents] = createSignal([]);
  const [loading, setLoading] = createSignal(false);
  const [status, setStatus] = createSignal("");

  const eventsSuccessHandler = async response => {
    let data;
    setLoading(false);
    if (response.ok) {
      data = await response.json();
      setEvents(data);
      setEvent(data[0]);
    } else {
      data = await response.text();
      console.log(data);
    }
  };

  const eventDataFetched = async response => {
    setLoading(false);
    if (response.ok) {
      const registrations = await response.json();
      const groupedData = groupByTeam(registrations);
      setEventData({ ...event(), ...groupedData });
    } else {
      if (response.status / 100 === 4) {
        const responseBody = await response.json();
        setStatus(responseBody.message);
      } else {
        setStatus(`Error: ${response.statusText}`);
      }
    }
  };

  const handleEventChange = e => {
    setEvent(events().find(ev => ev.id === Number(e.target.value)));
  };

  onMount(() => {
    if (!store.loggedIn) {
      fetchUserData(setLoggedIn, setData);
    }
  });

  onMount(() => {
    console.log("Fetching events info...");
    setLoading(true);
    fetchUrl("/api/events", eventsSuccessHandler, error => {
      console.log(error);
      setLoading(false);
    });
  });

  createEffect(() => {
    if (event()?.id) {
      const eventID = event()?.id;
      setLoading(true);
      setStatus("");
      fetchUrl(`/api/registrations/${eventID}`, eventDataFetched, error => {
        console.log(error);
        setLoading(false);
      });
    }
  });

  const greenText = "text-green-600 dark:text-green-500";
  const redText = "text-red-600 dark:text-red-500";

  return (
    <div id="accordion-collapse" data-accordion="collapse">
      <h2
        class="text-4xl font-bold text-blue-500"
        id="accordion-collapse-heading-1"
      >
        Upcoming Events
      </h2>
      <select
        id="event"
        class="my-4 bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
        value={event()?.id}
        onInput={handleEventChange}
        required
      >
        <option value="" placeholder disabled>
          Select event
        </option>
        <For each={events()}>
          {event => <option value={event?.id}>{event?.title}</option>}
        </For>
      </select>
      <Switch>
        <Match when={loading()}>
          <p>Fetching event information ...</p>
        </Match>
        <Match when={!loading() && !eventData() && status()}>
          <div
            class="p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50 dark:bg-gray-800 dark:text-red-400"
            role="alert"
          >
            {status()}
          </div>
          <Switch>
            <Match when={!store?.data?.player?.id && !store?.data?.is_staff}>
              You need to{" "}
              <A
                class="text-blue-500 hover:text-blue-700 dark:text-blue-600 dark:hover:text-blue-400"
                href="/registration/me"
              >
                register yourself
              </A>{" "}
              as a player and link your Ultimate Central profile to validate
              your team's roster.
            </Match>
            <Match
              when={
                !store?.data?.player?.ultimate_central_id &&
                !store?.data?.is_staff
              }
            >
              You need to{" "}
              <A
                class="text-blue-500 hover:text-blue-700 dark:text-blue-600 dark:hover:text-blue-400"
                href={`/uc-login/${store.data.player.id}`}
              >
                link your Ultimate Central
              </A>{" "}
              profile from here.
            </Match>
          </Switch>
        </Match>
        <Match when={eventData()?.ultimate_central_slug}>
          <h2 class="text-2xl font-bold text-blue-500">{eventData()?.title}</h2>
          <a
            href={`https://indiaultimate.org/en_in/e/${
              eventData()?.ultimate_central_slug
            }`}
          >
            View event on Ultimate Central
          </a>
          <Show
            when={
              !store?.data?.is_staff && (eventData()?.teams || []).length === 0
            }
          >
            <div
              class="p-4 mb-4 text-sm text-red-800 rounded-lg bg-red-50 dark:bg-gray-800 dark:text-red-400"
              role="alert"
            >
              You do not have access to view any teams participating in this
              event!
            </div>
          </Show>
          <div class="my-4 grid grid-cols-2 md:grid-cols-3 gap-4">
            <For each={eventData()?.teams}>
              {team => {
                const teamRegistrations =
                  eventData()?.registrationsByTeam[team.id];
                return (
                  <div>
                    <h3 class="text-xl font-bold text-blue-500">
                      {team.name} ({teamRegistrations.length})
                    </h3>
                    <ul class="my-4 w-200 text-sm font-medium text-gray-900 bg-white border border-gray-200 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white">
                      <For each={teamRegistrations}>
                        {registration => {
                          const age = getAge(
                            new Date(registration.person.player?.date_of_birth),
                            new Date(eventData()?.start_date)
                          );
                          const displayAge = Math.round(age * 100) / 100;
                          console.log(displayAge);
                          return (
                            <Show when={isPlayer(registration)}>
                              <li
                                class={clsx(
                                  "w-full px-4 py-2 border-b border-gray-200 rounded-t-lg dark:border-gray-600",
                                  displayAge < minAge
                                    ? "bg-gray-100 dark:bg-gray-800"
                                    : ""
                                )}
                              >
                                {registration.person.first_name}{" "}
                                {registration.person.last_name}
                                <Switch>
                                  <Match when={!registration?.person?.player}>
                                    <span
                                      class={clsx("mx-4", redText)}
                                      title="No Hub player linked with UC Profile"
                                    >
                                      <Icon
                                        path={noSymbol}
                                        style={{
                                          width: "20px",
                                          display: "inline"
                                        }}
                                      />
                                    </span>
                                  </Match>
                                  <Match when={registration?.person?.player}>
                                    <span
                                      title="Membership fee paid?"
                                      class={clsx(
                                        "mx-2",
                                        registration.person.player?.membership
                                          ?.is_active
                                          ? greenText
                                          : redText
                                      )}
                                    >
                                      <Icon
                                        path={currencyRupee}
                                        style={{
                                          width: "20px",
                                          display: "inline"
                                        }}
                                      />
                                    </span>
                                    <span
                                      title="Liability Waiver signed?"
                                      class={clsx(
                                        "mx-2",
                                        registration.person.player?.membership
                                          ?.waiver_valid
                                          ? greenText
                                          : redText
                                      )}
                                    >
                                      <Icon
                                        path={
                                          registration.person.player?.membership
                                            ?.waiver_valid
                                            ? handThumbUp
                                            : handThumbDown
                                        }
                                        style={{
                                          width: "20px",
                                          display: "inline"
                                        }}
                                      />
                                    </span>
                                    <span
                                      title="Vaccinated?"
                                      class={clsx(
                                        "mx-2",
                                        registration.person.player?.vaccination
                                          ?.is_vaccinated
                                          ? greenText
                                          : redText
                                      )}
                                    >
                                      <Icon
                                        path={
                                          registration.person.player
                                            ?.vaccination?.is_vaccinated
                                            ? shieldCheck
                                            : shieldExclamation
                                        }
                                        style={{
                                          width: "20px",
                                          display: "inline"
                                        }}
                                      />
                                    </span>
                                  </Match>
                                </Switch>
                                <Show when={displayAge < minAge}>
                                  <p
                                    class="text-sm text-red-800 rounded-lg bg-red-50 dark:bg-gray-800 dark:text-red-400"
                                    role="alert"
                                  >
                                    Under age: {displayAge} years old
                                  </p>
                                </Show>
                              </li>
                            </Show>
                          );
                        }}
                      </For>
                    </ul>
                  </div>
                );
              }}
            </For>
          </div>
          <ValidationLegend />
        </Match>
      </Switch>
    </div>
  );
};
export default ValidateRoster;
