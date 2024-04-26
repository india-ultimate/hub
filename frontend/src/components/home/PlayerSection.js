import { A } from "@solidjs/router";
import { Show } from "solid-js";

import { useStore } from "../../store";
import { assetURL } from "../../utils";

const PlayerSection = () => {
  const [store] = useStore();

  return (
    <>
      <div class="rounded-lg bg-blue-200 md:hidden">
        <div class="p-4">
          <img class="w-full" src={assetURL("hub-player.png")} />
          <h3 class="mt-2 text-xl font-bold text-black">Are you a player?</h3>
          <p class="mt-1 text-sm text-gray-700">
            Manage your memberships, accreditation and payments in one place.
          </p>
          <Show
            when={store?.data?.player}
            fallback={
              <A
                href="/dashboard"
                class="mt-2 block w-fit rounded-lg bg-violet-600 px-4 py-2 text-sm text-white"
              >
                Register on Hub
              </A>
            }
          >
            <A
              href="/dashboard"
              class="mt-2 block w-fit rounded-lg bg-violet-600 px-4 py-2 text-sm text-white"
            >
              My Account
            </A>
          </Show>
        </div>
      </div>

      <div class="hidden rounded-lg bg-blue-200 md:block">
        <div class="flex items-center justify-between p-6">
          <div>
            <h3 class="mt-2 text-4xl font-bold text-black">
              Are you a player?
            </h3>
            <p class="mt-3 text-lg text-gray-700">
              Manage your memberships, accreditation and payments in one place.
            </p>
            <Show
              when={store?.data?.player}
              fallback={
                <A
                  href="/dashboard"
                  class="mt-3 block w-fit rounded-lg bg-violet-600 px-8 py-2 text-sm text-white"
                >
                  Register on Hub
                </A>
              }
            >
              <A
                href="/dashboard"
                class="mt-3 block w-fit rounded-lg bg-violet-600 px-8 py-2 text-sm text-white"
              >
                My Account
              </A>
            </Show>
          </div>
          <img class="w-1/3" src={assetURL("hub-player.png")} />
        </div>
      </div>
    </>
  );
};

export default PlayerSection;
