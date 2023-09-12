import { getCookie, getAge, fetchUserData, findPlayerById } from "../utils";
import { useStore } from "../store";
import {
  createSignal,
  Show,
  Switch,
  Match,
  onMount,
  createEffect
} from "solid-js";
import {
  genderChoices,
  stateChoices,
  occupationChoices,
  relationChoices,
  minAge,
  majorAge
} from "../constants";
import {
  createForm,
  getValue,
  setValue,
  reset,
  // validators
  email,
  pattern,
  required,
  maxLength,
  minLength,
  custom
} from "@modular-forms/solid";
import { useParams } from "@solidjs/router";
import RegistrationSuccess from "./RegistrationSuccess";
import TextInput from "./TextInput";
import Select from "./Select";
import Checkbox from "./Checkbox";
import Breadcrumbs from "./Breadcrumbs";
import { inboxStack } from "solid-heroicons/solid";

const RegistrationForm = props => {
  const csrftoken = getCookie("csrftoken");

  // UI signals
  const [error, setError] = createSignal("");
  const [player, setPlayer] = createSignal();

  const [
    store,
    {
      setPlayer: setStorePlayer,
      addWard,
      userFetchSuccess,
      userFetchFailure,
      setPlayerById
    }
  ] = useStore();

  const today = new Date();
  const maxDate = new Date(new Date().setFullYear(today.getFullYear() - minAge))
    .toISOString()
    .split("T")[0];

  const validateMinAge = value => {
    const yearEnd = new Date(today.getFullYear(), 11, 31);
    return getAge(value, yearEnd) >= minAge;
  };

  const [ward, setWard] = createSignal(props.ward);

  const validateDateOfBirth = value => {
    const age = getAge(value);
    return ward() ? age < majorAge : age >= majorAge;
  };

  const [selfForm, setSelfForm] = createSignal(!props.ward && !props.others);
  createEffect(() => {
    setSelfForm(!ward() && !props.others);
  });

  const initialValues = {};

  const params = useParams();
  const [editForm, setEditForm] = createSignal(!!params.playerId);

  const [registrationForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  onMount(() => {
    if (!store?.data?.username) {
      fetchUserData(userFetchSuccess, userFetchFailure);
    }
  });

  createEffect(() => {
    if (store.data.id) {
      const playerData = findPlayerById(store.data, Number(params.playerId));
      setWard(props.ward || !!playerData?.guardian);
      reset(registrationForm, {
        initialValues: selfForm()
          ? { ...store.data, ...playerData }
          : playerData
      });
      // NOTE: reset above doesn't seem to set this field by default.
      setValue(
        registrationForm,
        "educational_institution",
        playerData?.educational_institution,
        { shouldTouched: true }
      );
    }
  });

  const submitFormData = async formData => {
    // Send a post request to the api
    const url = props.others
      ? "/api/registration/others"
      : props.ward
      ? "/api/registration/ward"
      : "/api/registration";

    const bodyData = editForm()
      ? { ...formData, player_id: Number(params.playerId) }
      : formData;

    if (ward()) {
      formData.occupation = "Student";
    }

    try {
      const response = await fetch(url, {
        method: editForm() ? "PUT" : "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken
        },
        body: JSON.stringify(bodyData)
      });

      if (response.ok) {
        console.log("Player created successfully");
        const playerData = await response.json();
        setPlayer(playerData);
        if (selfForm()) {
          setStorePlayer(playerData);
        } else if (ward()) {
          editForm() ? setPlayerById(playerData) : addWard(playerData);
        }
        setEditForm(false);
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
      <Breadcrumbs
        icon={inboxStack}
        pageList={[
          { url: "/dashboard", name: "Dashboard" },
          { name: "Registration" }
        ]}
      />
      <Show
        when={!player()}
        fallback={
          <RegistrationSuccess
            player={player()}
            others={props.others}
            ward={ward()}
          />
        }
      >
        <Switch>
          <Match when={props.others}>
            <div
              class="px-8 lg:px-10 p-4 mb-4 text-sm text-yellow-800 rounded-lg bg-yellow-50 dark:bg-gray-800 dark:text-yellow-300"
              role="alert"
            >
              {/* FIXME: Fix the wording and presentation here. */}
              You are filling up the registration form for a different player.
              Please make sure you enter their details correctly! You will be
              unable to edit the details submitted, unless you have access to
              the email address mentioned here.
            </div>
          </Match>
          <Match when={ward()}>
            <div
              class="px-8 lg:px-10 p-4 mb-4 text-sm text-yellow-800 rounded-lg bg-yellow-50 dark:bg-gray-800 dark:text-yellow-300"
              role="alert"
            >
              {/* FIXME: Fix the wording and presentation here. */}
              You are filling up the registration form for a ward. Please be
              sure that you are legally eligible to fill-up this form!
            </div>
          </Match>
        </Switch>
        <Form
          class="space-y-12 md:space-y-14 lg:space-y-16"
          onSubmit={values => submitFormData(values)}
        >
          <div class="space-y-8">
            <Show when={!editForm() && !selfForm()}>
              <Show when={ward()}>
                <Field
                  name="relation"
                  validate={required(
                    "Please select your relation to the ward."
                  )}
                >
                  {(field, props) => (
                    <Select
                      {...props}
                      value={field.value}
                      error={field.error}
                      options={relationChoices}
                      type="text"
                      label="Relation to the ward"
                      placeholder="Parent / Legal Guardian ?"
                      required
                    />
                  )}
                </Field>
              </Show>
              <Field
                name="email"
                type="string"
                validate={[
                  required("Please enter email address of the player."),
                  email("Please enter a valid email address.")
                ]}
              >
                {(field, props) => (
                  <TextInput
                    {...props}
                    value={field.value}
                    error={field.error}
                    type="text"
                    label="Email of the Player"
                    placeholder="player.name@email.com"
                    required
                  />
                )}
              </Field>
              <Show when={ward()}>
                <div
                  class="px-8 lg:px-10 p-4 mb-4 text-sm text-blue-800 rounded-lg bg-blue-50 dark:bg-gray-800 dark:text-blue-400"
                  role="alert"
                >
                  Entering an email address for your ward will allow them to
                  edit their profile information or for a smooth transition when
                  they become an adult. If they don't have their own email
                  address you can use a modified version of your own email
                  address with a <code>+tag</code> suffix. For example, if you
                  address is <code>uncle.ben@gmail.com</code>, you can use{" "}
                  <code>uncle.ben+peter@gmail.com</code> as your wards' email.
                  This <code>+</code> suffix email address is supported by most
                  popular Email services.
                </div>
              </Show>
            </Show>
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
              name="date_of_birth"
              validate={[
                required("Please enter date of birth."),
                custom(
                  validateMinAge,
                  `Players need to be at least ${minAge} years old by the end of the calendar year to register. They will be allowed to participate in UPAI events only if they are ${minAge} years old on the start day of the event.`
                ),
                custom(
                  validateDateOfBirth,
                  editForm()
                    ? "Minors need to have a guardian and adults cannot. Use the correct age!"
                    : ward()
                    ? `Minors need to be under ${majorAge}. Use the adults form, otherwise`
                    : `Use the minors form if the player is less than ${majorAge} years old`
                )
              ]}
            >
              {(field, props) => (
                <TextInput
                  {...props}
                  value={field.value}
                  error={field.error}
                  type="date"
                  max={maxDate}
                  label="Date of Birth"
                  placeholder={maxDate}
                  required
                />
              )}
            </Field>
            <Field name="gender" validate={required("Please select gender.")}>
              {(field, props) => (
                <Select
                  {...props}
                  value={field.value}
                  options={genderChoices}
                  error={field.error}
                  label="Gender"
                  placeholder="You identify as a ...?"
                  required
                />
              )}
            </Field>
            <Show when={getValue(registrationForm, "gender") === "O"}>
              <Field
                name="other_gender"
                validate={[
                  maxLength(30, "Gender cannot be more than 30 chars")
                ]}
              >
                {(field, props) => (
                  <TextInput
                    {...props}
                    value={field.value}
                    error={field.error}
                    type="text"
                    label="Other Gender:"
                    placeholder="Non-Binary"
                  />
                )}
              </Field>
            </Show>
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
            <Show when={!ward()}>
              <Field
                name="occupation"
                validate={required("Please select your occupation.")}
              >
                {(field, props) => (
                  <Select
                    {...props}
                    value={field.value}
                    options={occupationChoices}
                    error={field.error}
                    label="Occupation"
                    placeholder="What do you do?"
                    required
                  />
                )}
              </Field>
            </Show>
            <Show
              when={
                ward() || getValue(registrationForm, "occupation") === "Student"
              }
            >
              <Field
                name="educational_institution"
                validate={required("Please enter Educational institution.")}
              >
                {(field, props) => (
                  <TextInput
                    {...props}
                    value={field.value}
                    error={field.error}
                    type="text"
                    label="Educational Institution"
                    placeholder="Bangalore Public School"
                    required
                  />
                )}
              </Field>
            </Show>
            <Field name="city" validate={required("Please enter City")}>
              {(field, props) => (
                <TextInput
                  {...props}
                  value={field.value}
                  error={field.error}
                  type="text"
                  label="City"
                  placeholder="Bengaluru"
                  required
                />
              )}
            </Field>
            <Field name="not_in_india" type="boolean">
              {(field, props) => (
                <Checkbox
                  {...props}
                  checked={field.value}
                  value={field.value}
                  error={field.error}
                  label={
                    selfForm() ? "I'm not in India" : "Player not in India"
                  }
                />
              )}
            </Field>
            <Show when={!getValue(registrationForm, "not_in_india")}>
              <Field
                name="state_ut"
                validate={required("Please select State or UT")}
              >
                {(field, props) => (
                  <Select
                    {...props}
                    value={field.value}
                    options={stateChoices}
                    error={field.error}
                    label="State / UT"
                    placeholder="Which State/UT are you in?"
                    required
                  />
                )}
              </Field>
            </Show>
            <button
              type="submit"
              class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
            >
              Submit
            </button>
          </div>
        </Form>
        <Show when={error()}>
          <p class="my-2 text-sm text-red-600 dark:text-red-500">
            <span class="font-medium">Oops!</span> {error()}
          </p>
        </Show>
      </Show>
    </div>
  );
};

export default RegistrationForm;
