import { useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { userGroup } from "solid-heroicons/solid";
import { Suspense } from "solid-js";

import { fetchTeamBySlug } from "../../queries";
import Breadcrumbs from "../Breadcrumbs";

const View = () => {
  const params = useParams();

  const teamQuery = createQuery(
    () => ["teams", params.slug],
    () => fetchTeamBySlug(params.slug)
  );

  return (
    <div>
      <Breadcrumbs
        icon={userGroup}
        pageList={[{ url: "/teams", name: "Teams" }, { name: "View Team" }]}
      />

      <div class="flex justify-center">
        <img
          class="mr-3 inline-block h-24 w-24 rounded-full p-1 ring-2 ring-gray-300 dark:ring-blue-500"
          src={teamQuery.data?.image ?? teamQuery.data?.image_url}
          alt="Bordered avatar"
        />
      </div>
      <h1 class="my-5 text-center">
        <span class="w-fit bg-gradient-to-r from-blue-500 to-green-500 bg-clip-text text-2xl font-extrabold text-transparent">
          <Suspense
            fallback={
              <span class="inline-block h-2 w-60 animate-pulse rounded-full bg-gray-200 dark:bg-gray-700" />
            }
          >
            {teamQuery.data?.name}
          </Suspense>
        </span>
      </h1>
      <dl class="max-w-md divide-y divide-gray-200 text-gray-900 dark:divide-gray-700 dark:text-white">
        <div class="flex flex-col pb-3">
          <dt class="mb-1 text-gray-500 dark:text-gray-400 md:text-lg">
            Category
          </dt>
          <dd class="text-lg font-semibold">
            {teamQuery.data?.category || "-"}
          </dd>
        </div>
        <div class="flex flex-col py-3">
          <dt class="mb-1 text-gray-500 dark:text-gray-400 md:text-lg">
            State
          </dt>
          <dd class="text-lg font-semibold">
            {teamQuery.data?.state_ut || "-"}
          </dd>
        </div>
        <div class="flex flex-col pt-3">
          <dt class="mb-1 text-gray-500 dark:text-gray-400 md:text-lg">City</dt>
          <dd class="text-lg font-semibold">{teamQuery.data?.city || "-"}</dd>
        </div>
        <div class="flex flex-col pt-3">
          <dt class="mb-1 text-gray-500 dark:text-gray-400 md:text-lg">
            Admins
          </dt>
          <dd class="text-lg font-semibold">
            {teamQuery.data?.admins
              .map(admin => admin.full_name + ` (${admin.username})`)
              .join("\n") || "-"}
          </dd>
        </div>
      </dl>
    </div>
  );
};

export default View;
