import { Icon } from "solid-heroicons";
import { videoCamera } from "solid-heroicons/solid-mini";
import { createMemo, For, Show } from "solid-js";

import MatchHeader from "../match/MatchHeader";

const ScheduleTable = props => {
  const showReadableTime = time => {
    return new Date(time).toLocaleTimeString("en-US", {
      hour: "numeric",
      minute: "numeric",
      timeZone: "UTC"
    });
  };

  const fieldIdsSortedByName = createMemo(() => {
    const fieldIds = Object.keys(props.dayFieldMap[props.day]);
    fieldIds.sort((a, b) =>
      props.fieldsMap[Number(a)]?.name < props.fieldsMap[Number(b)]?.name
        ? -1
        : 1
    );
    return fieldIds;
  });

  return (
    <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
      <thead class="bg-gray-50 text-xs text-gray-700 dark:bg-gray-700 dark:text-gray-400">
        <tr>
          <th scope="col" class="px-2 py-3 text-center uppercase">
            Time
          </th>
          <For each={fieldIdsSortedByName()}>
            {fieldId => (
              <th scope="col" class="px-1 py-3 text-center">
                <span class="inline-flex content-center items-center gap-2 uppercase">
                  {props.fieldsMap[fieldId]?.name}
                  <Show when={props.fieldsMap[fieldId]?.is_broadcasted}>
                    <Icon class="inline w-4 text-red-500" path={videoCamera} />
                  </Show>
                </span>
                <Show when={props.fieldsMap[fieldId]?.address}>
                  <Show
                    when={props.fieldsMap[fieldId]?.location_url}
                    fallback={
                      <span class="block font-normal">
                        {props.fieldsMap[fieldId]?.address}
                      </span>
                    }
                  >
                    <a
                      href={props.fieldsMap[fieldId]?.location_url}
                      target="_blank"
                      class="block cursor-pointer font-normal text-blue-500 underline"
                    >
                      {props.fieldsMap[fieldId]?.address}
                    </a>
                  </Show>
                </Show>
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
                  <For each={fieldIdsSortedByName()}>
                    {fieldId => (
                      <td class="whitespace-nowrap px-2 py-4 text-xs">
                        <Show
                          when={
                            props.matchDayTimeFieldMap[props.day][startTime][
                              endTime
                            ][fieldId]
                          }
                        >
                          <MatchHeader
                            match={
                              props.matchDayTimeFieldMap[props.day][startTime][
                                endTime
                              ][fieldId]
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
