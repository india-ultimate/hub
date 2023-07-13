import { useNavigate } from "@solidjs/router";
import { createSignal, createEffect, Show } from "solid-js";
import { getCookie } from "../utils";
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

  fetch("/api/user", {
    method: "GET",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin"
  })
    .then(response => {
      if (response.status == 200) {
        setLoggedIn(true);
        response.json().then(data => {
          console.log(data);
          setData(data);
        });
      } else {
        setLoggedIn(false);
      }
    })
    .catch(error => {
      console.log(error);
      setLoggedIn(false);
    });

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
