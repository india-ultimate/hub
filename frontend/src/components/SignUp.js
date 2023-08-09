import { getCookie } from "../utils";
import { useStore } from "../store";
import { createEffect, createSignal, Show, For, Switch, Match } from "solid-js";
import {
  createForm,
  getValue,
  // validators
  email,
  pattern,
  required,
  minLength
} from "@modular-forms/solid";
import { useNavigate } from "@solidjs/router";
import TextInput from "./TextInput";

const SignUp = props => {
  const csrftoken = getCookie("csrftoken");

  // UI signals
  const [error, setError] = createSignal("");

  const [store, { setLoggedIn, setData }] = useStore();

  const initialValues = { email: props.emailId };
  const [signupForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const submitFormData = async formData => {
    // Send a post request to the api
    const url = "/api/firebase-login"; // FIXME: fix URL
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken
        },
        body: JSON.stringify({
          ...formData,
          email: props.emailId,
          uid: props.uid,
          token: props.token,
          sign_up: true
        })
      });

      if (response.ok) {
        console.log("Successfully signed up!");
        const data = await response.json();
        setData(data);
        setLoggedIn(true);
        window.localStorage.removeItem("firebaseCreds");
        const navigate = useNavigate();
        navigate("/", { replace: true });
      } else {
        if (response.status == 400) {
          const error = await response.json();
          setError(error.message);
        } else {
          setError(
            `Server returned an error: ${response.statusText} (${response.status})`
          );
        }
      }
    } catch (error) {
      setError(`An error occurred: ${error}`);
    }
  };

  return (
    <div>
      <div
        class="p-4 mb-4 text-sm text-blue-800 rounded-lg bg-blue-50 dark:bg-gray-800 dark:text-blue-400"
        role="alert"
      >
        An account doesn't exist with this email ID. Would you like to Sign up?
      </div>
      <Form
        class="space-y-12 md:space-y-14 lg:space-y-16"
        onSubmit={values => submitFormData(values)}
      >
        <div class="space-y-8">
          <Field name="email" type="string">
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="text"
                label="Email"
                placeholder="player.name@email.com"
                required
                disabled
              />
            )}
          </Field>
          <Field
            name="first_name"
            validate={required("Please enter first name.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="text"
                label="First Name"
                placeholder="Jane"
                required
              />
            )}
          </Field>
          <Field
            name="last_name"
            validate={required("Please enter last name.")}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="text"
                label="Last Name"
                placeholder="Doe"
                required
              />
            )}
          </Field>
          <Field
            name="phone"
            validate={[
              required("Please enter a phone number."),
              pattern(
                /^\+\d+$/,
                "Enter a phone number along with the country code"
              ),
              minLength(8, "Phone number must be at least 8 digits long")
            ]}
          >
            {(field, props) => (
              <TextInput
                {...props}
                value={field.value}
                error={field.error}
                type="text"
                label="Phone number"
                placeholder="+919998887776"
                required
              />
            )}
          </Field>
          <button
            type="submit"
            class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
          >
            Sign Up
          </button>
        </div>
      </Form>
      <Show when={error()}>
        <p class="my-2 text-sm text-red-600 dark:text-red-500">
          <span class="font-medium">Oops!</span> {error()}
        </p>
      </Show>
    </div>
  );
};

export default SignUp;
