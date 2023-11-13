import { A } from "@solidjs/router";
import { For, Suspense } from "solid-js";
import { createQuery } from "@tanstack/solid-query";
import { fetchContributors } from "../queries";
import ContributorsSkeleton from "../skeletons/Contributors";
import { chatBubbleBottomCenterText } from "solid-heroicons/solid";
import { Icon } from "solid-heroicons";
import { WALink } from "../constants";

const Home = () => {
  const query = createQuery(() => ["contributors"], fetchContributors, {
    refetchOnWindowFocus: false
  });

  const features = [
    {
      title: "Tournaments",
      link: "/tournaments",
      description:
        "View Schedule, Standings etc. of the various India Ultimate Tournaments around you!"
    },
    {
      title: "Membership",
      link: "/dashboard",
      description:
        "India Ultimate’s Membership process made easier - one place to keep track of it all!"
    },
    {
      title: "Payments",
      link: "/dashboard",
      description:
        "Direct integrated payment system for easy individual or group membership payments"
    },
    {
      title: "Roster",
      link: "/dashboard",
      description: "Validate your Team Roster for any events"
    }
  ];

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
        <h3 class="text-center text-2xl font-extrabold">Features</h3>
        <div
          class={
            "mt-5 grid grid-cols-1 justify-items-center gap-5 md:grid-cols-2 lg:grid-cols-3 "
          }
        >
          <For each={features}>
            {feature => (
              <A
                href={feature.link}
                class="block w-full rounded-lg border border-blue-600 bg-white p-4 shadow dark:border-blue-400 dark:bg-gray-800"
              >
                <h5 class="mb-2 text-xl font-bold tracking-tight text-blue-600 dark:text-blue-400">
                  {feature.title}
                </h5>
                <p class="font-normal text-gray-700 dark:text-gray-400">
                  {feature.description}
                </p>
              </A>
            )}
          </For>
        </div>
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
