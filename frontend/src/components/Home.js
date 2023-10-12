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
        <span class="font-extrabold text-transparent text-8xl bg-clip-text bg-gradient-to-r from-blue-500 to-green-500 w-fit">
          Hub
        </span>
      </h1>
      <h2 class="text-center">By UPAI & FDSF(I)</h2>
      <div class="mt-5">
        <h3 class="text-2xl font-extrabold text-center">Features</h3>
        <div
          class={
            "grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3 justify-items-center mt-5 "
          }
        >
          <For each={features}>
            {feature => (
              <A
                href={feature.link}
                class="block p-4 bg-white border border-blue-600 rounded-lg shadow dark:bg-gray-800 dark:border-blue-400 w-full"
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
        <h3 class="text-2xl font-extrabold text-center">
          <a href="https://github.com/india-ultimate/hub" target="_blank">
            <mark class="px-2 text-white bg-blue-600 rounded dark:bg-blue-500">
              Made
            </mark>{" "}
            with 💙 by...
          </a>
        </h3>
        <div class="w-fit mx-auto mt-5">
          <Suspense fallback={<ContributorsSkeleton />}>
            <For each={query.data}>
              {contributor => (
                <div class="flex items-center space-x-4 my-3 w-full">
                  <img
                    class="w-10 h-10 rounded-full p-0.5 ring-2 ring-blue-600 dark:ring-blue-500"
                    src={contributor["avatar_url"]}
                    alt=""
                  />
                  <div class="font-medium hover:text-blue-600 dark:hover:text-blue-500">
                    <div>
                      <a href={contributor["html_url"]}>{contributor.name}</a>
                    </div>
                  </div>
                </div>
              )}
            </For>
          </Suspense>
        </div>
        <div class="w-full mt-8">
          <a
            href={WALink}
            target="_blank"
            type="button"
            class="text-blue-600 bg-white hover:bg-gray-100 border border-blue-600 font-medium rounded-lg text-sm px-5 py-2.5 text-center flex items-center dark:bg-gray-800 dark:border-blue-400 dark:text-blue-400 dark:hover:bg-gray-700 mb-2 mx-auto w-fit"
          >
            <Icon
              path={chatBubbleBottomCenterText}
              class="w-6 h-5 mr-2 -ml-1"
            />
            Connect to Contribute!
          </a>
        </div>
      </div>
    </div>
  );
};

export default Home;
