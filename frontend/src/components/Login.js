import { getCookie, loginWithFirebaseResponse, firebaseConfig } from "../utils";
import { useStore } from "../store";
import { createSignal, createEffect, onMount } from "solid-js";
import { useNavigate } from "@solidjs/router";
import { initializeApp } from "firebase/app";
import {
  getAuth,
  RecaptchaVerifier,
  sendSignInLinkToEmail,
  signInWithPhoneNumber
} from "firebase/auth";
import { initFlowbite } from "flowbite";

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

const SendEmailLink = ({ setStatus }) => {
  const [email, setEmail] = createSignal("");
  let url = new URL(window.location);
  url.hash = "#/email-link";
  const sendFirebaseEmailLink = e => {
    e.preventDefault();
    const actionCodeSettings = {
      // URL you want to redirect back to. The domain (www.example.com) for this
      // URL must be in the authorized domains list in the Firebase Console.
      url: url.toString(),
      // This must be true.
      handleCodeInApp: true
    };

    // console.log(auth, email, actionCodeSettings);

    sendSignInLinkToEmail(auth, email(), actionCodeSettings)
      .then(() => {
        // The link was successfully sent. Inform the user.
        setStatus(`Email was successfully sent to ${email()}`);
        // Save the email locally so you don't need to ask the user for it
        // again if they open the link on the same device.
        window.localStorage.setItem("emailForSignIn", email());
      })
      .catch(error => {
        setStatus(
          `Failed to send email to ${email()}: ${error.code}; ${error.message}`
        );
      });
  };

  return (
    <form onSubmit={sendFirebaseEmailLink}>
      <div class="grid gap-3 mb-6">
        <label
          for="email-link-input"
          class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
        >
          Enter Email ID for sending login link
        </label>
        <div class="mb-6">
          <input
            class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            id="email-link-input"
            placeholder="Email Address"
            value={email()}
            onInput={e => setEmail(e.currentTarget.value)}
          />
        </div>

        <button
          type="submit"
          class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
        >
          Send Email
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
      .then(async response =>
        loginWithFirebaseResponse(response, setStatus, setLoggedIn, setData)
      )
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

  const signInFailed = window.localStorage.getItem("emailSignInFailed");
  if (signInFailed) {
    setStatus(signInFailed);
    window.localStorage.removeItem("emailSignInFailed");
  }

  createEffect(() => {
    if (store.loggedIn) {
      const navigate = useNavigate();
      // FIXME: query params are not cleared with hashrouter!
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
              id="email-link-tab"
              data-tabs-target="#email-link"
              type="button"
              role="tab"
              aria-controls="email-link"
              aria-selected="false"
            >
              Email-Link
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
          id="email-link"
          role="tabpanel"
          aria-labelledby="email-link-tab"
        >
          <SendEmailLink setStatus={setStatus} />
        </div>
        <div
          class="hidden p-4 rounded-lg bg-gray-50 dark:bg-gray-800"
          id="phone"
          role="tabpanel"
          aria-labelledby="phone-tab"
        >
          <SendPhoneConfirmation setStatus={setStatus} />
          <p>
            Note: The free Firebase plan only allows for 10 SMS/day. Use the
            email login feature, if you can.
          </p>
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
