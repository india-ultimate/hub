import {
  get,
  parseRequestOptionsFromJSON,
  supported
} from "@github/webauthn-json/browser-ponyfill";
import { useNavigate } from "@solidjs/router";
import { initFlowbite } from "flowbite";
import { Icon } from "solid-heroicons";
import { eye, eyeSlash, fingerPrint, home } from "solid-heroicons/solid";
import { createEffect, createSignal, onMount, Show } from "solid-js";

import { Spinner } from "../icons";
import { useStore } from "../store";
import { getCookie } from "../utils";
import Breadcrumbs from "./Breadcrumbs";

const PasswordLogin = props => {
  const csrftoken = getCookie("csrftoken");
  const [username, setUsername] = createSignal("");
  const [password, setPassword] = createSignal("");
  const [store, { setLoggedIn, setData }] = useStore();
  const [showPassword, setShowPassword] = createSignal(false);

  createEffect(() => {
    if (store.loggedIn) {
      const navigate = useNavigate();
      const redirect = new URL(window.location.href).searchParams.get(
        "redirect"
      );
      const isSafe =
        redirect && redirect.startsWith("/") && !redirect.startsWith("//");
      navigate(isSafe ? redirect : "/dashboard", { replace: true });
    }
  });

  const login = async e => {
    e.preventDefault();
    const response = await fetch("/api/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrftoken
      },
      body: JSON.stringify({
        username: username()?.trim(),
        password: password()
      })
    });

    if (response.ok) {
      props.setStatus("Successfully logged in!");
      const data = await response.json();
      setData(data);
      setLoggedIn(true);
    } else {
      setLoggedIn(false);
      try {
        const data = await response.json();
        props.setStatus(`Login failed with error: ${data.message}`);
      } catch {
        props.setStatus(
          `Login failed with error: ${response.statusText} (${response.status})`
        );
      }
    }
  };
  return (
    <form onSubmit={login}>
      <div class="mb-6 grid gap-3">
        <label
          for="email"
          class="mb-2 block text-sm font-medium text-gray-900 dark:text-white"
        >
          Email
        </label>
        <div class="mb-6">
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="username"
            class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
            placeholder="johndoe@gmail.com"
            value={username()}
            onInput={e => setUsername(e.currentTarget.value)}
          />
        </div>
        <label
          for="current-password"
          class="mb-2 block text-sm font-medium text-gray-900 dark:text-white"
        >
          Password
        </label>
        <div class="relative mb-6">
          <div class="absolute inset-y-0 right-0 flex items-center px-2">
            <input
              class="hidden"
              id="toggle"
              type="checkbox"
              onClick={() => setShowPassword(prevValue => !prevValue)}
            />
            <label
              class="cursor-pointer rounded px-2 py-1 font-mono text-sm text-gray-600 dark:text-gray-200"
              for="toggle"
            >
              <Icon path={showPassword() ? eyeSlash : eye} class="h-5 w-5" />
            </label>
          </div>
          <input
            id="current-password"
            autoComplete="current-password"
            class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
            placeholder="password"
            type={showPassword() ? "text" : "password"}
            required
            value={password()}
            onInput={e => setPassword(e.currentTarget.value)}
          />
        </div>
        <button
          type="submit"
          class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
        >
          Login
        </button>
      </div>
      <div
        class="mb-4 rounded-lg bg-yellow-50 p-4 text-sm text-yellow-800 dark:bg-gray-800 dark:text-yellow-300"
        role="alert"
      >
        Kindly use the Google Login option or request an Email-Link for logging
        in. This is a login page for admins or users having trouble using other
        methods to login. Your Ultimate Central credentials cannot be used to
        login from this page.
      </div>
    </form>
  );
};

const SendEmailOTP = props => {
  const csrftoken = getCookie("csrftoken");
  const [email, setEmail] = createSignal("");
  const [otp, setOtp] = createSignal("");
  const [checkSpam, setCheckSpam] = createSignal(false);
  const [loading, setLoading] = createSignal(false);
  const [otpData, setOtpData] = createSignal();
  const [store, { setLoggedIn, setData }] = useStore();
  const [enableRetry, setEnableRetry] = createSignal(false);
  const [forumLogin, setForumLogin] = createSignal(false);

  createEffect(() => {
    const redirect = new URL(window.location.href).searchParams.get("redirect");

    if (redirect && redirect.includes("forum")) {
      setForumLogin(true);
    }

    if (store.loggedIn) {
      const navigate = useNavigate();
      const isSafe =
        redirect && redirect.startsWith("/") && !redirect.startsWith("//");
      navigate(isSafe ? redirect : "/dashboard", { replace: true });
    }
  });

  let url = new URL(window.location);
  url.pathname = "/email-otp";

  const sendOTPEmail = async e => {
    e.preventDefault();
    setLoading(true);

    const response = await fetch("/api/send-otp", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrftoken
      },
      body: JSON.stringify({
        email: email()?.trim().toLowerCase()
      })
    });

    if (response.ok) {
      props.setStatus("Successfully sent otp!");
      const data = await response.json();
      setOtpData(data);
      setCheckSpam(true);
      setEnableRetry(false);
      setTimeout(() => setEnableRetry(true), 10000);
    } else {
      try {
        const data = await response.json();
        props.setStatus(`OTP sending failed with error: ${data.message}`);
      } catch {
        props.setStatus(
          `OTP sending failed with error: ${response.statusText} (${response.status})`
        );
      }
    }
    setLoading(false);
  };

  const validateOTP = async e => {
    e.preventDefault();

    const response = await fetch("/api/otp-login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrftoken
      },
      body: JSON.stringify({
        email: email()?.trim(),
        otp: otp()?.trim(),
        forum_login: forumLogin(),
        ...otpData()
      })
    });

    if (response.ok) {
      props.setStatus("Successfully logged in!");
      const data = await response.json();
      setData(data);
      setLoggedIn(true);
    } else {
      setLoggedIn(false);
      try {
        const data = await response.json();
        props.setStatus(`Login failed with error: ${data.message}`);
      } catch {
        props.setStatus(
          `Login failed with error: ${response.statusText} (${response.status})`
        );
      }
    }
  };

  const resetEmail = async e => {
    e.preventDefault();

    setEmail("");
    setCheckSpam(false);
    setOtpData();
    props.setStatus("");
  };

  return (
    <div class="mb-6 grid gap-3">
      <label
        for="otp-email"
        class="mb-2 block text-sm font-medium text-gray-900 dark:text-white"
      >
        Enter Email ID for sending login OTP
      </label>
      <div class="mb-6">
        <input
          class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
          id="otp-email"
          name="email"
          placeholder="Email Address"
          type="email"
          autoComplete="email"
          value={email()}
          disabled={otpData()}
          onInput={e => setEmail(e.currentTarget.value)}
        />
      </div>
      <Show when={otpData()}>
        <div class="mb-6">
          <input
            class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400 dark:focus:border-blue-500 dark:focus:ring-blue-500"
            id="email-otp-number"
            placeholder="Verification Code"
            value={otp()}
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="\d{6}"
            onInput={e => setOtp(e.currentTarget.value)}
          />
        </div>
      </Show>

      <Show
        when={otpData()}
        fallback={
          <button
            id="send-otp-button"
            onClick={sendOTPEmail}
            disabled={loading()}
            class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
          >
            <Show when={loading()} fallback={"Send OTP"}>
              <Spinner />
            </Show>
          </button>
        }
      >
        <button
          id="validate-otp-button"
          onClick={validateOTP}
          class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
        >
          Confirm OTP
        </button>
        <span class="mt-5 text-center text-sm">
          Haven't received your OTP yet?
        </span>
        <button
          disabled={!enableRetry() || loading()}
          class="text-blue-500 transition duration-300 disabled:text-gray-500"
          onClick={sendOTPEmail}
        >
          <Show when={loading()} fallback={"Resend OTP"}>
            <Spinner />
          </Show>
        </button>
        <button class="text-sm text-blue-500 underline" onClick={resetEmail}>
          Wrong Email? Click here to edit
        </button>
      </Show>

      <Show when={checkSpam()}>
        <div
          class="mb-4 rounded-lg bg-yellow-50 p-4 text-sm text-yellow-800 dark:bg-gray-800 dark:text-yellow-300"
          role="alert"
        >
          Please check the Junk folder if you are unable to find the email in
          your Inbox. You should see an email with the subject "Sign in to India
          Ultimate Hub".
        </div>
      </Show>
    </div>
  );
};

const PasskeyLogin = props => {
  const csrftoken = getCookie("csrftoken");
  const [loading, setLoading] = createSignal(false);
  const [store, { setLoggedIn, setData }] = useStore();

  createEffect(() => {
    if (store.loggedIn) {
      const navigate = useNavigate();
      const redirect = new URL(window.location.href).searchParams.get(
        "redirect"
      );
      const isSafe =
        redirect && redirect.startsWith("/") && !redirect.startsWith("//");
      navigate(isSafe ? redirect : "/dashboard", { replace: true });
    }
  });

  let url = new URL(window.location);
  url.pathname = "/passkey";

  const loginWithPasskey = async e => {
    e.preventDefault();
    setLoading(true);

    const loginOptions = await fetch("/api/passkey/login/start", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrftoken
      }
    });

    if (loginOptions.ok) {
      props.setStatus("Successfully initialised passkey method!");
      const data = await loginOptions.json();

      const credential = await get(
        parseRequestOptionsFromJSON(JSON.parse(data["passkey_response"]))
      );

      const loginResponse = await fetch("/api/passkey/login/finish", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify({ passkey_request: JSON.stringify(credential) })
      });

      if (loginResponse.ok) {
        props.setStatus("Successfully logged in!");
        const data = await loginResponse.json();
        setData(data);
        setLoggedIn(true);
      } else {
        setLoggedIn(false);
        try {
          const data = await loginResponse.json();
          props.setStatus(`Login failed with error: ${data.message}`);
        } catch {
          props.setStatus(
            `Login failed with error: ${loginResponse.statusText} (${loginResponse.status})`
          );
        }
      }
    } else {
      try {
        const data = await loginOptions.json();
        props.setStatus(
          `Passkey initializing failed with error: ${data.message}`
        );
      } catch {
        props.setStatus(
          `Passkey initializing failed with error: ${loginOptions.statusText} (${loginOptions.status})`
        );
      }
    }
    setLoading(false);
  };

  return (
    <div class="mb-6 grid gap-3">
      <button
        id="passkey-login-button"
        onClick={loginWithPasskey}
        disabled={loading() || !supported()}
        class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:bg-gray-300 disabled:text-gray-600 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 dark:disabled:bg-gray-700 sm:w-auto"
      >
        <Show
          when={supported()}
          fallback={"Not supported for this device/browser"}
        >
          <Show
            when={loading()}
            fallback={
              <span class="flex items-center justify-center">
                <span>Tap to Login</span>
                <Icon class="ml-2 h-6 w-6" path={fingerPrint} />
              </span>
            }
          >
            <Spinner />
          </Show>
        </Show>
      </button>

      <div
        class="mb-4 rounded-lg bg-yellow-50 p-4 text-sm text-yellow-800 dark:bg-gray-800 dark:text-yellow-300"
        role="alert"
      >
        Only for already registered users who have enabled One-Tap login for
        their device.
        <br />
        <br />
        To Enable: Login with OTP &gt; Dashboard &gt; User Actions &gt; Enable
        One-Tab Login
      </div>
    </div>
  );
};

const Login = () => {
  const [status, setStatus] = createSignal("");
  const [store, _] = useStore();

  const signInFailed = window.localStorage.getItem("emailSignInFailed");
  if (signInFailed) {
    setStatus(signInFailed);
    window.localStorage.removeItem("emailSignInFailed");
  }

  createEffect(() => {
    if (store.loggedIn) {
      const navigate = useNavigate();
      navigate("/dashboard", { replace: true });
    }
  });

  onMount(async () => {
    initFlowbite();
  });

  return (
    <>
      <Breadcrumbs
        icon={home}
        pageList={[{ url: "/", name: "Home" }, { name: "Login" }]}
      />
      <div class="mb-4 border-b border-gray-200 dark:border-gray-700">
        <ul
          class="-mb-px flex flex-wrap text-center text-sm font-medium"
          id="signinTabs"
          data-tabs-toggle="#signinTabContent"
          role="tablist"
        >
          <li class="mr-2" role="presentation">
            <button
              class="inline-block rounded-t-lg border-b-2 p-4"
              id="email-otp-tab"
              data-tabs-target="#email-otp"
              type="button"
              role="tab"
              aria-controls="email-otp"
              aria-selected="false"
            >
              OTP
            </button>
          </li>
          <li class="mr-2" role="presentation">
            <button
              class="inline-block rounded-t-lg border-b-2 p-4"
              id="passkey-tab"
              data-tabs-target="#passkey"
              type="button"
              role="tab"
              aria-controls="passkey"
              aria-selected="false"
            >
              One-Tap Login
            </button>
          </li>
          <li class="mr-2" role="presentation">
            <button
              class="inline-block rounded-t-lg border-b-2 p-4"
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
          class="hidden rounded-lg bg-gray-50 p-4 dark:bg-gray-800"
          id="email-otp"
          role="tabpanel"
          aria-labelledby="email-otp-tab"
        >
          <SendEmailOTP setStatus={setStatus} />
        </div>
        <div
          class="hidden rounded-lg bg-gray-50 p-4 dark:bg-gray-800"
          id="password"
          role="tabpanel"
          aria-labelledby="password-tab"
        >
          <PasswordLogin setStatus={setStatus} />
        </div>
        <div
          class="hidden rounded-lg bg-gray-50 p-4 dark:bg-gray-800"
          id="passkey"
          role="tabpanel"
          aria-labelledby="passkey-tab"
        >
          <PasskeyLogin setStatus={setStatus} />
        </div>
      </div>
      <p>{status()}</p>
    </>
  );
};

export default Login;
