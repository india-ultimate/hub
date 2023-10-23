import {
  getCookie,
  firebaseConfig,
  loginWithFirebaseResponse,
  clearCookie
} from "../utils";
import { useStore } from "../store";
import { Spinner } from "../icons";
import {
  createSignal,
  createEffect,
  onMount,
  Switch,
  Match,
  Show
} from "solid-js";
import { useNavigate } from "@solidjs/router";
import { initializeApp } from "firebase/app";
import {
  getAuth,
  sendSignInLinkToEmail,
  signInWithPopup,
  GoogleAuthProvider
} from "firebase/auth";
import { initFlowbite } from "flowbite";
import SignUp from "./SignUp";
import Breadcrumbs from "./Breadcrumbs";
import { home } from "solid-heroicons/solid";

const PasswordLogin = props => {
  const csrftoken = getCookie("csrftoken");
  const [username, setUsername] = createSignal("");
  const [password, setPassword] = createSignal("");
  const [store, { setLoggedIn, setData }] = useStore();

  createEffect(() => {
    if (store.loggedIn) {
      const navigate = useNavigate();
      navigate("/dashboard", { replace: true });
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
      props.setError(true);
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
      <div
        class="p-4 mb-4 text-sm text-yellow-800 rounded-lg bg-yellow-50 dark:bg-gray-800 dark:text-yellow-300"
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

const GoogleLogin = props => {
  const [store, { setLoggedIn, setData }] = useStore();
  const [creds, setCreds] = createSignal();
  const [showSignUp, setShowSignUp] = createSignal(false);
  const [loading, setLoading] = createSignal(false);

  createEffect(() => {
    if (store.loggedIn) {
      const navigate = useNavigate();
      navigate("/dashboard", { replace: true });
    }
  });

  const onSuccess = async response => {
    props.setStatus("Successfully logged in!");
    setLoading(false);
    setLoggedIn(true);
    setData(await response.json());
  };

  const onFailure = async response => {
    setLoading(false);
    setLoggedIn(false);
    props.setError(true);
    if (response.status === 404) {
      setShowSignUp(true);
      return;
    }
    try {
      const data = await response.json();
      props.setStatus(`Login failed with error: ${data.message}`);
      setShowSignUp(false);
    } catch {
      props.setStatus(
        `Login failed with error: ${response.statusText} (${response.status})`
      );
      setShowSignUp(false);
    }
  };

  const loginWithGoogle = e => {
    e.preventDefault();

    const provider = new GoogleAuthProvider();
    provider.addScope("https://www.googleapis.com/auth/userinfo.email");
    provider.addScope("https://www.googleapis.com/auth/userinfo.profile");
    provider.addScope("openid");

    // Initialize Firebase
    const app = initializeApp(firebaseConfig);
    const auth = getAuth(app);
    auth.useDeviceLanguage();

    signInWithPopup(auth, provider)
      .then(result => {
        setCreds(result);
        setLoading(true);
        loginWithFirebaseResponse(result, onSuccess, onFailure);
      })
      .catch(error => {
        props.setStatus(
          `Failed to login using Google: ${error.code}; ${error.message}`
        );
      });
  };

  return (
    <Switch>
      <Match when={!showSignUp()}>
        <div class="grid gap-3 mb-6">
          <button
            class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
            onClick={loginWithGoogle}
          >
            Login with Google
          </button>
        </div>
        <div
          class="p-4 mb-4 text-sm text-yellow-800 rounded-lg bg-yellow-50 dark:bg-gray-800 dark:text-yellow-300"
          role="alert"
        >
          If you have issues logging in using Google on Firefox, disable
          "Enhanced Tracking Protection" for this site (Use the shield icon (🛡)
          in the address bar) or use the "Email Link" based sign-in.
        </div>
        <Show when={loading()}>
          <Spinner />
        </Show>
      </Match>
      <Match when={showSignUp()}>
        <SignUp
          emailId={creds()?.user?.email}
          uid={creds()?.user?.uid}
          token={creds()?.user?.stsTokenManager?.accessToken}
        />
      </Match>
    </Switch>
  );
};

const SendEmailLink = props => {
  const [email, setEmail] = createSignal("");
  const [checkSpam, setCheckSpam] = createSignal(false);
  let url = new URL(window.location);
  url.pathname = "/email-link";
  const sendFirebaseEmailLink = e => {
    e.preventDefault();
    const actionCodeSettings = {
      // URL you want to redirect back to. The domain (www.example.com) for this
      // URL must be in the authorized domains list in the Firebase Console.
      url: url.toString(),
      // This must be true.
      handleCodeInApp: true
    };

    // Initialize Firebase
    const app = initializeApp(firebaseConfig);
    const auth = getAuth(app);
    auth.useDeviceLanguage();

    sendSignInLinkToEmail(auth, email()?.trim(), actionCodeSettings)
      .then(() => {
        // The link was successfully sent. Inform the user.
        props.setStatus(`Email was successfully sent to ${email()}`);
        // Save the email locally so you don't need to ask the user for it
        // again if they open the link on the same device.
        window.localStorage.setItem("emailForSignIn", email());
        setCheckSpam(true);
      })
      .catch(error => {
        setCheckSpam(false);
        props.setStatus(
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
        <Show when={checkSpam()}>
          <div
            class="p-4 mb-4 text-sm text-yellow-800 rounded-lg bg-yellow-50 dark:bg-gray-800 dark:text-yellow-300"
            role="alert"
          >
            Please check the Junk folder if you are unable to find the email in
            your Inbox. You should see an email with the subject "Sign in to
            India Ultimate Hub".
          </div>
        </Show>
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

  createEffect(() => {
    if (store.loggedIn) {
      const navigate = useNavigate();
      navigate("/dashboard", { replace: true });
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
        email: email()?.trim()
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
      props.setError(true);
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
        ...otpData()
      })
    });

    if (response.ok) {
      props.setStatus("Successfully logged in!");
      const data = await response.json();
      setData(data);
      setLoggedIn(true);
    } else {
      props.setError(true);
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
    <div class="grid gap-3 mb-6">
      <label
        for="email-link-input"
        class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
      >
        Enter Email ID for sending login OTP
      </label>
      <div class="mb-6">
        <input
          class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
          id="email-otp-input"
          placeholder="Email Address"
          value={email()}
          disabled={otpData()}
          onInput={e => setEmail(e.currentTarget.value)}
        />
      </div>
      <Show when={otpData()}>
        <div class="mb-6">
          <input
            class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
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
            class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
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
          class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
        >
          Confirm OTP
        </button>
        <span class="text-center text-sm mt-5">
          Haven't received your OTP yet?
        </span>
        <button
          disabled={!enableRetry() || loading()}
          class="disabled:text-gray-500 text-blue-500 transition duration-300"
          onClick={sendOTPEmail}
        >
          <Show when={loading()} fallback={"Resend OTP"}>
            <Spinner />
          </Show>
        </button>
        <button class="text-sm underline text-blue-500" onClick={resetEmail}>
          Wrong Email? Click here to edit
        </button>
      </Show>

      <Show when={checkSpam()}>
        <div
          class="p-4 mb-4 text-sm text-yellow-800 rounded-lg bg-yellow-50 dark:bg-gray-800 dark:text-yellow-300"
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

const Login = () => {
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal(false);
  const [store, _] = useStore();

  const signInFailed = window.localStorage.getItem("emailSignInFailed");
  if (signInFailed) {
    setStatus(signInFailed);
    setError(true);
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
          class="flex flex-wrap -mb-px text-sm font-medium text-center"
          id="signinTabs"
          data-tabs-toggle="#signinTabContent"
          role="tablist"
        >
          <li class="mr-2" role="presentation">
            <button
              class="inline-block p-4 border-b-2 rounded-t-lg"
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
              class="inline-block p-4 border-b-2 rounded-t-lg"
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
          id="google"
          role="tabpanel"
          aria-labelledby="google-tab"
        >
          <GoogleLogin setStatus={setStatus} setError={setError} />
        </div>
        <div
          class="hidden p-4 rounded-lg bg-gray-50 dark:bg-gray-800"
          id="email-link"
          role="tabpanel"
          aria-labelledby="email-link-tab"
        >
          <SendEmailLink setStatus={setStatus} setError={setError} />
        </div>
        <div
          class="hidden p-4 rounded-lg bg-gray-50 dark:bg-gray-800"
          id="email-otp"
          role="tabpanel"
          aria-labelledby="email-otp-tab"
        >
          <SendEmailOTP setStatus={setStatus} setError={setError} />
        </div>
        <div
          class="hidden p-4 rounded-lg bg-gray-50 dark:bg-gray-800"
          id="password"
          role="tabpanel"
          aria-labelledby="password-tab"
        >
          <PasswordLogin setStatus={setStatus} setError={setError} />
        </div>
      </div>
      <p>{status()}</p>
      <Show when={error()}>
        <button
          type="submit"
          class="mx-2 text-white bg-gray-700 hover:bg-gray-800 focus:ring-4 focus:outline-none focus:ring-gray-300 font-small rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-gray-600 dark:hover:bg-gray-700 dark:focus:ring-gray-800"
          onClick={() => {
            setError(false);
            alert(document.cookie);
            clearCookie("csrftoken");
          }}
        >
          Clear cookies
        </button>{" "}
        if you are having trouble signing in...
      </Show>
    </>
  );
};

export default Login;
