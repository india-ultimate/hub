import clsx from "clsx";
import { For, createSignal, createEffect, Show, Match, Switch } from "solid-js";
import { onMount } from "solid-js";
import { fetchUserData, fetchUrl } from "../utils";
import { useStore } from "../store";
import { Icon } from "solid-heroicons";
import {
  noSymbol,
  currencyRupee,
  handThumbUp,
  handThumbDown,
  shieldCheck,
  shieldExclamation
} from "solid-heroicons/solid-mini";

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
  console.log(registration?.roles);
  return registration?.roles?.indexOf("player") > -1;
};

const ValidateRoster = () => {
  const [store, { setLoggedIn, setData }] = useStore();
  const [event, setEvent] = createSignal();
  const [eventData, setEventData] = createSignal();
  const [events, setEvents] = createSignal([]);
  const [loading, setLoading] = createSignal(false);

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
    let data;
    if (response.ok) {
      data = await response.json();
      const groupedData = groupByTeam(data?.registrations);
      console.log(groupedData, "grouped");
      setEventData({ ...data, ...groupedData });
    } else {
      data = await response.text();
      console.log(data);
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
    fetchUrl("/api/events?include_all=1", eventsSuccessHandler, error => {
      console.log(error);
      setLoading(false);
    });
  });

  createEffect(() => {
    if (event()?.id) {
      const eventID = event()?.id;
      setLoading(true);
      fetchUrl(`/api/event/${eventID}`, eventDataFetched, error => {
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
        <Match when={eventData()?.ultimate_central_slug}>
          <h2 class="text-2xl font-bold text-blue-500">{eventData()?.title}</h2>
          <a
            href={`https://indiaultimate.org/en_in/e/${
              eventData()?.ultimate_central_slug
            }`}
          >
            View event on Ultimate Central
          </a>
          <div class="my-4 grid grid-cols-2 md:grid-cols-3 gap-4">
            <For each={eventData()?.teams}>
              {team => (
                <div>
                  <h3 class="text-xl font-bold text-blue-500">{team.name}</h3>
                  <ul class="my-4 w-200 text-sm font-medium text-gray-900 bg-white border border-gray-200 rounded-lg dark:bg-gray-700 dark:border-gray-600 dark:text-white">
                    <For each={eventData()?.registrationsByTeam[team.id]}>
                      {registration => (
                        <Show when={isPlayer(registration)}>
                          <li class="w-full px-4 py-2 border-b border-gray-200 rounded-t-lg dark:border-gray-600">
                            {registration.person.first_name}{" "}
                            {registration.person.last_name}
                            <Switch>
                              <Match when={!registration?.person?.player}>
                                <span class={clsx("mx-4", redText)}>
                                  <Icon
                                    path={noSymbol}
                                    style={{ width: "20px", display: "inline" }}
                                  />
                                </span>
                              </Match>
                              <Match when={registration?.person?.player}>
                                <span
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
                                    style={{ width: "20px", display: "inline" }}
                                  />
                                </span>
                                <span
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
                                    style={{ width: "20px", display: "inline" }}
                                  />
                                </span>
                                <span
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
                                      registration.person.player?.vaccination
                                        ?.is_vaccinated
                                        ? shieldCheck
                                        : shieldExclamation
                                    }
                                    style={{ width: "20px", display: "inline" }}
                                  />
                                </span>
                              </Match>
                            </Switch>
                          </li>
                        </Show>
                      )}
                    </For>
                  </ul>
                </div>
              )}
            </For>
          </div>
        </Match>
      </Switch>
    </div>
  );
};
export default ValidateRoster;
