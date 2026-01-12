import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { userGroup } from "solid-heroicons/solid";
import { Show } from "solid-js";

import { fetchTeamBySlug, fetchUser } from "../../queries";
import Breadcrumbs from "../Breadcrumbs";
import Modal from "../Modal";
import EditTeamNameForm from "./EditTeamNameForm";

const EditNameModal = props => {
  let modalRef;
  return (
    <>
      <button
        type="button"
        onClick={() => modalRef.showModal()}
        class="inline-flex items-center gap-x-2 rounded-lg border-2 border-yellow-300 bg-yellow-50 px-3 py-2 text-center text-sm font-medium text-yellow-700 shadow-sm hover:bg-yellow-100 focus:outline-none focus:ring-2 focus:ring-yellow-300"
      >
        Edit name
      </button>
      <Modal
        ref={modalRef}
        title={<span class="text-md font-semibold">Edit name</span>}
        close={() => modalRef.close()}
      >
        {props.children}
      </Modal>
    </>
  );
};

const View = () => {
  const params = useParams();

  const teamQuery = createQuery(
    () => ["teams", params.slug],
    () => fetchTeamBySlug(params.slug)
  );
  const userQuery = createQuery(() => ["me"], fetchUser);

  return (
    <div>
      <Breadcrumbs
        icon={userGroup}
        pageList={[{ url: "/teams", name: "Teams" }, { name: "View Team" }]}
      />

      <div>
        <div class="mb-6 flex w-full flex-row items-center justify-start gap-x-6 rounded-xl border border-gray-200 bg-gray-100 p-4">
          <div>
            <img
              class="h-24 w-24 rounded-full p-1 ring-2 ring-gray-300 dark:ring-blue-500"
              src={teamQuery.data?.image ?? teamQuery.data?.image_url}
              alt="Bordered avatar"
            />
          </div>

          <div class="flex flex-col items-start justify-center gap-y-2">
            <div class="text-lg font-bold text-gray-700">
              {teamQuery.data?.name}
            </div>
            <Show
              when={
                userQuery.isSuccess &&
                userQuery.data?.admin_teams
                  ?.map(team => team.id)
                  .includes(teamQuery.data?.id)
              }
            >
              <div class="flex flex-row gap-x-2">
                <EditNameModal>
                  <EditTeamNameForm
                    teamId={teamQuery.data?.id}
                    teamName={teamQuery.data?.name}
                  />
                </EditNameModal>
                <A href={`/team/${params.slug}/edit`}>
                  <button
                    type="button"
                    class="inline-flex items-center gap-x-2 rounded-lg border-2 border-yellow-300 bg-yellow-50 px-3 py-2 text-center text-sm font-medium text-yellow-700 shadow-sm hover:bg-yellow-100 focus:outline-none focus:ring-2 focus:ring-yellow-300"
                  >
                    Edit details
                  </button>
                </A>
              </div>
            </Show>
          </div>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-y-6">
          <dl class="mx-2 max-w-md divide-y divide-gray-200 text-gray-800 dark:divide-gray-700 dark:text-white">
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
              <dt class="mb-1 text-gray-500 dark:text-gray-400 md:text-lg">
                City
              </dt>
              <dd class="text-lg font-semibold">{teamQuery.data?.city || "-"}</dd>
            </div>
            <div class="flex flex-col pt-3">
              <dt class="mb-1 text-gray-500 dark:text-gray-400 md:text-lg">
                Admins
              </dt>
              <dd class="text-lg font-semibold">
                {teamQuery.data?.admins
                  .map(admin => (<p>{admin.full_name + ` (${admin.username})`}</p>)) || "-"}
              </dd>
            </div>
          </dl>
          <dl class="mx-2 max-w-md divide-y divide-gray-200 text-gray-800 dark:divide-gray-700 dark:text-white">
            <div class="flex flex-col pb-3">
              <dt class="mb-1 text-gray-500 dark:text-gray-400 md:text-lg">
                Last Played Tournaments
              </dt>
              <dd>
                <div class="flex flex-col gap-y-3">
                  <Show
                    when={teamQuery.data?.tournaments && teamQuery.data.tournaments.length > 0}
                    fallback={<p class="text-gray-500">No tournaments</p>}
                  >
                    {teamQuery.data?.tournaments.map(tournament => (
                      <A
                        href={`/tournament/${tournament.event.slug}/team/${params.slug}`}
                        class="flex items-center gap-3 rounded-md bg-gray-100 p-3 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700"
                      >
                        <Show when={tournament.logo_light || tournament.logo_dark}>
                          <img
                            src={tournament.logo_dark || tournament.logo_light}
                            alt="Tournament logo"
                            class="hidden h-12 w-12 rounded-sm object-contain dark:block"
                          />
                          <img
                            src={tournament.logo_light || tournament.logo_dark}
                            alt="Tournament logo"
                            class="block h-12 w-12 rounded-sm object-contain dark:hidden"
                          />
                        </Show>
                        <div class="flex-1">
                          <h3 class="text-sm font-bold text-gray-700 dark:text-white">
                            {tournament.event.title}
                          </h3>
                          <Show when={tournament.current_seed}>
                            <p class="mt-1 text-xs text-gray-600 dark:text-gray-400">
                              Seed: {tournament.current_seed}
                            </p>
                          </Show>
                        </div>
                      </A>
                    ))}
                  </Show>
                </div>
              </dd>
            </div>
          </dl>
        </div>
      </div>
    </div>
  );
};

export default View;
