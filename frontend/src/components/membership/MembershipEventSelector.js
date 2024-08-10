import { createEffect, createSignal, For, onMount, Show } from "solid-js";

import { eventMembershipFee } from "../../constants";
import { displayDate, fetchUrl } from "../../utils";

const MembershipEventSelector = props => {
  const [events, setEvents] = createSignal([]);

  const isShortEvent = event =>
    (new Date(event.end_date) - new Date(event.start_date)) / (1000 * 86400) <=
    5;

  const eventsSuccessHandler = async response => {
    const data = await response.json();
    if (response.ok) {
      setEvents(data.filter(isShortEvent));
    } else {
      console.log(data);
    }
  };

  const handleEventChange = e => {
    props.setEvent(events().find(ev => ev.id === Number(e.target.value)));
  };

  onMount(() => {
    fetchUrl("/api/events", eventsSuccessHandler, error => console.log(error));
  });

  createEffect(() => {
    // Set event when we have a list of events
    if (events()?.length > 0) {
      props.setEvent(events()?.[0]);
    }
  });

  return (
    <>
      <Show when={!props.annual && events()?.length > 0}>
        <select
          id="event"
          class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
          value={props.event?.id}
          onInput={handleEventChange}
          required
        >
          <For each={events()}>
            {event => <option value={event?.id}>{event?.title}</option>}
          </For>
        </select>
        <p>
          Pay India Ultimate membership fee (₹ {eventMembershipFee / 100}) for
          the {props.event.title} ({displayDate(props.startDate)} to{" "}
          {displayDate(props.endDate)})
        </p>
      </Show>
      <Show when={!props.annual && events()?.length === 0}>
        <p>No upcoming events found, for membership...</p>
      </Show>
    </>
  );
};

export default MembershipEventSelector;
