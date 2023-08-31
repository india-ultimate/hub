import { For, Suspense } from "solid-js";
import { createQuery } from "@tanstack/solid-query";
import { fetchContributors } from "../queries";
import ContributorsSkeleton from "../skeletons/Contributors";

const Home = () => {
  const query = createQuery(() => ["contributors"], fetchContributors, {
    refetchOnWindowFocus: false
  });

  const features = [
    {
      title: "Membership",
      description: "All in one place to keep track of your UPAI membership"
    },
    {
      title: "Payments",
      description:
        "Direct integrated payment system for easy individual or group membership payments"
    },
    {
      title: "Roster",
      description: "Validate your Team Roster for any events"
    },
    {
      title: "Tournaments",
      description: "Shhhhh... Coming Soon!"
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
      <h2 class="text-center">By UPAI</h2>
      <div class="mt-5">
        <h3 class="text-2xl font-extrabold text-center">Features</h3>
        <div
          class={
            "grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3 justify-items-center mt-5 "
          }
        >
          <For each={features}>
            {feature => (
              <div class="block p-4 bg-white border border-blue-600 rounded-lg shadow dark:bg-gray-800 dark:border-blue-400 w-full">
                <h5 class="mb-2 text-xl font-bold tracking-tight text-blue-600 dark:text-blue-400">
                  {feature.title}
                </h5>
                <p class="font-normal text-gray-700 dark:text-gray-400">
                  {feature.description}
                </p>
              </div>
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
      </div>
    </div>
  );
};

export default Home;
