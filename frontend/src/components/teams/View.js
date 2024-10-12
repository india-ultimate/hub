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
                  <EditTeamNameForm teamName={teamQuery.data?.name} />
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
                .map(admin => admin.full_name + ` (${admin.username})`)
                .join("\n") || "-"}
            </dd>
          </div>
        </dl>
      </div>
    </div>
  );
};

export default View;
