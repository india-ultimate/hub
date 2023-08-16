import { useStore } from "../store";
import { useParams } from "@solidjs/router";
import {
  createSignal,
  createEffect,
  onMount,
  Show,
  Switch,
  Match
} from "solid-js";
import { getCookie, fetchUserData, getPlayer } from "../utils";
import { createForm, required } from "@modular-forms/solid";
import StatusStepper from "./StatusStepper";
import TextInput from "./TextInput";
import { Spinner } from "../icons";

const UltimateCentralLogin = () => {
  const [store, { setLoggedIn, setData, setPlayerById }] = useStore();

  const initialValues = { is_vaccinated: true };
  const [_form, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const [player, setPlayer] = createSignal();
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const params = useParams();
  createEffect(() => {
    const player = getPlayer(store.data, Number(params.playerId));
    setPlayer(player);
  });

  onMount(() => {
    if (!store.loggedIn) {
      fetchUserData(setLoggedIn, setData);
    }
  });

  const handleSubmit = async values => {
    const data = { ...values, player_id: player()?.id };
    setError("");
    setStatus(<Spinner />);

    try {
      const response = await fetch("/api/upai/me", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify(data)
      });
      setStatus("");
      if (response.ok) {
        setStatus("Player's Ultimate Central ID saved!");
        const data = await response.json();
        setPlayerById({ data });
      } else {
        const message = await response.json();
        const text = message?.message || JSON.stringify(message);
        setError(`${text}`);
      }
    } catch (error) {
      setError(`An error occurred while submitting vaccination data: ${error}`);
    }
  };

  return (
    <div>
      <h1 class="text-2xl font-bold text-blue-500">
        Ultimate Central profile details for {player()?.full_name}
      </h1>
      <Switch>
        <Match when={!player()}>
          <p>Player information for player {params.playerId} not accessible.</p>
        </Match>
        <Match when={player()?.ultimate_central_id}>
          <p>Ultimate Central Profile ID: {player()?.ultimate_central_id}</p>
          <StatusStepper player={player()} />
        </Match>
        <Match when={!player()?.ultimate_central_id}>
          <details>
            <summary
              class="p-4 text-sm text-blue-800 rounded-lg bg-blue-50 dark:bg-gray-800 dark:text-blue-400"
              role="alert"
            >
              We only use your Ultimate Central (indiaultimate.org) credentials
              to authenticate against the Ultimate Central site, and fetch your
              profile information.
            </summary>
            <p class="p-4 mb-4 text-sm text-blue-800 rounded-lg bg-blue-50 dark:bg-gray-800 dark:text-blue-400">
              Ultimate Central has a beta implementation of OAuth2, and requires
              us to ask for your password, unlike the OAuth2 implementations by
              other providers like Google or Facebook. The API spec provided by
              Ultimate Central is{" "}
              <a
                href="https://docs.google.com/document/d/148SFmTpsdon5xoGpAeNCokrpaPKKOSDtrLNBHOIq5c4/edit#heading=h.px865pu3sfvw"
                class="underline"
              >
                here
              </a>
              , and our code for authentication is{" "}
              <a
                href="https://github.com/india-ultimate/hub/blob/admin-views/server/api.py#L505"
                class="underline"
              >
                here
              </a>
              , in case you are curious.
            </p>
          </details>
          <Form
            class="mt-12 space-y-12 md:space-y-14 lg:space-y-16"
            onSubmit={values => handleSubmit(values)}
          >
            <Field
              name="username"
              validate={required("Please enter the Ultimate Central email.")}
            >
              {(field, props) => (
                <TextInput
                  {...props}
                  value={field.value}
                  error={field.error}
                  type="text"
                  label="Ultimate Central email"
                  placeholder="john.doe@gmail.com"
                  required
                />
              )}
            </Field>
            <Field
              name="password"
              validate={required("Please enter the Ultimate Central password.")}
            >
              {(field, props) => (
                <TextInput
                  {...props}
                  value={field.value}
                  error={field.error}
                  type="password"
                  label="Ultimate Central password"
                  placeholder="**********"
                  required
                />
              )}
            </Field>
            <button
              type="submit"
              class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
            >
              Submit
            </button>
          </Form>
          <Show when={error()}>
            <p class="my-2 text-sm text-red-600 dark:text-red-500">
              <span class="font-medium">Oops!</span> {error()}
            </p>
          </Show>
          <p class="my-2">{status()}</p>
        </Match>
      </Switch>
    </div>
  );
};

export default UltimateCentralLogin;
