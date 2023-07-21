import { useNavigate, A } from "@solidjs/router";
import { createSignal, createEffect, onMount, Show } from "solid-js";
import { getCookie, fetchUserData } from "../utils";
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
    }
  };

  return (
    <div>
      <h1 class="text-4xl font-bold mb-4 text-red-500">
        Welcome, {store.data.first_name} {store.data.last_name}!
      </h1>
      <div>
        <Show
          when={!store.data.player}
          fallback={
            <div>
              <Player player={store.data.player} />
            </div>
          }
        >
          <h3 class="text-2xl font-bold mb-4">
            Want to play?{" "}
            <A
              href="/registration"
              class="font-medium text-blue-600 dark:text-blue-500 hover:underline"
            >
              Register!
            </A>
          </h3>
        </Show>
      </div>
      <button class="my-10" onClick={logout}>
        Logout
      </button>
    </div>
  );
};

export default Home;
