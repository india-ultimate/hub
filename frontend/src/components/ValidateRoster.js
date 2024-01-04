import { A } from "@solidjs/router";
import clsx from "clsx";
import { Icon } from "solid-heroicons";
import {
  currencyRupee,
  document,
  documentCheck,
  handThumbDown,
  handThumbUp,
  noSymbol,
  pencil,
  plus,
  shieldCheck,
  shieldExclamation,
  xCircle,
  xMark
} from "solid-heroicons/solid-mini";
import { createEffect, createSignal, For, Match, Show, Switch } from "solid-js";
import { onMount } from "solid-js";

import { accreditationChoices, matchUpChoices, minAge } from "../constants";
import { useStore } from "../store";
import { fetchUrl, getAge, getLabel } from "../utils";

const allRoles = [
  "captain",
  "spirit captain",
  "coach",
  "assistant coach",
  "admin",
  "player"
];

const greenText = "text-green-600 dark:text-green-500";
const redText = "text-red-600 dark:text-red-500";

// const RoleBadge = props => {
//   return (
//     <span
//       class={clsx(
//         "inline-flex items-center rounded-lg px-2 py-1 font-medium",
//         props.colors
//       )}
//     >
//       {props.role}
//       <button
//         type="button"
//         class="ms-2 inline-flex items-center rounded-sm bg-transparent text-sm"
//         aria-label="Remove"
//       >
//         <Icon
//           path={props.iconPath}
//           class="m-0 inline w-5"
//           onClick={props.onClick}
//         />
//       </button>
//     </span>
//   );
// };

const EditPlayerRoles = props => {
  let dialogRef;

  const [roles, setRoles] = createSignal(props.registration?.roles);

  const otherRoles = () => allRoles.filter(role => !roles().includes(role));

  const updatePlayerRoles = async registration => {
    console.log(
      `person_id: ${registration?.person?.id}, reg_id: ${
        registration?.id
      }, roles: ${roles()}`
    );
    // const response = await fetch("/api/uc-registration/set-roles", {
    //   method: "POST",
    //   headers: {
    //     "Content-Type": "application/json",
    //     "X-CSRFToken": getCookie("csrftoken")
    //   },
    //   credentials: "same-origin",
    //   body: JSON.stringify({
    //     person_id: registration.person.id,
    //     registration_id: registration.id,
    //     roles: roles()
    //   })
    // });

    // if (response.ok) {
    // show that roles have been updated successfully
    // }

    const response = await new Promise(res => {
      setTimeout(() => res({ ok: true }), 1000);
    });

    if (response.ok) {
      console.log("successfully updated roles");
    }
  };

  return (
    <>
      <dialog
        ref={dialogRef}
        class="min-w-64 max-w-72 rounded-xl backdrop:bg-gray-700/90 sm:max-w-96"
      >
        <div
          class={clsx(
            "flex w-full flex-col items-start gap-2 rounded-xl p-4",
            "border border-gray-800 dark:border-gray-300",
            "bg-gray-50 dark:bg-gray-600",
            "text-gray-600 dark:text-gray-100"
          )}
        >
          <div class="flex w-full items-center justify-between text-base sm:text-lg">
            <div class="flex">
              <span class="mr-1 font-normal">Player - </span>
              <span class="font-semibold">
                {props.registration?.person?.first_name}{" "}
                {props.registration?.person?.last_name}
              </span>
            </div>
            <button
              type="button"
              class="rounded-lg bg-red-500/90 px-4 py-1 text-sm text-white hover:bg-red-600 dark:bg-red-900  dark:text-gray-100 dark:hover:bg-red-800"
              aria-label="Exit"
              onClick={() => dialogRef.close()}
            >
              <p class="text-sm">Exit</p>
            </button>
          </div>

          <hr class="mt-1 h-px w-full border-0 bg-gray-300 dark:bg-gray-500" />

          <div class="mt-2">
            <div class="mb-2 text-sm">Roles</div>
            <Show
              when={roles().length > 0}
              fallback={
                <p class="font-normal italic text-gray-300/80">
                  The player has no roles
                </p>
              }
            >
              <div class="flex select-none flex-row flex-wrap justify-start gap-2">
                <For each={roles()}>
                  {role => (
                    <>
                      <span class="inline-flex items-center rounded-lg bg-yellow-100 px-2 py-1 font-medium text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
                        {role}
                        <button
                          type="button"
                          class="ms-2 inline-flex items-center rounded-sm bg-transparent text-sm text-yellow-400 hover:bg-yellow-200 hover:text-yellow-900 dark:hover:bg-yellow-800 dark:hover:text-yellow-300"
                          aria-label="Remove"
                        >
                          <Icon
                            path={xMark}
                            class="m-0 inline w-5"
                            onClick={() =>
                              setRoles(prev =>
                                prev.filter(prev_role => prev_role !== role)
                              )
                            }
                          />
                        </button>
                      </span>
                    </>
                  )}
                </For>
              </div>
            </Show>
          </div>

          <div class="mt-3">
            <div class="mb-2 text-sm">Other roles</div>
            <Show
              when={otherRoles().length > 0}
              fallback={
                <p class="font-normal italic text-gray-300/80">
                  No more roles to give
                </p>
              }
            >
              <div class="flex select-none flex-row flex-wrap justify-start gap-2">
                <For each={otherRoles()}>
                  {role => (
                    <>
                      <span class="inline-flex items-center rounded-lg bg-blue-100 px-2 py-1 font-medium text-blue-800 dark:bg-blue-900 dark:text-blue-300">
                        {role}
                        <button
                          type="button"
                          class="ms-2 inline-flex items-center rounded-sm bg-transparent text-sm text-blue-400 hover:bg-blue-200 hover:text-blue-900 dark:hover:bg-blue-800 dark:hover:text-blue-300"
                          aria-label="Add"
                        >
                          <Icon
                            path={plus}
                            class="m-0 inline w-5"
                            onClick={() => setRoles(prev => [...prev, role])}
                          />
                        </button>
                      </span>
                    </>
                  )}
                </For>
              </div>
            </Show>
          </div>

          <button
            type="button"
            class={clsx(
              "me-2 mt-6 w-full rounded-lg px-3 py-2.5",
              "text-sm font-medium text-white dark:text-gray-100",
              "bg-green-500/80 hover:bg-green-600 dark:bg-green-900 dark:hover:bg-green-700",
              "focus:outline-none focus:ring-4 focus:ring-green-300 dark:focus:ring-green-800"
            )}
            onClick={() => updatePlayerRoles(props.registration)}
          >
            Update roles
          </button>
        </div>
      </dialog>

      <button>
        <Icon
          path={pencil}
          class="mr-2"
          style={{
            width: "20px",
            display: "inline",
            color: "orange"
          }}
          onClick={() => dialogRef.showModal()}
        />
      </button>
    </>
  );
};

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

const isCaptain = registration => {
  return registration?.roles?.indexOf("captain") > -1;
};

const isSpiritCaptain = registration => {
  return registration?.roles?.indexOf("spirit captain") > -1;
};

const isNonPlayer = registration => {
  return (
    registration?.roles?.indexOf("coach") > -1 ||
    registration?.roles?.indexOf("assistant coach") > -1 ||
    registration?.roles?.indexOf("admin") > -1
  );
};

const ValidationLegend = () => (
  <ul class="w-80 rounded-lg border border-gray-200 bg-white text-sm font-medium text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white">
    <li class="w-full rounded-t-lg border-b border-gray-200 px-4 py-2 dark:border-gray-600">
      <Icon
        path={noSymbol}
        style={{
          width: "20px",
          display: "inline"
        }}
      />{" "}
      — Ultimate Central profile not linked to the Hub
    </li>
    <li class="w-full border-b border-gray-200 px-4 py-2 dark:border-gray-600">
      <Icon
        path={currencyRupee}
        style={{
          width: "20px",
          display: "inline"
        }}
      />
      — Membership Fee status
    </li>
    <li class="w-full border-b border-gray-200 px-4 py-2 dark:border-gray-600">
      <Icon
        path={handThumbUp}
        style={{
          width: "20px",
          display: "inline"
        }}
      />{" "}
      — Liability Waiver Signed
    </li>
    <li class="w-full border-b border-gray-200 px-4 py-2 dark:border-gray-600">
      <Icon
        path={handThumbDown}
        style={{
          width: "20px",
          display: "inline"
        }}
      />{" "}
      — Liability Waiver Not Signed
    </li>
    <li class="w-full border-b border-gray-200 px-4 py-2 dark:border-gray-600">
      <Icon
        path={shieldCheck}
        style={{
          width: "20px",
          display: "inline"
        }}
      />{" "}
      — Player Vaccinated
    </li>
    <li class="w-full border-b border-gray-200 px-4 py-2 dark:border-gray-600">
      <Icon
        path={shieldExclamation}
        style={{
          width: "20px",
          display: "inline"
        }}
      />{" "}
      — Player Not Vaccinated
    </li>
    <li class="w-full border-b border-gray-200 px-4 py-2 dark:border-gray-600">
      <Icon
        path={documentCheck}
        style={{
          width: "20px",
          display: "inline"
        }}
      />{" "}
      — Advanced Accreditation
    </li>
    <li class="w-full border-b border-gray-200 px-4 py-2 dark:border-gray-600">
      <Icon
        path={document}
        style={{
          width: "20px",
          display: "inline"
        }}
      />{" "}
      — Standard Accreditation
    </li>
    <li class="w-full rounded-b-lg px-4 py-2">
      <Icon
        path={xCircle}
        style={{
          width: "20px",
          display: "inline"
        }}
      />{" "}
      — No Accreditation
    </li>
  </ul>
);

const PlayerRegistration = props => {
  const age = getAge(
    new Date(props.registration.person.player?.date_of_birth),
    new Date(props.eventStartDate)
  );
  const displayAge = Math.round(age * 100) / 100;
  const accreditationDate =
    props.registration?.person?.player?.accreditation?.date;
  const accreditationLevel =
    props.registration?.person?.player?.accreditation?.level;

  return (
    <li
      class={clsx(
        "flex w-full justify-between rounded-t-lg border-b border-gray-200 px-4 py-2 dark:border-gray-600",
        displayAge < minAge ? "bg-gray-100 dark:bg-gray-800" : ""
      )}
    >
      <span>
        <Show when={props.userIsStaff && props.registration}>
          <EditPlayerRoles registration={props.registration} />
        </Show>
        {props.registration.person.first_name}{" "}
        {props.registration.person.last_name}
        <Show when={isCaptain(props.registration)}>
          <span class="text-blue-500"> (C)</span>
        </Show>
        <Show when={isSpiritCaptain(props.registration)}>
          <span class="text-blue-500"> (SC)</span>
        </Show>
      </span>

      <div>
        <Switch>
          <Match when={!props.registration?.person?.player}>
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
          <Match when={props.registration?.person?.player}>
            <span
              title="Membership valid?"
              class={clsx(
                "mx-2",
                props.membershipValidForEvent(props.registration.person.player)
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
                props.registration.person.player?.membership?.waiver_valid
                  ? greenText
                  : redText
              )}
            >
              <Icon
                path={
                  props.registration.person.player?.membership?.waiver_valid
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
                props.registration.person.player?.vaccination?.is_vaccinated
                  ? greenText
                  : redText
              )}
            >
              <Icon
                path={
                  props.registration.person.player?.vaccination?.is_vaccinated
                    ? shieldCheck
                    : shieldExclamation
                }
                style={{
                  width: "20px",
                  display: "inline"
                }}
              />
            </span>
            <span
              title={`Accreditation - ${
                props.playerAccreditationValid(props.registration.person.player)
                  ? `${getLabel(
                      accreditationChoices,
                      accreditationLevel
                    )} (${accreditationDate})`
                  : !accreditationDate
                  ? "No accreditation"
                  : `Outdated: ${accreditationDate}`
              }`}
              class={clsx(
                "mx-2",
                props.playerAccreditationValid(props.registration.person.player)
                  ? greenText
                  : redText
              )}
            >
              <Icon
                path={
                  props.playerAccreditationValid(
                    props.registration.person.player
                  )
                    ? accreditationLevel === "ADV"
                      ? documentCheck
                      : document
                    : xCircle
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
            class="rounded-lg bg-red-50 text-sm text-red-800 dark:bg-gray-800 dark:text-red-400"
            role="alert"
          >
            Under age: {displayAge} years old
          </p>
        </Show>
      </div>
    </li>
  );
};

const ValidateRoster = () => {
  const [store] = useStore();
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
      setEvents(data.sort((a, b) => a.start_date < b.start_date));
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
      setStatus("");
      fetchUrl(`/api/registrations/${eventID}`, eventDataFetched, error => {
        console.log(error);
        setLoading(false);
      });
    }
  });

  const today = new Date().toISOString().split("T")[0];

  const playerAccreditationValid = player => {
    if (!player?.accreditation?.is_valid) {
      return false;
    }
    if (!event()) {
      return player?.accreditation?.is_valid;
    }
    let lastValid = new Date(event()?.end_date);
    lastValid.setMonth(lastValid.getMonth() - 18); // 18 months validity for accreditations
    return new Date(player?.accreditation?.date) > lastValid;
  };

  const membershipValidForEvent = player => {
    if (!player?.membership?.is_active) {
      return false;
    }
    if (!event()) {
      return player?.membership?.is_active;
    }
    const eventStart = new Date(event()?.start_date);
    const eventEnd = new Date(event()?.end_date);

    const membershipStart = new Date(player.membership.start_date);
    const membershipEnd = new Date(player.membership.end_date);

    return membershipStart <= eventStart && membershipEnd >= eventEnd;
  };

  return (
    <div>
      <div class="mb-12">
        <h2
          class="text-2xl font-bold text-red-500"
          id="accordion-collapse-heading-1"
        >
          Select Event
        </h2>
        <select
          id="event"
          class="my-4 block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
          value={event()?.id}
          onInput={handleEventChange}
          required
        >
          <option value="" placeholder disabled>
            Select event
          </option>
          <For each={events()?.filter(e => e.end_date >= today)}>
            {event => <option value={event?.id}>{event?.title}</option>}
          </For>
          <option value="" placeholder disabled>
            Past events
          </option>
          <For each={events()?.filter(e => e.end_date < today)}>
            {event => <option value={event?.id}>{event?.title}</option>}
          </For>
        </select>
      </div>
      <Switch>
        <Match when={loading()}>
          <p>Fetching event information ...</p>
        </Match>
        <Match when={!loading() && !eventData() && status()}>
          <div
            class="mb-4 rounded-lg bg-red-50 p-4 text-sm text-red-800 dark:bg-gray-800 dark:text-red-400"
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
              class="mb-4 rounded-lg bg-red-50 p-4 text-sm text-red-800 dark:bg-gray-800 dark:text-red-400"
              role="alert"
            >
              You do not have access to view any teams participating in this
              event!
            </div>
          </Show>
          <div class="my-4 grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3">
            <For each={eventData()?.teams}>
              {team => {
                const teamRegistrations = eventData()?.registrationsByTeam[
                  team.id
                ].filter(r => isPlayer(r));
                const matchUps =
                  teamRegistrations.filter(r => !r.person.player).length > 0
                    ? [...matchUpChoices, { label: "Unknown" }]
                    : matchUpChoices;

                const teamNonPlayersRegistrations =
                  eventData()?.registrationsByTeam[team.id].filter(r =>
                    isNonPlayer(r)
                  );
                return (
                  <div>
                    <h3 class="text-xl font-bold text-blue-500">
                      {team.name} ({teamRegistrations.length})
                    </h3>
                    <For each={matchUps}>
                      {matchUp => (
                        <>
                          <h4 class="text-l font-bold text-blue-400 dark:text-blue-300">
                            {matchUp.label}
                          </h4>
                          <ul class="w-200 my-4 rounded-lg border border-gray-200 bg-white text-sm font-medium text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white">
                            <For
                              each={teamRegistrations.filter(
                                r =>
                                  (!matchUp.value && !r.person.player) ||
                                  r.person.player?.match_up === matchUp.value
                              )}
                            >
                              {registration => (
                                <PlayerRegistration
                                  registration={registration}
                                  eventStartDate={eventData()?.start_date}
                                  userIsStaff={store?.data?.is_staff}
                                  membershipValidForEvent={
                                    membershipValidForEvent
                                  }
                                  playerAccreditationValid={
                                    playerAccreditationValid
                                  }
                                />
                              )}
                            </For>
                          </ul>
                        </>
                      )}
                    </For>
                    <Show when={teamNonPlayersRegistrations.length > 0}>
                      <h4 class="text-l font-bold text-blue-400 dark:text-blue-300">
                        Non Players
                      </h4>
                      <ul class="w-200 my-4 rounded-lg border border-gray-200 bg-white text-sm font-medium text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white">
                        <For each={teamNonPlayersRegistrations}>
                          {registration => (
                            <li class="w-full rounded-t-lg border-b border-gray-200 px-4 py-2 dark:border-gray-600">
                              {registration.person.first_name}{" "}
                              {registration.person.last_name}{" "}
                              <span class="text-blue-500">
                                ({registration.roles.join(", ")})
                              </span>
                            </li>
                          )}
                        </For>
                      </ul>
                    </Show>
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
