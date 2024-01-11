import { createForm, required } from "@modular-forms/solid";
import { useParams } from "@solidjs/router";
import { inboxStack } from "solid-heroicons/solid";
import { createEffect, createSignal, Match, Show, Switch } from "solid-js";

import { Spinner } from "../icons";
import { useStore } from "../store";
import { getCookie, getPlayer } from "../utils";
import Breadcrumbs from "./Breadcrumbs";
import StatusStepper from "./StatusStepper";
import TextInput from "./TextInput";

const UltimateCentralLogin = () => {
  const [store, { setPlayerById }] = useStore();
  const initialValues = {};
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
        const text =
          response.status === 403
            ? `Ultimate Central profile already linked to ${message.full_name} (${message.id}) [${message.email}]`
            : message?.message || JSON.stringify(message);
        setError(`${text}`);
      }
    } catch (error) {
      setError(
        `An error occurred while logging into Ultimate central: ${error}`
      );
    }
  };

  return (
    <div>
      <Breadcrumbs
        icon={inboxStack}
        pageList={[
          { url: "/dashboard", name: "Dashboard" },
          { name: "Ultimate Central" }
        ]}
      />
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
              class="rounded-lg bg-blue-50 p-4 text-sm text-blue-800 dark:bg-gray-800 dark:text-blue-400"
              role="alert"
            >
              We only use your Ultimate Central (indiaultimate.org) credentials
              to authenticate against the Ultimate Central site, and fetch your
              profile information.
            </summary>
            <p class="mb-4 rounded-lg bg-blue-50 p-4 text-sm text-blue-800 dark:bg-gray-800 dark:text-blue-400">
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
              class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 sm:w-auto dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
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
