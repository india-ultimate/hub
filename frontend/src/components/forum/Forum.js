import { useNavigate } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { Show } from "solid-js";

import { fetchMembershipStatus } from "../../queries";

const Forum = () => {
  const navigate = useNavigate();

  const membershipQuery = createQuery(
    () => ["membership"],
    fetchMembershipStatus
  );

  const handleGoToDashboard = () => {
    navigate("/dashboard");
  };

  return (
    <div class="rounded-lg bg-white dark:bg-gray-800 md:p-6 md:shadow">
      <Show
        when={membershipQuery.isLoading}
        fallback={
          <Show
            when={membershipQuery.isSuccess && membershipQuery.data?.is_active}
            fallback={
              <div class="space-y-4">
                <h2 class="text-2xl font-bold text-blue-700 dark:text-white">
                  India Ultimate Forum Access
                </h2>
                <div class="rounded-lg bg-yellow-100 p-6 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
                  <div class="flex items-center">
                    <svg
                      class="mr-2 h-5 w-5"
                      fill="currentColor"
                      viewBox="0 0 20 20"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        fill-rule="evenodd"
                        d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                        clip-rule="evenodd"
                      />
                    </svg>
                    <h3 class="text-lg font-medium">Membership Required</h3>
                  </div>
                  <div class="mt-2">
                    <p>
                      You do not have an active India Ultimate membership and
                      hence cannot access the India Ultimate Forum.
                    </p>
                    <button
                      onClick={handleGoToDashboard}
                      class="mt-3 inline-flex items-center rounded-lg bg-blue-700 px-4 py-2 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                    >
                      Go Back to Dashboard
                    </button>
                  </div>
                </div>
              </div>
            }
          >
            <div class="space-y-4">
              <h2 class="text-2xl font-bold text-blue-700 dark:text-white">
                India Ultimate Forum Access
              </h2>
              <div class="rounded-lg bg-green-100 p-6 text-green-800 dark:bg-green-900 dark:text-green-300">
                <div class="flex items-center">
                  <svg
                    class="mr-2 h-5 w-5"
                    fill="currentColor"
                    viewBox="0 0 20 20"
                    xmlns="http://www.w3.org/2000/svg"
                  >
                    <path
                      fill-rule="evenodd"
                      d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                      clip-rule="evenodd"
                    />
                  </svg>
                  <h3 class="text-lg font-medium">Access Granted</h3>
                </div>
                <div class="mt-2">
                  <p class="mb-4">
                    You have an active India Ultimate membership. You can now
                    access the India Ultimate Forum.
                  </p>
                  <a
                    href="https://forum.indiaultimate.org"
                    rel="noopener noreferrer"
                    class="inline-flex items-center rounded-lg bg-blue-700 px-4 py-2 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                  >
                    Access India Ultimate Forum here
                    <svg
                      class="ml-2 h-4 w-4"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      xmlns="http://www.w3.org/2000/svg"
                    >
                      <path
                        stroke-linecap="round"
                        stroke-linejoin="round"
                        stroke-width="2"
                        d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                      />
                    </svg>
                  </a>
                </div>
              </div>
            </div>
          </Show>
        }
      >
        <div class="flex items-center justify-center p-8">
          <div class="text-center">
            <div class="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-current border-r-transparent align-[-0.125em] motion-reduce:animate-[spin_1.5s_linear_infinite]" />
            <p class="mt-4 text-gray-600 dark:text-gray-400">Loading...</p>
          </div>
        </div>
      </Show>

      <Show when={membershipQuery.error}>
        <div class="rounded-lg bg-red-100 p-6 text-red-800 dark:bg-red-900 dark:text-red-300">
          <div class="flex items-center">
            <svg
              class="mr-2 h-5 w-5"
              fill="currentColor"
              viewBox="0 0 20 20"
              xmlns="http://www.w3.org/2000/svg"
            >
              <path
                fill-rule="evenodd"
                d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                clip-rule="evenodd"
              />
            </svg>
            <h3 class="text-lg font-medium">Error</h3>
          </div>
          <div class="mt-2">
            <p>
              {membershipQuery.error?.message ||
                "Failed to load forum access information. Please try again later."}
            </p>
          </div>
        </div>
      </Show>
    </div>
  );
};

export default Forum;
