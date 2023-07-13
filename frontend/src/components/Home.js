import { useNavigate } from "@solidjs/router";
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
    if (!store.loggedIn) {
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
      <Show when={store.data.player}>
        <Player player={store.data.player} />
      </Show>
      <button class="my-10" onClick={logout}>
        Logout
      </button>
    </div>
  );
};

export default Home;
