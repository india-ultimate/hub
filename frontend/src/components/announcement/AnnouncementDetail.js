import { useNavigate, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import DOMPurify from "dompurify";
import { initFlowbite } from "flowbite";
import { Icon } from "solid-heroicons";
import {
  arrowRight,
  calendarDays,
  chatBubbleBottomCenterText,
  documentText,
  eye,
  eyeSlash,
  lockClosed,
  tag
} from "solid-heroicons/solid";
import { createEffect, onMount, Show } from "solid-js";

import {
  getAnnouncementTypeColor,
  getAnnouncementTypeLabel
} from "../../colors";
import { fetchMembershipStatus } from "../../queries";
import { useStore } from "../../store";

const fetchAnnouncement = async slug => {
  const response = await fetch(`/api/announcements/${slug}`);
  if (!response.ok) throw new Error("Failed to fetch announcement");
  return response.json();
};

export default function AnnouncementDetail() {
  const [store] = useStore();
  const params = useParams();
  const navigate = useNavigate();

  const query = createQuery(
    () => ["announcement", params.slug],
    () => fetchAnnouncement(params.slug)
  );

  // Fetch membership status
  const membershipQuery = createQuery(
    () => ["membership"],
    fetchMembershipStatus,
    {
      refetchOnWindowFocus: false
    }
  );

  let contentRef;

  onMount(() => {
    initFlowbite();
  });

  createEffect(() => {
    // When content loads, ensure tables are wide enough to trigger horizontal scroll if needed
    if (contentRef && query.data) {
      const tables = contentRef.querySelectorAll("table");
      tables.forEach(t => {
        t.classList.add("min-w-full");
      });
    }
  });

  const formatDate = dateString =>
    new Date(dateString).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric"
    });

  return (
    <div class="mx-auto">
      <Show
        when={store.loggedIn}
        fallback={
          <div class="py-12 text-center">
            <Icon path={lockClosed} class="mx-auto h-16 w-16 text-gray-400" />
            <h3 class="mt-4 text-xl font-semibold text-gray-900 dark:text-white">
              Login Required
            </h3>
            <p class="mt-2 text-gray-600 dark:text-gray-400">
              You need to login to read this announcement
            </p>
            <div class="mt-6">
              <a
                href={`/login?redirect=/announcement/${params.slug}`}
                class="inline-flex items-center rounded-lg bg-blue-600 px-6 py-3 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:focus:ring-blue-800"
              >
                Login
              </a>
            </div>
          </div>
        }
      >
        <div class="mb-8">
          <button
            class="text-blue-600 hover:text-blue-700"
            onClick={() => navigate("/announcements")}
          >
            ← All Announcements
          </button>
        </div>
        <Show
          when={query.data}
          fallback={
            <div class="py-8 text-center">
              <Icon
                path={documentText}
                class="mx-auto h-12 w-12 text-gray-400"
              />
              <p class="mt-2 text-gray-500 dark:text-gray-400">
                Loading announcement...
              </p>
            </div>
          }
        >
          <article class=" dark:border-gray-700 dark:bg-gray-800">
            <div class="mb-4 flex flex-wrap items-center justify-between gap-2">
              <div class="flex flex-wrap items-center gap-2">
                <span
                  class={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${getAnnouncementTypeColor(
                    query.data.type
                  )}`}
                >
                  <Icon path={tag} class="mr-1 h-3 w-3" />
                  {getAnnouncementTypeLabel(query.data.type)}
                </span>
                <Show when={!query.data.is_published}>
                  <span class="inline-flex items-center rounded-full bg-orange-100 px-2.5 py-0.5 text-xs font-medium text-orange-800 dark:bg-orange-900 dark:text-orange-300">
                    <Icon path={eyeSlash} class="mr-1 h-3 w-3" />
                    Draft
                  </span>
                </Show>
                <Show when={query.data.is_members_only}>
                  <span class="inline-flex items-center rounded-full bg-red-100 px-2.5 py-0.5 text-xs font-medium text-red-800 dark:bg-red-900 dark:text-red-300">
                    <Icon path={eye} class="mr-1 h-3 w-3" />
                    Members Only
                  </span>
                </Show>
              </div>
              <div class="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400">
                <Icon path={calendarDays} class="h-4 w-4" />
                <span>{formatDate(query.data.created_at)}</span>
              </div>
            </div>
            <h1 class="mb-3 text-xl font-bold text-gray-900 dark:text-white md:text-3xl">
              {query.data.title}
            </h1>
            <div class="mb-6 flex items-center gap-2">
              <Show
                when={query.data.author_profile_pic_url}
                fallback={
                  <div class="flex h-8 w-8 items-center justify-center rounded-full bg-gray-200 text-xs font-medium text-gray-600 dark:bg-gray-700 dark:text-gray-300">
                    {query.data.author.first_name?.[0]}
                    {query.data.author.last_name?.[0]}
                  </div>
                }
              >
                <img
                  src={query.data.author_profile_pic_url}
                  alt={`${query.data.author.first_name} ${query.data.author.last_name}`}
                  class="h-8 w-8 rounded-full object-cover"
                  loading="lazy"
                />
              </Show>
              <span class="text-sm font-medium text-gray-900 dark:text-white">
                {query.data.author.first_name} {query.data.author.last_name}
              </span>
            </div>

            <Show
              when={
                !query.data.is_members_only ||
                (membershipQuery.data?.is_active ?? false)
              }
              fallback={
                <div class="py-12 text-center">
                  <Icon
                    path={lockClosed}
                    class="mx-auto h-16 w-16 text-gray-400"
                  />
                  <h3 class="mt-4 text-xl font-semibold text-gray-900 dark:text-white">
                    Members Only
                  </h3>
                  <p class="mt-2 text-gray-600 dark:text-gray-400">
                    This announcement is for members only
                  </p>
                  <div class="mt-6">
                    <a
                      href="/dashboard"
                      class="inline-flex items-center rounded-lg bg-blue-600 px-6 py-3 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:focus:ring-blue-800"
                    >
                      Become a India Ultimate member now
                    </a>
                  </div>
                </div>
              }
            >
              <Show when={query.data.action_text && query.data.action_url}>
                <div class="mb-6 rounded-lg bg-gradient-to-r from-blue-50 to-indigo-50 p-4 dark:from-blue-900/20 dark:to-indigo-900/20">
                  <div class="flex items-start justify-center gap-3">
                    <div>
                      <a
                        href={query.data.action_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        class="inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:focus:ring-blue-800"
                      >
                        {query.data.action_text}
                        <Icon path={arrowRight} class="ml-2 h-4 w-4" />
                      </a>
                    </div>
                  </div>
                </div>
              </Show>

              <div class="max-w-full overflow-x-auto sm:overflow-visible">
                <div
                  ref={el => (contentRef = el)}
                  class="prose-sm max-w-none dark:prose-invert md:prose lg:prose-lg prose-a:text-blue-600 hover:prose-a:text-blue-700
                          [&_img]:!h-auto [&_img]:object-contain
                        [&_li]:!list-item [&_ol]:!list-decimal [&_ol]:!pl-6
                        [&_table]:!my-2 [&_table]:!mb-4 [&_table]:border [&_table]:border-gray-200 dark:[&_table]:border-gray-700 [&_td]:border
                        [&_td]:border-gray-200 [&_td]:!px-2 [&_td]:!py-1
                        [&_td]:!text-xs dark:[&_td]:border-gray-700 sm:[&_td]:!px-4
                        sm:[&_td]:!py-2 sm:[&_td]:!text-sm [&_th]:border
                        [&_th]:border-gray-200 [&_th]:!px-2 [&_th]:!py-1
                        [&_th]:!text-xs dark:[&_th]:border-gray-700
                        sm:[&_th]:!px-4 sm:[&_th]:!py-2
                        sm:[&_th]:!text-sm [&_ul]:!list-disc
                        [&_ul]:!pl-6"
                  // eslint-disable-next-line solid/no-innerhtml
                  innerHTML={DOMPurify.sanitize(query.data.content)}
                />
              </div>

              <Show when={query.data.forum_discussion_id}>
                <div class="mt-6 rounded-lg border border-gray-200 bg-gray-50 p-4 dark:border-gray-700 dark:bg-gray-800/50">
                  <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                      <Icon
                        path={chatBubbleBottomCenterText}
                        class="h-5 w-5 text-blue-600 dark:text-blue-400"
                      />
                      <div>
                        <h3 class="text-sm font-semibold text-gray-900 dark:text-white">
                          Have some thoughts?
                        </h3>
                        <p class="text-xs text-gray-600 dark:text-gray-400">
                          Join the conversation on our forum
                        </p>
                      </div>
                    </div>
                    <a
                      href={`https://forum.indiaultimate.org/d/${query.data.forum_discussion_id}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      class="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:focus:ring-blue-800"
                    >
                      <span>View Discussion</span>
                      <Icon path={arrowRight} class="h-4 w-4" />
                    </a>
                  </div>
                </div>
              </Show>

              <Show when={query.data.action_text && query.data.action_url}>
                <div class="mt-6 rounded-lg bg-gradient-to-r from-blue-50 to-indigo-50 p-4 dark:from-blue-900/20 dark:to-indigo-900/20">
                  <div class="flex items-start justify-center gap-3">
                    <div>
                      <a
                        href={query.data.action_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        class="inline-flex items-center rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:focus:ring-blue-800"
                      >
                        {query.data.action_text}
                        <Icon path={arrowRight} class="ml-2 h-4 w-4" />
                      </a>
                    </div>
                  </div>
                </div>
              </Show>
            </Show>
          </article>
        </Show>
      </Show>
    </div>
  );
}
