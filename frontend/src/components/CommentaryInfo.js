import {
  createForm,
  maxRange,
  minRange,
  required,
  setValues
} from "@modular-forms/solid";
import { useNavigate, useParams } from "@solidjs/router";
import { inboxStack } from "solid-heroicons/solid";
import { createEffect, createSignal, Show } from "solid-js";

import { useStore } from "../store";
import { getCookie, getPlayer } from "../utils";
import Breadcrumbs from "./Breadcrumbs";
import TextAreaInput from "./TextAreaInput";
import TextInput from "./TextInput";

const CommentaryInfo = () => {
  const [store, { setPlayerById }] = useStore();

  const initialValues = {};
  const [commentaryInfoForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const [player, setPlayer] = createSignal();
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const params = useParams();
  const navigate = useNavigate();

  createEffect(() => {
    const player = getPlayer(store.data, Number(params.playerId));
    setPlayer(player);

    if (player?.commentary_info) {
      setValues(commentaryInfoForm, player.commentary_info);
    }
  });

  // handleSubmit function to handle form submission
  const handleSubmit = async values => {
    let data = { ...values, player_id: player()?.id };

    setStatus("");
    setError("");

    try {
      const response = await fetch("/api/commentary-info", {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: JSON.stringify(data)
      });

      if (response.ok) {
        setStatus("Saved!");

        const data = await response.json();
        setPlayerById({ ...player(), commentary_info: data });

        navigate("/dashboard", { replace: true });
      } else {
        const message = await response.json();
        const text = message?.message || JSON.stringify(message);
        setStatus(`${text}`);
      }
    } catch (error) {
      setError(`An error occurred while submitting commentary info: ${error}`);
    }
  };

  return (
    <div>
      <Breadcrumbs
        icon={inboxStack}
        pageList={[
          { url: "/dashboard", name: "Dashboard" },
          { name: "Commentary Info" }
        ]}
      />
      <Show
        when={player()}
        fallback={
          <p>
            Accreditation information for player {params.playerId} not
            accessible.
          </p>
        }
      >
        <div>
          <h1 class="text-2xl font-bold text-blue-500">
            Commentary Info for {player()?.full_name}
          </h1>
          <Form
            class="mt-12 space-y-12 md:space-y-14 lg:space-y-16"
            onSubmit={values => handleSubmit(values)}
          >
            <div class="space-y-8">
              <Field
                name="jersey_number"
                validate={[
                  required("Enter your Jersey Number"),
                  minRange(0, "Jersey Number should be greater than 0"),
                  maxRange(99, "Jersey Number should be less than 99")
                ]}
              >
                {(field, props) => (
                  <TextInput
                    {...props}
                    value={field.value}
                    error={field.error}
                    type="number"
                    label="Jersey Number"
                    placeholder="99"
                    required
                  />
                )}
              </Field>
              <Field
                name="ultimate_origin"
                validate={[required("Enter your story!")]}
              >
                {(field, props) => (
                  <TextAreaInput
                    {...props}
                    value={field.value}
                    error={field.error}
                    type="text"
                    label="Which year did you first play ultimate, and in which team/city did you start playing with?"
                    placeholder="2018, BPHC Ultimate, Hyderabad"
                    required
                  />
                )}
              </Field>
              <Field name="ultimate_attraction">
                {(field, props) => (
                  <TextAreaInput
                    {...props}
                    value={field.value}
                    error={field.error}
                    type="text"
                    label="What attracted you to Ultimate and made you join the sport?"
                    placeholder="Mixed Gender & Self Refereed"
                  />
                )}
              </Field>
              <Field name="ultimate_fav_role">
                {(field, props) => (
                  <TextAreaInput
                    {...props}
                    value={field.value}
                    error={field.error}
                    type="text"
                    label="What's your favorite thing to do while playing Ultimate? (eg, type of throw, role, playing position)"
                    placeholder="Cutting & IO Hucks"
                  />
                )}
              </Field>
              <Field name="ultimate_fav_exp">
                {(field, props) => (
                  <TextAreaInput
                    {...props}
                    value={field.value}
                    error={field.error}
                    type="text"
                    label="Share something about your Ultimate tournament experiences (eg. Favorite tournaments, national / state campaigns)"
                    placeholder="Sakkath 2022"
                  />
                )}
              </Field>
              <Field name="interests">
                {(field, props) => (
                  <TextAreaInput
                    {...props}
                    value={field.value}
                    error={field.error}
                    type="text"
                    label="Share something about your profession / career interests"
                    placeholder="Love to code!"
                  />
                )}
              </Field>
              <Field name="fun_fact">
                {(field, props) => (
                  <TextAreaInput
                    {...props}
                    value={field.value}
                    error={field.error}
                    type="text"
                    label="Share a fun fact about you"
                    placeholder="Dropped a pull every tournament xD"
                  />
                )}
              </Field>
              <button
                type="submit"
                class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
              >
                Save
              </button>
            </div>
          </Form>
          <Show when={error()}>
            <p class="my-2 text-sm text-red-600 dark:text-red-500">
              <span class="font-medium">Oops!</span> {error()}
            </p>
          </Show>
          <p>{status()}</p>
        </div>
      </Show>
    </div>
  );
};

export default CommentaryInfo;
