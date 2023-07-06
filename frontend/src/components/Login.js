import { getCookie } from "../utils.js";
import { createSignal, createEffect } from "solid-js";
import { useNavigate } from "@solidjs/router";

const Login = () => {
  const csrftoken = getCookie("csrftoken");
  const [username, setUsername] = createSignal("");
  const [password, setPassword] = createSignal("");
  const [status, setStatus] = createSignal("");
  const [loggedIn, setLoggedIn] = createSignal(false);

  createEffect(() => {
    if (loggedIn()) {
      const navigate = useNavigate();
      navigate("/", { replace: true });
    }
  });

  const login = async e => {
    e.preventDefault();
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrftoken },
      body: JSON.stringify({
        username: username(),
        password: password()
      })
    });

    if (response.ok) {
      setStatus(`Successfully logged in!`);
      setLoggedIn(true);
    } else {
      setLoggedIn(false);
      try {
        const data = await response.json();
        setStatus(`Login failed with error: ${data.message}`);
      } catch {
        setStatus(
          `Login failed with error: ${response.statusText} (${response.status})`
        );
      }
    }
  };

  return (
    <>
      <form onSubmit={login}>
        <div class="grid gap-3 mb-6">
          <label for="username" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Username</label>
          <div class="mb-6">
            <input
              id="username"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              placeholder="username"
              value={username()}
              onInput={e => setUsername(e.currentTarget.value)}
            />
          </div>
          <label for="password" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Password</label>
          <div class="mb-6">
            <input
              id="password"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              placeholder="password"
              type="password"
              required
              value={password()}
              onInput={e => setPassword(e.currentTarget.value)}
            />
          </div>
          <button
            type="submit"
            class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
          >Login
          </button>
        </div>
      </form>
      <p>{status()}</p>
    </>
  );
};

export default Login;
