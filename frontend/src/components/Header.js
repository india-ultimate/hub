import { A } from "@solidjs/router";
import { createSignal, Show } from "solid-js";

import { Hamburger, XMark } from "../icons";
import { useStore } from "../store";
import { assetURL, fetchUserData } from "../utils";

export default function Header() {
  const [store, { userFetchSuccess }] = useStore();
  const [hamburgerOpen, setHamburgerOpen] = createSignal(false);

  // const toggleTheme = () => {
  //   if (store.theme === "dark") setTheme("light");
  //   else setTheme("dark");
  // };

  fetchUserData(userFetchSuccess, () => {});

  return (
    <div>
      <nav class="border-gray-200 bg-gray-50 dark:border-gray-700 dark:bg-gray-800">
        <div class="mx-auto flex max-w-screen-xl flex-wrap items-center justify-between border-b border-gray-200 px-4 py-2 md:border-b-0 md:py-4">
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
          <div class="flex items-center">
            {/* <button
              type="button"
              class="inline-flex h-12 w-12 items-center justify-center rounded-lg p-2 text-sm text-gray-500 hover:bg-gray-100 focus:outline-none dark:text-gray-400 dark:hover:bg-gray-700 dark:focus:ring-gray-600 md:hidden"
              onClick={toggleTheme}
            >
              <Show
                when={store.theme === "dark"}
                fallback={<Icon path={moon} style={{ width: "24px" }} />}
              >
                <Icon path={sun} style={{ width: "24px" }} />
              </Show>
            </button> */}
            <Show
              when={store.loggedIn}
              fallback={
                <A
                  href="/login"
                  class="me-2 h-fit rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-800  focus:outline-none dark:bg-blue-600  dark:hover:bg-blue-700 md:hidden"
                >
                  Login
                </A>
              }
            >
              <A
                href="/dashboard"
                class="inline-flex h-12 w-12 items-center justify-center rounded-lg p-2 text-sm text-gray-500  focus:outline-none dark:text-gray-400  md:hidden"
              >
                <img
                  class="rounded-full"
                  src={
                    store?.data?.player?.uc_person?.image_url ||
                    "https://secure.gravatar.com/avatar/04d7b508acc28c747e55a9d1d81cdd4a?s=200&d=mm&r=r"
                  }
                  alt="Rounded avatar"
                />
              </A>
            </Show>
            <button
              data-collapse-toggle="navbar-solid-bg"
              type="button"
              class="inline-flex h-12 w-12 items-center justify-center rounded-lg p-2 text-sm text-gray-500 hover:bg-gray-100 focus:outline-none dark:text-gray-400 dark:hover:bg-gray-700 md:hidden"
              aria-controls="navbar-solid-bg"
              aria-expanded="false"
              onClick={() => setHamburgerOpen(!hamburgerOpen())}
            >
              <span class="sr-only">Open main menu</span>
              <Show when={!hamburgerOpen()} fallback={<XMark />}>
                <Hamburger />
              </Show>
            </button>
          </div>
          <div class="hidden w-full md:block md:w-auto" id="navbar-solid-bg">
            <ul class="mt-4 flex flex-col rounded-lg bg-gray-50 font-medium dark:border-gray-700 dark:bg-gray-800 md:mt-0 md:flex-row md:space-x-8 md:border-0 md:bg-transparent md:dark:bg-transparent">
              <li class="flex items-center">
                <A
                  href="/"
                  activeClass="w-full block py-2 rounded bg-transparent text-blue-700 md:p-0 dark:text-blue-500 underline underline-offset-8 font-bold decoration-2"
                  inactiveClass="w-full block py-2 text-gray-900 rounded md:hover:bg-transparent md:border-0 md:hover:text-blue-700 md:p-0 dark:text-white md:dark:hover:text-blue-500 md:dark:hover:bg-transparent"
                  end={true}
                >
                  Home
                </A>
              </li>
              <li class="flex items-center">
                <A
                  href="/teams"
                  activeClass="w-full block py-2 rounded bg-transparent text-blue-700 md:p-0 dark:text-blue-500 underline underline-offset-8 font-bold decoration-2"
                  inactiveClass="w-full block py-2 text-gray-900 rounded md:hover:bg-transparent md:border-0 md:hover:text-blue-700 md:p-0 dark:text-white md:dark:hover:text-blue-500 md:dark:hover:bg-transparent"
                  end={true}
                >
                  Teams
                </A>
              </li>
              <li class="flex items-center">
                <A
                  href="/series"
                  activeClass="w-full block py-2 rounded bg-transparent text-blue-700 md:p-0 dark:text-blue-500 underline underline-offset-8 font-bold decoration-2"
                  inactiveClass="w-full block py-2 text-gray-900 rounded md:hover:bg-transparent md:border-0 md:hover:text-blue-700 md:p-0 dark:text-white md:dark:hover:text-blue-500 md:dark:hover:bg-transparent"
                  end={true}
                >
                  Series
                </A>
              </li>
              <li class="flex items-center">
                <A
                  href="/tournaments"
                  activeClass="w-full block py-2 rounded bg-transparent text-blue-700 md:p-0 dark:text-blue-500 underline underline-offset-8 font-bold decoration-2"
                  inactiveClass="w-full block py-2 text-gray-900 rounded md:hover:bg-transparent md:border-0 md:hover:text-blue-700 md:p-0 dark:text-white md:dark:hover:text-blue-500 md:dark:hover:bg-transparent"
                  end={true}
                >
                  Tournaments
                </A>
              </li>
              <li class="flex items-center">
                <A
                  href="/chat"
                  activeClass="w-full block py-2 rounded bg-transparent text-blue-700 md:p-0 dark:text-blue-500 underline underline-offset-8 font-bold decoration-2"
                  inactiveClass="w-full block py-2 text-gray-900 rounded md:hover:bg-transparent md:border-0 md:hover:text-blue-700 md:p-0 dark:text-white md:dark:hover:text-blue-500 md:dark:hover:bg-transparent"
                  end={true}
                >
                  AI Chat
                </A>
              </li>
              <li class="flex items-center">
                <A
                  href="/tickets"
                  activeClass="w-full block py-2 rounded bg-transparent text-blue-700 md:p-0 dark:text-blue-500 underline underline-offset-8 font-bold decoration-2"
                  inactiveClass="w-full block py-2 text-gray-900 rounded md:hover:bg-transparent md:border-0 md:hover:text-blue-700 md:p-0 dark:text-white md:dark:hover:text-blue-500 md:dark:hover:bg-transparent"
                  end={true}
                >
                  Help
                </A>
              </li>
              <li class="mb-4 md:hidden">
                <A
                  href={store.loggedIn ? "/dashboard" : "/login"}
                  activeClass="block py-2 rounded bg-transparent text-blue-700 md:p-0 dark:text-blue-500 underline underline-offset-8 font-bold decoration-2"
                  inactiveClass="block py-2 text-gray-900 rounded md:hover:bg-transparent md:border-0 md:hover:text-blue-700 md:p-0 dark:text-white md:dark:hover:text-blue-500 md:dark:hover:bg-transparent"
                  end={true}
                >
                  My account
                </A>
              </li>
              <li>
                <Show
                  when={store.loggedIn}
                  fallback={
                    <A
                      href="/login"
                      class="mb-2 me-2 hidden rounded-lg bg-blue-700 px-5 py-2.5 text-sm font-medium text-white  hover:bg-blue-800 dark:bg-blue-600 dark:hover:bg-blue-700 md:inline"
                    >
                      Login
                    </A>
                  }
                >
                  <A
                    href="/dashboard"
                    id="my-account"
                    data-tooltip-target="tooltip-my-account"
                    class="hidden rounded py-2 pl-3 pr-4 text-gray-900 focus:outline-none dark:text-white md:block md:border-0 md:p-0 md:hover:text-blue-700 md:dark:hover:text-blue-500"
                  >
                    <img
                      class="rounded-full"
                      style={{ width: "36px" }}
                      src={
                        store?.data?.player?.uc_person?.image_url ||
                        "https://secure.gravatar.com/avatar/04d7b508acc28c747e55a9d1d81cdd4a?s=200&d=mm&r=r"
                      }
                      alt="Rounded avatar"
                    />
                  </A>
                </Show>
              </li>
              <div
                id="tooltip-my-account"
                role="tooltip"
                class="tooltip invisible absolute z-10 inline-block rounded-lg bg-gray-900 px-3 py-2 text-sm font-medium text-white opacity-0 shadow-sm transition-opacity duration-300 dark:bg-gray-700"
              >
                My account
                <div class="tooltip-arrow" data-popper-arrow />
              </div>
              {/* <li>
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
              </li> */}
            </ul>
          </div>
        </div>
      </nav>
    </div>
  );
}
