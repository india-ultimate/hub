import { useNavigate } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { initFlowbite } from "flowbite";
import { Icon } from "solid-heroicons";
import {
  calendarDays,
  documentText,
  eye,
  eyeSlash,
  link,
  lockClosed,
  tag
} from "solid-heroicons/solid";
import { For, onMount, Show, Suspense } from "solid-js";

import { fetchMembershipStatus } from "../../queries";
import { useStore } from "../../store";
import { getCookie } from "../../utils";

// Fetch announcements API
const fetchAnnouncements = async () => {
  const csrfToken = getCookie("csrftoken");
  const response = await fetch("/api/announcements", {
    headers: {
      "X-CSRFToken": csrfToken
    }
  });
  if (!response.ok) {
    throw new Error("Failed to fetch announcements");
  }
  return response.json();
};

const Announcements = () => {
  const [store] = useStore();
  const navigate = useNavigate();

  // Fetch announcements (backend handles filtering based on user permissions)
  const query = createQuery(() => ["announcements"], fetchAnnouncements, {
    refetchOnWindowFocus: false
  });

  // Fetch membership status
  const membershipQuery = createQuery(
    () => ["membership"],
    fetchMembershipStatus,
    {
      refetchOnWindowFocus: false
    }
  );

  onMount(() => {
    initFlowbite();
  });

  const formatDate = dateString => {
    return new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric"
    });
  };

  const getTypeColor = type => {
    const colors = {
      competitions:
        "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300",
      executive_board:
        "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300",
      project_gamechangers:
        "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300",
      finance:
        "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300"
    };
    return (
      colors[type] ||
      "bg-gray-100 text-gray-800 dark:bg-gray-900 dark:text-gray-300"
    );
  };

  const getTypeLabel = type => {
    const labels = {
      competitions: "Competitions",
      executive_board: "Executive Board",
      project_gamechangers: "Project GameChangers",
      finance: "Finance"
    };
    return labels[type] || type;
  };

  const stripHtml = html => {
    const tmp = document.createElement("div");
    tmp.innerHTML = html;
    return tmp.textContent || tmp.innerText || "";
  };

  const truncateContent = (content, maxLength = 200) => {
    const text = stripHtml(content);
    return text.length > maxLength
      ? text.substring(0, maxLength) + "..."
      : text;
  };

  return (
    <div class="mx-auto">
      <div class="mb-8">
        <h1 class="mb-4 text-4xl font-bold text-blue-700 dark:text-white">
          Announcements
        </h1>
        <p class="text-lg text-gray-600 dark:text-gray-400">
          Stay updated with the latest news and updates from India Ultimate.
        </p>
      </div>

      <Suspense fallback={<AnnouncementsSkeleton />}>
        <Show
          when={store.loggedIn}
          fallback={
            <div class="py-12 text-center">
              <Icon path={lockClosed} class="mx-auto h-16 w-16 text-gray-400" />
              <h3 class="mt-4 text-xl font-semibold text-gray-900 dark:text-white">
                Login Required
              </h3>
              <p class="mt-2 text-gray-600 dark:text-gray-400">
                Please log in to view announcements.
              </p>
              <div class="mt-6">
                <a
                  href="/login?redirect=/announcements"
                  class="inline-flex items-center rounded-lg bg-blue-600 px-6 py-3 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:focus:ring-blue-800"
                >
                  Login
                </a>
              </div>
            </div>
          }
        >
          <Show
            when={query.data}
            fallback={
              <div class="py-8 text-center">
                <Icon
                  path={documentText}
                  class="mx-auto h-12 w-12 text-gray-400"
                />
                <p class="mt-2 text-gray-500 dark:text-gray-400">
                  No announcements available.
                </p>
              </div>
            }
          >
            <div class="space-y-6">
              <For each={query.data}>
                {announcement => {
                  const hasActiveMembership =
                    membershipQuery.data?.is_active ?? false;
                  const isMembersOnly = announcement.is_members_only;
                  const canAccess = !isMembersOnly || hasActiveMembership;

                  return (
                    <div
                      class={`rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800 ${
                        canAccess ? "cursor-pointer" : ""
                      }`}
                      role={canAccess ? "link" : undefined}
                      tabIndex={canAccess ? 0 : undefined}
                      onClick={() =>
                        canAccess &&
                        navigate(`/announcement/${announcement.slug}`)
                      }
                      onKeyDown={e => {
                        if (canAccess && e.key === "Enter")
                          navigate(`/announcement/${announcement.slug}`);
                      }}
                    >
                      {/* Header */}
                      <div class="mb-2 flex items-start justify-between">
                        <div class="flex-1">
                          <div class="mb-2 flex items-center gap-2">
                            <span
                              class={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getTypeColor(
                                announcement.type
                              )}`}
                            >
                              <Icon path={tag} class="mr-1 h-3 w-3" />
                              {getTypeLabel(announcement.type)}
                            </span>
                            <Show when={!announcement.is_published}>
                              <span class="inline-flex items-center rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-medium text-orange-800 dark:bg-orange-900 dark:text-orange-300">
                                <Icon path={eyeSlash} class="mr-1 h-3 w-3" />
                                Draft
                              </span>
                            </Show>
                            <Show when={announcement.is_members_only}>
                              <span class="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800 dark:bg-red-900 dark:text-red-300">
                                <Icon path={eye} class="mr-1 h-3 w-3" />
                                Members Only
                              </span>
                            </Show>
                          </div>
                          <h2 class="text-xl font-semibold text-blue-700 dark:text-white">
                            <a
                              href={`/announcement/${announcement.slug}`}
                              class="hover:underline"
                            >
                              {announcement.title}
                            </a>
                          </h2>
                        </div>
                      </div>

                      {/* Content Preview or Members Only Message */}
                      <Show
                        when={canAccess}
                        fallback={
                          <div class="py-2 text-center">
                            <Icon
                              path={lockClosed}
                              class="mx-auto h-8 w-8 text-gray-400"
                            />
                            <p class="mt-1 text-sm text-gray-600 dark:text-gray-400">
                              This announcement is for members only.{" "}
                              <a
                                href="/dashboard"
                                class="text-blue-600 underline hover:text-blue-700"
                              >
                                Become a member
                              </a>
                            </p>
                          </div>
                        }
                      >
                        <div>
                          <p class="text-gray-600 dark:text-gray-400">
                            {truncateContent(announcement.content)}
                          </p>
                        </div>

                        {/* Call to Action */}
                        <Show
                          when={
                            announcement.action_text && announcement.action_url
                          }
                        >
                          <div class="mt-4">
                            <a
                              href={announcement.action_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              aria-label={announcement.action_text}
                              title={announcement.action_text}
                              class="inline-flex items-center text-blue-600 hover:text-blue-700"
                              onClick={e => e.stopPropagation()}
                            >
                              <Icon path={link} class="mr-2 h-4 w-4" />
                              <span>{announcement.action_text}</span>
                            </a>
                          </div>
                        </Show>
                      </Show>

                      {/* Footer */}
                      <div class="mt-4 flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
                        <div class="flex items-center gap-2">
                          <Show
                            when={announcement.author_profile_pic_url}
                            fallback={
                              <div class="flex h-8 w-8 items-center justify-center rounded-full bg-gray-200 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                                {announcement.author.first_name?.[0]}
                                {announcement.author.last_name?.[0]}
                              </div>
                            }
                          >
                            <img
                              src={announcement.author_profile_pic_url}
                              alt={`${announcement.author.first_name} ${announcement.author.last_name}`}
                              class="h-8 w-8 rounded-full object-cover"
                              loading="lazy"
                            />
                          </Show>
                          <span>
                            {announcement.author.first_name}{" "}
                            {announcement.author.last_name}
                          </span>
                        </div>
                        <div class="flex items-center gap-1">
                          <Icon path={calendarDays} class="h-4 w-4" />
                          <span>{formatDate(announcement.created_at)}</span>
                        </div>
                      </div>
                    </div>
                  );
                }}
              </For>
            </div>
          </Show>
        </Show>
      </Suspense>
    </div>
  );
};

const AnnouncementsSkeleton = () => (
  <div class="space-y-6">
    <For each={[1, 2, 3]}>
      {() => (
        <div class="rounded-lg border border-gray-200 bg-white p-6 shadow-sm dark:border-gray-700 dark:bg-gray-800">
          <div class="mb-4">
            <div class="mb-2 h-4 w-24 animate-pulse rounded bg-gray-300 dark:bg-gray-600" />
            <div class="h-6 w-3/4 animate-pulse rounded bg-gray-300 dark:bg-gray-600" />
          </div>
          <div class="mb-4 space-y-2">
            <div class="h-4 w-full animate-pulse rounded bg-gray-300 dark:bg-gray-600" />
            <div class="h-4 w-5/6 animate-pulse rounded bg-gray-300 dark:bg-gray-600" />
            <div class="h-4 w-4/5 animate-pulse rounded bg-gray-300 dark:bg-gray-600" />
          </div>
          <div class="flex items-center gap-4">
            <div class="h-4 w-32 animate-pulse rounded bg-gray-300 dark:bg-gray-600" />
            <div class="h-4 w-24 animate-pulse rounded bg-gray-300 dark:bg-gray-600" />
          </div>
        </div>
      )}
    </For>
  </div>
);

export default Announcements;
