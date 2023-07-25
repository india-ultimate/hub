import { useNavigate, A } from "@solidjs/router";
import { createSignal, createEffect, onMount, Show } from "solid-js";
import { fetchUserData } from "../utils";
import { useStore } from "../store";
import Player from "./Player";

const Home = () => {
  const [store, { setLoggedIn, setData }] = useStore();

  createEffect(() => {
    if (!store.loggedIn) {
      const navigate = useNavigate();
      navigate("/login", { replace: true });
    }
  });

  onMount(() => {
    if (!store?.data?.username) {
      fetchUserData(setLoggedIn, setData);
    }
  });

  return (
    <div>
      <h1 class="text-4xl font-bold mb-4 text-red-500">
        Welcome {store?.data?.full_name || store?.data?.username}!
      </h1>
      <div class="relative overflow-x-auto">
        <table class="w-full text-sm text-left text-gray-500 dark:text-gray-400">
          <tbody>
            <Show when={!store.data.player}>
              <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
                <th
                  scope="row"
                  class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
                >
                  <A
                    href="/registration/me"
                    class="font-medium text-blue-600 dark:text-blue-500 hover:underline"
                  >
                    Register yourself as a player
                  </A>
                </th>
              </tr>
            </Show>
            <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
              <th
                scope="row"
                class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
              >
                <A
                  href="/registration/others"
                  class="font-medium text-blue-600 dark:text-blue-500 hover:underline"
                >
                  Fill the membership form for another player
                </A>
              </th>
            </tr>
            <tr class="bg-white border-b dark:bg-gray-800 dark:border-gray-700">
              <th
                scope="row"
                class="px-6 py-4 font-medium text-gray-900 whitespace-nowrap dark:text-white"
              >
                <A
                  href=""
                  class="font-medium text-blue-600 dark:text-blue-500 hover:underline cursor-not-allowed"
                  disabled
                >
                  Fill the membership form as a guardian
                </A>
              </th>
              <td class="px-6 py-4" />
            </tr>
          </tbody>
        </table>
      </div>
      <Show when={store.data.player}>
        <div class="mt-5">
          <h2 class="text-2xl font-bold mb-4 text-black-500">
            Player information
          </h2>
          <div>
            <Player player={store.data.player} />
          </div>
        </div>
      </Show>
    </div>
  );
};

export default Home;
