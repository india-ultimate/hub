import { getCookie } from "../utils.js";
import { useStore } from "../store.js";
import { createSignal, createEffect, onMount } from "solid-js";
import { useNavigate } from "@solidjs/router";
import { initializeApp } from "firebase/app";
import {
  getAuth,
  RecaptchaVerifier,
  signInWithPhoneNumber
} from "firebase/auth";
import { initFlowbite } from "flowbite";

// Your web app's Firebase configuration
const firebaseConfig = {
  apiKey: "AIzaSyB5iRXnIckzjZMOthOUc3d4tCIaO2blLCA",
  authDomain: "india-ultimate-hub.firebaseapp.com",
  projectId: "india-ultimate-hub",
  storageBucket: "india-ultimate-hub.appspot.com",
  messagingSenderId: "677703680955",
  appId: "1:677703680955:web:9014c1e57b3e04e7873a9e"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
auth.useDeviceLanguage();

const PasswordLogin = ({ setStatus }) => {
  const csrftoken = getCookie("csrftoken");
  const [username, setUsername] = createSignal("");
  const [password, setPassword] = createSignal("");
  const [store, { setLoggedIn, setData }] = useStore();

  createEffect(() => {
    if (store.loggedIn) {
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
      const data = await response.json();
      setData(data);
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
    <form onSubmit={login}>
      <div class="grid gap-3 mb-6">
        <label
          for="username-input"
          class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
        >
          Username
        </label>
        <div class="mb-6">
          <input
            id="username-input"
            class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            placeholder="username"
            value={username()}
            onInput={e => setUsername(e.currentTarget.value)}
          />
        </div>
        <label
          for="password-input"
          class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
        >
          Password
        </label>
        <div class="mb-6">
          <input
            id="password-input"
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
        >
          Login
        </button>
      </div>
    </form>
  );
};

const SendPhoneConfirmation = ({ setStatus }) => {
  const [phone, setPhone] = createSignal("+91");
  const [code, setCode] = createSignal("");
  const [verifier, setVerifier] = createSignal();
  const [confirmationResult, setConfirmationResult] = createSignal();
  const [store, { setLoggedIn, setData }] = useStore();

  const auth = getAuth();
  auth.useDeviceLanguage();
  createEffect(() => {
    setVerifier(new RecaptchaVerifier("recaptcha-container", {}, auth));
  });

  const onSignInSubmit = e => {
    e.preventDefault();
    signInWithPhoneNumber(auth, phone(), verifier())
      .then(confirmationResult => {
        setConfirmationResult(confirmationResult);
        setStatus(`Confirmation code has been sent to ${phone()}`);
      })
      .catch(error => {
        // Error; SMS not sent
        console.log(error);
        setStatus(`Failed to send code: ${error}`);
        verifier()
          .render()
          .then(function(widgetId) {
            grecaptcha.reset(widgetId);
          });
        setConfirmationResult();
      });
  };

  const confirmResult = e => {
    e.preventDefault();
    console.log(e);
    confirmationResult()
      .confirm(code())
      .then(async firebaseResponse => {
        const { user: { uid, accessToken: token } } = firebaseResponse;
        const response = await fetch("/api/firebase-login", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRFToken": getCookie("csrftoken")
          },
          body: JSON.stringify({ uid, token })
        });

        if (response.ok) {
          setStatus(`Successfully logged in!`);
          const data = await response.json();
          setData(data);
          setLoggedIn(true);
        } else {
          setLoggedIn(false);
          try {
            const data = await response.json();
            setStatus(`Login failed with error: ${data.message}`);
          } catch {
            setStatus(
              `Login failed with error: ${response.statusText} (${
                response.status
              })`
            );
          }
        }
      })
      .catch(error => {
        setStatus(`Login failed: ${error}`);
        console.log(error);
      });
  };

  return (
    <>
      {!confirmationResult() && (
        <form onSubmit={onSignInSubmit}>
          <div class="grid gap-3 mb-6">
            <label
              for="phone-number-input"
              class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
            >
              Mobile Number
            </label>

            <input
              id="phone-number-input"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              placeholder="Phone Number"
              value={phone()}
              onInput={e => setPhone(e.currentTarget.value)}
            />
            <button
              id="phone-signin-button"
              type="submit"
              class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
            >
              Send Confirmation Code
            </button>
            <div class="py-2.5" id="recaptcha-container" />
          </div>
        </form>
      )}
      {confirmationResult() && (
        <form onSubmit={confirmResult}>
          <div class="grid gap-3 mb-6">
            <label
              for="confirmation-code-input"
              class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
            >
              Enter Confirmation Code sent via SMS
            </label>
            <input
              id="confirmation-code-input"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              placeholder="Confirmation Code"
              value={code()}
              onInput={e => setCode(e.currentTarget.value)}
            />
            <button
              type="submit"
              class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
            >
              Verify Confirmation Code
            </button>
          </div>
        </form>
      )}
    </>
  );
};

const Login = () => {
  const [status, setStatus] = createSignal("");
  const [store, { setLoggedIn, setData }] = useStore();

  createEffect(() => {
    if (store.loggedIn) {
      const navigate = useNavigate();
      navigate("/", { replace: true });
    }
  });

  onMount(async () => {
    initFlowbite();
  });

  return (
    <>
      <div class="mb-4 border-b border-gray-200 dark:border-gray-700">
        <ul
          class="flex flex-wrap -mb-px text-sm font-medium text-center"
          id="signinTabs"
          data-tabs-toggle="#signinTabContent"
          role="tablist"
        >
          <li class="mr-2" role="presentation">
            <button
              class="inline-block p-4 border-b-2 rounded-t-lg"
              id="phone-tab"
              data-tabs-target="#phone"
              type="button"
              role="tab"
              aria-controls="phone"
              aria-selected="false"
            >
              Phone
            </button>
          </li>
          <li class="mr-2" role="presentation">
            <button
              class="inline-block p-4 border-b-2 border-transparent rounded-t-lg hover:text-gray-600 hover:border-gray-300 dark:hover:text-gray-300"
              id="password-tab"
              data-tabs-target="#password"
              type="button"
              role="tab"
              aria-controls="password"
              aria-selected="false"
            >
              Password
            </button>
          </li>
        </ul>
      </div>
      <div id="signinTabContent">
        <div
          class="hidden p-4 rounded-lg bg-gray-50 dark:bg-gray-800"
          id="phone"
          role="tabpanel"
          aria-labelledby="phone-tab"
        >
          <SendPhoneConfirmation setStatus={setStatus} />
        </div>
        <div
          class="hidden p-4 rounded-lg bg-gray-50 dark:bg-gray-800"
          id="password"
          role="tabpanel"
          aria-labelledby="password-tab"
        >
          <PasswordLogin setStatus={setStatus} />
        </div>
      </div>
      <p>{status()}</p>
    </>
  );
};

export default Login;
