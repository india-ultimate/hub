import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { createSignal, For, Show } from "solid-js";

import { fetchTickets } from "../../queries";

const TicketList = props => {
  const [filter, setFilter] = createSignal("");

  const ticketsQuery = createQuery(
    () => ["tickets", filter()],
    () => fetchTickets(filter())
  );

  const getStatusBadgeClass = status => {
    switch (status) {
      case "OPN":
        return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300";
      case "PRG":
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300";
      case "RES":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300";
      case "CLS":
        return "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300";
    }
  };

  const getPriorityBadgeClass = priority => {
    switch (priority) {
      case "URG":
        return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-300";
      case "HIG":
        return "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-300";
      case "MED":
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300";
      case "LOW":
        return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300";
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300";
    }
  };

  const getStatusText = status => {
    switch (status) {
      case "OPN":
        return "Open";
      case "PRG":
        return "In Progress";
      case "RES":
        return "Resolved";
      case "CLS":
        return "Closed";
      default:
        return status;
    }
  };

  const getPriorityText = priority => {
    switch (priority) {
      case "URG":
        return "Urgent";
      case "HIG":
        return "High";
      case "MED":
        return "Medium";
      case "LOW":
        return "Low";
      default:
        return priority;
    }
  };

  return (
    <div class="rounded-lg bg-white dark:bg-gray-800 md:shadow">
      <div class="border-gray-200 dark:border-gray-700 md:border-b md:p-6">
        <div class="flex items-center justify-between">
          <h2 class="text-xl font-bold text-blue-700 dark:text-white">
            Help Tickets
          </h2>
          <A
            href="/tickets/new"
            class="rounded-lg bg-blue-700 px-8 py-2.5 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
          >
            New
          </A>
        </div>

        <div class="mt-4 flex flex-wrap items-stretch gap-2">
          <For
            each={[
              { value: "", label: "All" },
              { value: "OPN", label: "Open" },
              { value: "PRG", label: "In Progress" },
              { value: "RES", label: "Resolved" },
              { value: "CLS", label: "Closed" },
              { value: "ME", label: "Created by me" }
            ]}
          >
            {item => (
              <button
                onClick={() => setFilter(item.value)}
                class={`rounded-lg px-4 py-2 text-sm font-medium ${
                  filter() === item.value
                    ? "bg-blue-700 text-white"
                    : "bg-gray-200 text-gray-800 dark:bg-gray-700 dark:text-white"
                }`}
              >
                {item.label}
              </button>
            )}
          </For>
        </div>
      </div>

      <div class="pt-6 md:p-6">
        <Show when={ticketsQuery.isLoading}>
          <div class="flex justify-center p-4">
            <div class="h-8 w-8 animate-spin rounded-full border-b-2 border-t-2 border-blue-600" />
          </div>
        </Show>

        <Show when={ticketsQuery.isSuccess && ticketsQuery.data.length === 0}>
          <div class="p-4 text-center text-gray-500 dark:text-gray-400">
            No tickets found
          </div>
        </Show>

        <Show when={ticketsQuery.isSuccess && ticketsQuery.data.length > 0}>
          <div class="overflow-x-auto">
            <table class="w-full text-left text-sm text-gray-500 dark:text-gray-400">
              <thead class="bg-gray-50 text-xs uppercase text-gray-700 dark:bg-gray-700 dark:text-gray-400">
                <tr>
                  <Show when={props.user.is_staff}>
                    <th scope="col" class="px-6 py-3">
                      ID
                    </th>
                  </Show>
                  <th scope="col" class="px-6 py-3">
                    Title
                  </th>
                  <th scope="col" class="px-6 py-3">
                    Status
                  </th>
                  <th scope="col" class="px-6 py-3">
                    Created By
                  </th>
                  <Show when={props.user.is_staff}>
                    <th scope="col" class="px-6 py-3">
                      Assigned To
                    </th>
                    <th scope="col" class="px-6 py-3">
                      Priority
                    </th>
                  </Show>
                  <th scope="col" class="px-6 py-3">
                    Created At
                  </th>
                  <th scope="col" class="px-6 py-3">
                    Messages
                  </th>
                </tr>
              </thead>
              <tbody>
                <For each={ticketsQuery.data}>
                  {ticket => (
                    <tr class="border-b bg-white hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:hover:bg-gray-700">
                      <Show when={props.user.is_staff}>
                        <td class="px-6 py-4">{ticket.id}</td>
                      </Show>
                      <td class="px-6 py-4">
                        <A
                          href={`/tickets/${ticket.id}`}
                          class="text-blue-600 hover:underline dark:text-blue-500"
                        >
                          {ticket.title}
                        </A>
                      </td>
                      <td class="px-6 py-4">
                        <span
                          class={`mr-2 rounded px-2.5 py-0.5 text-xs font-medium ${getStatusBadgeClass(
                            ticket.status
                          )}`}
                        >
                          {getStatusText(ticket.status)}
                        </span>
                      </td>

                      <td class="px-6 py-4">
                        {ticket.created_by.first_name}{" "}
                        {ticket.created_by.last_name}
                      </td>
                      <Show when={props.user.is_staff}>
                        <td class="px-6 py-4">
                          {ticket.assigned_to
                            ? `${ticket.assigned_to.first_name} ${ticket.assigned_to.last_name}`
                            : "Unassigned"}
                        </td>
                        <td class="px-6 py-4">
                          <span
                            class={`mr-2 rounded px-2.5 py-0.5 text-xs font-medium ${getPriorityBadgeClass(
                              ticket.priority
                            )}`}
                          >
                            {getPriorityText(ticket.priority)}
                          </span>
                        </td>
                      </Show>
                      <td class="px-6 py-4">
                        {new Date(ticket.created_at).toLocaleDateString()}
                      </td>
                      <td class="px-6 py-4">{ticket.message_count}</td>
                    </tr>
                  )}
                </For>
              </tbody>
            </table>
          </div>
        </Show>
      </div>
    </div>
  );
};

export default TicketList;
