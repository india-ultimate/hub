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
      const data = await response.json();
      setStatus(`Login failed with error: ${data.message}`);
      setLoggedIn(false);
    }
  };

  return (
    <>
      <form onSubmit={login}>
        <input
          placeholder="username"
          value={username()}
          onInput={e => setUsername(e.currentTarget.value)}
        />
        <input
          placeholder="password"
          type="password"
          required
          value={password()}
          onInput={e => setPassword(e.currentTarget.value)}
        />
        <button>Login</button>
      </form>
      <p>{status()}</p>
    </>
  );
};

export default Login;
