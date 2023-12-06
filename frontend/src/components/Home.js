import { createQuery } from "@tanstack/solid-query";
import { Icon } from "solid-heroicons";
import { chatBubbleBottomCenterText } from "solid-heroicons/solid";
import { For, Suspense } from "solid-js";

import { WALink } from "../constants";
import { fetchContributors } from "../queries";
import ContributorsSkeleton from "../skeletons/Contributors";
import Tournaments from "./Tournaments";

const Home = () => {
  const query = createQuery(() => ["contributors"], fetchContributors, {
    refetchOnWindowFocus: false
  });

  return (
    <div>
      <h1 class="text-center">India Ultimate</h1>
      <h1 class="text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-8xl font-extrabold text-transparent">
          Hub
        </span>
      </h1>
      <h2 class="text-center">By UPAI & FDSF(I)</h2>
      <div class="mt-5">
        <Tournaments />
      </div>
      <div class="mt-10">
        <h3 class="text-center text-2xl font-extrabold">
          <a href="https://github.com/india-ultimate/hub" target="_blank">
            <mark class="rounded bg-blue-600 px-2 text-white dark:bg-blue-500">
              Made
            </mark>{" "}
            with 💙 by...
          </a>
        </h3>
        <div class="mx-auto mt-5 w-fit">
          <Suspense fallback={<ContributorsSkeleton />}>
            <For each={query.data}>
              {contributor => (
                <div class="my-3 flex w-full items-center space-x-4">
                  <img
                    class="h-10 w-10 rounded-full p-0.5 ring-2 ring-blue-600 dark:ring-blue-500"
                    src={contributor["avatar_url"]}
                    alt=""
                  />
                  <div class="font-medium hover:text-blue-600 dark:hover:text-blue-500">
                    <div>
                      <a href={contributor["html_url"]}>
                        {contributor.name || contributor.login}
                      </a>
                    </div>
                  </div>
                </div>
              )}
            </For>
          </Suspense>
        </div>
        <div class="mt-8 w-full">
          <a
            href={WALink}
            target="_blank"
            type="button"
            class="mx-auto mb-2 flex w-fit items-center rounded-lg border border-blue-600 bg-white px-5 py-2.5 text-center text-sm font-medium text-blue-600 hover:bg-gray-100 dark:border-blue-400 dark:bg-gray-800 dark:text-blue-400 dark:hover:bg-gray-700"
          >
            <Icon
              path={chatBubbleBottomCenterText}
              class="-ml-1 mr-2 h-5 w-6"
            />
            Connect to Contribute!
          </a>
        </div>
      </div>
    </div>
  );
};

export default Home;
