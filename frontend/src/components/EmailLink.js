import { useStore } from "../store";
import { firebaseConfig, loginWithFirebaseResponse } from "../utils";
import { createSignal, createEffect } from "solid-js";
import { useNavigate } from "@solidjs/router";
import { initializeApp } from "firebase/app";
import {
  getAuth,
  isSignInWithEmailLink,
  signInWithEmailLink
} from "firebase/auth";

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
auth.useDeviceLanguage();

const SignInForm = ({ setStatus }) => {
  // Get the email if available. This should be available if the user completes
  // the flow on the same device where they started it.
  const [email, setEmail] = createSignal(
    window.localStorage.getItem("emailForSignIn") || ""
  );
  // Input disabled if using same device and email is found from localStorage
  const [disableInput, setDisableInput] = createSignal(email() !== "");
  const [loginFail, setLoginFail] = createSignal(false);
  const [_, { setLoggedIn, setData }] = useStore();
  createEffect(() => {
    if (loginFail()) {
      const navigate = useNavigate();
      navigate("/login");
    }
  });

  const signIn = e => {
    e.preventDefault();
    // The client SDK will parse the code from the link for you.
    signInWithEmailLink(auth, email(), window.location.href)
      .then(async result => {
        // Clear email from storage.
        window.localStorage.removeItem("emailForSignIn");
        // You can access the new user via result.user
        // Additional user info profile not available via:
        // result.additionalUserInfo.profile == null
        // You can check if the user is new or existing:
        // result.additionalUserInfo.isNewUser
        console.log(result);
        await loginWithFirebaseResponse(
          result,
          setStatus,
          setLoggedIn,
          setData
        );
      })
      .catch(error => {
        window.localStorage.setItem(
          "emailSignInFailed",
          `Logging in failed with an error: ${error.code}.`
        );
        setLoginFail(true);
      });
  };

  return (
    <form onSubmit={signIn}>
      <div class="grid gap-3 mb-6">
        <label
          for="email-link-input"
          class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
        >
          Confirm the Email ID (for which the login link was created)
        </label>
        <div class="mb-6">
          <input
            class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
            id="email-link-input"
            placeholder="Email Address"
            value={email()}
            onInput={e => setEmail(e.currentTarget.value)}
            disabled={disableInput()}
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

const EmailLink = () => {
  const [status, setStatus] = createSignal("");
  const [invalidLink, setInvalidLink] = createSignal(false);
  const [store, _] = useStore();
  const navigate = useNavigate();

  createEffect(() => {
    if (store.loggedIn) {
      navigate("/", { replace: true });
    }
  });

  createEffect(() => {
    if (invalidLink()) {
      setTimeout(() => navigate("/login", { replace: true }), 3000);
    }
  });

  if (isSignInWithEmailLink(auth, window.location.href)) {
    // Additional state parameters can also be passed via URL.
    // This can be used to continue the user's intended action before
    // triggering the sign-in operation.
  } else {
    setStatus(
      "Not a valid email signin link. Redirecting to the login page..."
    );
    setInvalidLink(true);
  }

  return (
    <>
      <SignInForm setStatus={setStatus} />
      <p>{status()}</p>
    </>
  );
};

export default EmailLink;
