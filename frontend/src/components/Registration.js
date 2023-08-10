import { getCookie } from "../utils";
import { useStore } from "../store";
import { createSignal, Show, Switch, Match } from "solid-js";
import {
  genderChoices,
  stateChoices,
  occupationChoices,
  relationChoices,
  minAge
} from "../constants";
import {
  createForm,
  getValue,
  // validators
  email,
  pattern,
  required,
  maxLength,
  minLength,
  custom
} from "@modular-forms/solid";
import RegistrationSuccess from "./RegistrationSuccess";
import TextInput from "./TextInput";
import Select from "./Select";
import Checkbox from "./Checkbox";

const RegistrationForm = props => {
  const csrftoken = getCookie("csrftoken");

  // UI signals
  const [error, setError] = createSignal("");
  const [player, setPlayer] = createSignal();

  const [store, { setPlayer: setStorePlayer, addWard }] = useStore();

  const today = new Date();
  const maxDate = new Date(new Date().setFullYear(today.getFullYear() - minAge))
    .toISOString()
    .split("T")[0];

  const getAge = value => {
    const dobDate = new Date(value);
    const yearDiff = today.getFullYear() - dobDate.getFullYear();
    const monthDiff = today.getMonth() - dobDate.getMonth();
    const dayDiff = today.getDate() - dobDate.getDate();
    return yearDiff + monthDiff / 12 + dayDiff / 365;
  };

  const validateMinAge = value => {
    return getAge(value) >= 13;
  };

  const validateDateOfBirth = value => {
    const age = getAge(value);
    return props.ward ? age < 18 : age >= 18;
  };

  const initialValues =
    !props.ward && !props.others
      ? {
          first_name: store.data.first_name,
          last_name: store.data.last_name,
          phone: store.data.phone
        }
      : {};
  const [registrationForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const submitFormData = async formData => {
    // Send a post request to the api
    const url = props.others
      ? "/api/registration/others"
      : props.ward
      ? "/api/registration/ward"
      : "/api/registration";
    try {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken
        },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        console.log("Player created successfully");
        const player = await response.json();
        setPlayer(player);
        if (!props.others && !props.ward) {
          setStorePlayer(player);
        } else if (props.ward) {
          addWard(player);
        }
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
      <Show
        when={!player()}
        fallback={
          <RegistrationSuccess
            player={player()}
            others={props.others}
            ward={props.ward}
          />
        }
      >
        <Switch>
          <Match when={props.others}>
            <div
              class="p-4 mb-4 text-sm text-blue-800 rounded-lg bg-blue-50 dark:bg-gray-800 dark:text-blue-400"
              role="alert"
            >
              {/* FIXME: Fix the wording and presentation here. */}
              You are filling up the registration form for a different player.
              Please make sure you enter their details correctly! You will be
              unable to edit the details submitted, unless you have access to
              the email address mentioned here.
            </div>
          </Match>
          <Match when={props.ward}>
            <div
              class="p-4 mb-4 text-sm text-blue-800 rounded-lg bg-blue-50 dark:bg-gray-800 dark:text-blue-400"
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
            <Show when={props.others || props.ward}>
              <Show when={props.ward}>
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
                custom(validateMinAge, "Players need to be 13 years or older"),
                custom(
                  validateDateOfBirth,
                  props.ward
                    ? "Minors need to be under-18. Use the adults form, otherwise"
                    : "Use the minors form if the player is less than 18 years old"
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
                  required("Please enter the name of the other gender"),
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
                    required
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
            <Field
              name="team_name"
              validate={required("Please enter Team name.")}
            >
              {(field, props) => (
                <TextInput
                  {...props}
                  value={field.value}
                  error={field.error}
                  type="text"
                  label="Team Name (Association with UPAI)"
                  placeholder="Thatte Idli Kaal Soup"
                  required
                />
              )}
            </Field>
            <Show when={!props.ward}>
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
                props.ward ||
                getValue(registrationForm, "occupation") === "Student"
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
                  label="Not in India"
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
