import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { bars_3, moon, sun } from "solid-heroicons/solid-mini";
import { Show } from "solid-js";

import { useStore } from "../store";
import { assetURL, fetchUserData, getCookie } from "../utils";

export default function Header() {
  const [store, { userFetchSuccess, userFetchFailure, setTheme }] = useStore();

  const logout = async () => {
    const response = await fetch("/api/logout", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin"
    });
    if (response.status == 200) {
      userFetchFailure();
      // NOTE: we reload the page to ensure the store is empty. Doesn't seem to
      // happen with just setData, for some reason?!
      window.location = "/";
    }
  };

  const toggleTheme = () => {
    if (store.theme === "dark") setTheme("light");
    else setTheme("dark");
  };

  fetchUserData(userFetchSuccess, () => {});

  return (
    <div>
      <nav class="border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800">
        <div class="mx-auto flex max-w-screen-xl flex-wrap items-center justify-between p-4">
          <A href="/" class="flex items-center">
            <img
              src={assetURL("logo-vertical.png")}
              class="mr-3 block h-8 dark:hidden"
              alt="India Ultimate Logo"
            />
            <img
              src={assetURL("white-logo-vertical.jpg")}
              class="mr-3 hidden h-8 rounded dark:block"
              alt="India Ultimate Logo"
            />
            <span class="self-center whitespace-nowrap text-2xl font-semibold dark:text-white">
              Hub
            </span>
          </A>
          <div>
            <button
              type="button"
              class="inline-flex h-10 w-10 items-center justify-center rounded-lg p-2 text-sm text-gray-500 hover:bg-gray-100 focus:outline-none dark:text-gray-400 dark:hover:bg-gray-700 dark:focus:ring-gray-600 md:hidden"
              onClick={toggleTheme}
            >
              <Show
                when={store.theme === "dark"}
                fallback={<Icon path={moon} style={{ width: "24px" }} />}
              >
                <Icon path={sun} style={{ width: "24px" }} />
              </Show>
            </button>
            <button
              data-collapse-toggle="navbar-solid-bg"
              type="button"
              class="inline-flex h-10 w-10 items-center justify-center rounded-lg p-2 text-sm text-gray-500 hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-200 dark:text-gray-400 dark:hover:bg-gray-700 dark:focus:ring-gray-600 md:hidden"
              aria-controls="navbar-solid-bg"
              aria-expanded="false"
            >
              <span class="sr-only">Open main menu</span>
              <Icon path={bars_3} style={{ width: "24px" }} />
            </button>
          </div>
          <div class="hidden w-full md:block md:w-auto" id="navbar-solid-bg">
            <ul class="mt-4 flex flex-col rounded-lg bg-gray-50 font-medium dark:border-gray-700 dark:bg-gray-800 md:mt-0 md:flex-row md:space-x-8 md:border-0 md:bg-transparent md:dark:bg-transparent">
              <li>
                <A
                  href="/"
                  activeClass="block py-2 pl-3 pr-4 text-white bg-blue-700 rounded md:bg-transparent md:text-blue-700 md:p-0 md:dark:text-blue-500 dark:bg-blue-600 md:dark:bg-transparent"
                  inactiveClass="block py-2 pl-3 pr-4 text-gray-900 rounded hover:bg-gray-100 md:hover:bg-transparent md:border-0 md:hover:text-blue-700 md:p-0 dark:text-white md:dark:hover:text-blue-500 dark:hover:bg-gray-700 dark:hover:text-white md:dark:hover:bg-transparent"
                  end={true}
                >
                  Home
                </A>
              </li>
              <li>
                <A
                  href="/dashboard"
                  activeClass="block py-2 pl-3 pr-4 text-white bg-blue-700 rounded md:bg-transparent md:text-blue-700 md:p-0 md:dark:text-blue-500 dark:bg-blue-600 md:dark:bg-transparent"
                  inactiveClass="block py-2 pl-3 pr-4 text-gray-900 rounded hover:bg-gray-100 md:hover:bg-transparent md:border-0 md:hover:text-blue-700 md:p-0 dark:text-white md:dark:hover:text-blue-500 dark:hover:bg-gray-700 dark:hover:text-white md:dark:hover:bg-transparent"
                  end={true}
                >
                  Dashboard
                </A>
              </li>
              <li>
                <A
                  href="/tournaments"
                  activeClass="block py-2 pl-3 pr-4 text-white bg-blue-700 rounded md:bg-transparent md:text-blue-700 md:p-0 md:dark:text-blue-500 dark:bg-blue-600 md:dark:bg-transparent"
                  inactiveClass="block py-2 pl-3 pr-4 text-gray-900 rounded hover:bg-gray-100 md:hover:bg-transparent md:border-0 md:hover:text-blue-700 md:p-0 dark:text-white md:dark:hover:text-blue-500 dark:hover:bg-gray-700 dark:hover:text-white md:dark:hover:bg-transparent"
                  end={true}
                >
                  Tournaments
                </A>
              </li>
              <li>
                <Show
                  when={store.loggedIn}
                  fallback={
                    <A
                      href="/login"
                      class="block rounded py-2 pl-3 pr-4 text-gray-900 hover:bg-gray-100 dark:text-white dark:hover:bg-gray-700 dark:hover:text-white md:border-0 md:p-0 md:hover:bg-transparent md:hover:text-blue-700 md:dark:hover:bg-transparent md:dark:hover:text-blue-500"
                    >
                      Login
                    </A>
                  }
                >
                  <A
                    href=""
                    class="block rounded py-2 pl-3 pr-4 text-gray-900 hover:bg-gray-100 dark:text-white dark:hover:bg-gray-700 dark:hover:text-white md:border-0 md:p-0 md:hover:bg-transparent md:hover:text-blue-700 md:dark:hover:bg-transparent md:dark:hover:text-blue-500"
                    onClick={logout}
                  >
                    Logout
                  </A>
                </Show>
              </li>
              <li>
                <button
                  type="button"
                  class="hidden rounded py-2 pl-3 pr-4 text-gray-900 focus:outline-none dark:text-white md:block md:border-0 md:p-0 md:hover:text-blue-700 md:dark:hover:text-blue-500"
                  onClick={toggleTheme}
                >
                  <Show
                    when={store.theme === "dark"}
                    fallback={<Icon path={moon} style={{ width: "24px" }} />}
                  >
                    <Icon path={sun} style={{ width: "24px" }} />
                  </Show>
                </button>
              </li>
            </ul>
          </div>
        </div>
      </nav>
    </div>
  );
}
