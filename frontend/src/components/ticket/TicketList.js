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
      default:
        return status;
    }
  };

  const getCategoryBadgeClass = category => {
    switch (category) {
      case "Account":
        return "bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-300";
      case "Competitions":
        return "bg-violet-100 text-violet-800 dark:bg-violet-900 dark:text-violet-300";
      case "Membership":
        return "bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-300";
      case "Tournament":
        return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-300";
      case "Payment":
        return "bg-lime-100 text-lime-800 dark:bg-lime-900 dark:text-lime-300";
      case "Tech":
        return "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-300";
      case "Other":
        return "bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-300";
      default:
        return "bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400";
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
                  <th scope="col" class="px-6 py-3">
                    Category
                  </th>
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
                      <td class="px-6 py-4">
                        <span
                          class={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${getCategoryBadgeClass(
                            ticket.category
                          )}`}
                        >
                          {ticket.category ?? "—"}
                        </span>
                      </td>
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
