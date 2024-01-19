import { For, Show } from "solid-js";

import MatchCard from "./MatchCard";

const ScheduleTable = props => {
  const showReadableTime = time => {
    return new Date(time).toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "numeric",
      timeZone: "UTC"
    });
  };

  return (
    <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
      <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
        <tr>
          <th scope="col" class="px-2 py-3 text-center">
            Time
          </th>
          <For each={Object.keys(props.fieldMap[props.day]).sort()}>
            {field => (
              <th scope="col" class="px-1 py-3 text-center">
                {field}
              </th>
            )}
          </For>
        </tr>
      </thead>
      <tbody>
        <For
          each={Object.keys(props.matchDayTimeFieldMap[props.day]).sort(
            (a, b) => new Date(a) - new Date(b)
          )}
        >
          {startTime => (
            <For
              each={Object.keys(
                props.matchDayTimeFieldMap[props.day][startTime]
              ).sort((a, b) => new Date(a) - new Date(b))}
            >
              {endTime => (
                <tr class="border-b bg-white dark:border-gray-700 dark:bg-gray-800">
                  <th
                    scope="row"
                    class="whitespace-nowrap px-2 py-2 text-center text-xs font-medium "
                  >
                    <span class="text-gray-900 dark:text-white">
                      {showReadableTime(startTime)}
                    </span>
                    <hr class="my-2 h-px border-0 bg-gray-200 dark:bg-gray-700" />
                    {showReadableTime(endTime)}
                  </th>
                  <For each={Object.keys(props.fieldMap[props.day]).sort()}>
                    {field => (
                      <td class="whitespace-nowrap px-2 py-4 text-xs">
                        <Show
                          when={
                            props.matchDayTimeFieldMap[props.day][startTime][
                              endTime
                            ][field]
                          }
                        >
                          <MatchCard
                            match={
                              props.matchDayTimeFieldMap[props.day][startTime][
                                endTime
                              ][field]
                            }
                            showSeed={true}
                            setFlash={props.setFlash}
                          />
                        </Show>
                      </td>
                    )}
                  </For>
                </tr>
              )}
            </For>
          )}
        </For>
      </tbody>
    </table>
  );
};

export default ScheduleTable;
