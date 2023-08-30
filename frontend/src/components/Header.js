import { Show } from "solid-js";
import { useStore } from "../store";
import { getCookie } from "../utils";
import { A } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { bars_3, moon, sun } from "solid-heroicons/solid-mini";

const assetURL = name =>
  process.env.NODE_ENV === "production" // eslint-disable-line no-undef
    ? `/static/assets/${name}`
    : `/assets/${name}`;

export default function Header() {
  const [store, { setLoggedIn, setData, setTheme }] = useStore();

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
      setLoggedIn(false);
      setData({});
    }
  };

  const toggleTheme = () => {
    if (store.theme === "dark") setTheme("light");
    else setTheme("dark");
  };

  return (
    <div>
      <nav class="border-gray-200 bg-gray-50 dark:bg-gray-800 dark:border-gray-700">
        <div class="max-w-screen-xl flex flex-wrap items-center justify-between mx-auto p-4">
          <A href="/" class="flex items-center">
            <img
              src={assetURL("logo-vertical.png")}
              class="h-8 mr-3 block dark:hidden"
              alt="UPAI Logo"
            />
            <img
              src={assetURL("logo-vertical.jpg")}
              class="h-8 mr-3 hidden dark:block"
              alt="UPAI Logo"
            />
            <span class="self-center text-2xl font-semibold whitespace-nowrap dark:text-white">
              Hub
            </span>
          </A>
          <div>
            <button
              type="button"
              class="inline-flex items-center p-2 w-10 h-10 justify-center text-sm text-gray-500 rounded-lg md:hidden hover:bg-gray-100 focus:outline-none dark:text-gray-400 dark:hover:bg-gray-700 dark:focus:ring-gray-600"
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
              class="inline-flex items-center p-2 w-10 h-10 justify-center text-sm text-gray-500 rounded-lg md:hidden hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-200 dark:text-gray-400 dark:hover:bg-gray-700 dark:focus:ring-gray-600"
              aria-controls="navbar-solid-bg"
              aria-expanded="false"
            >
              <span class="sr-only">Open main menu</span>
              <Icon path={bars_3} style={{ width: "24px" }} />
            </button>
          </div>
          <div class="hidden w-full md:block md:w-auto" id="navbar-solid-bg">
            <ul class="flex flex-col font-medium mt-4 rounded-lg bg-gray-50 md:flex-row md:space-x-8 md:mt-0 md:border-0 md:bg-transparent dark:bg-gray-800 md:dark:bg-transparent dark:border-gray-700">
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
                <Show
                  when={store.loggedIn}
                  fallback={
                    <A
                      href="/login"
                      class="block py-2 pl-3 pr-4 text-gray-900 rounded hover:bg-gray-100 md:hover:bg-transparent md:border-0 md:hover:text-blue-700 md:p-0 dark:text-white md:dark:hover:text-blue-500 dark:hover:bg-gray-700 dark:hover:text-white md:dark:hover:bg-transparent"
                    >
                      Login
                    </A>
                  }
                >
                  <A
                    href=""
                    class="block py-2 pl-3 pr-4 text-gray-900 rounded hover:bg-gray-100 md:hover:bg-transparent md:border-0 md:hover:text-blue-700 md:p-0 dark:text-white md:dark:hover:text-blue-500 dark:hover:bg-gray-700 dark:hover:text-white md:dark:hover:bg-transparent"
                    onClick={logout}
                  >
                    Logout
                  </A>
                </Show>
              </li>
              <li>
                <button
                  type="button"
                  class="hidden md:block py-2 pl-3 pr-4 text-gray-900 rounded md:border-0 md:hover:text-blue-700 md:p-0 dark:text-white md:dark:hover:text-blue-500 focus:outline-none"
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
