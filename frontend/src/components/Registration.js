import { getCookie } from "../utils.js";
import { createSignal } from "solid-js";
import { genderChoices, stateChoices } from "../constants.js";
import { useNavigate } from "@solidjs/router";

const RegistrationForm = () => {
  const navigate = useNavigate();
  const csrftoken = getCookie("csrftoken");

  // Form signals
  const [firstName, setFirstName] = createSignal("");
  const [lastName, setLastName] = createSignal("");
  const [dateOfBirth, setDateOfBirth] = createSignal("");
  const [phone, setPhone] = createSignal("");
  const [upaiProfile, setUpaiProfile] = createSignal("");
  const [teamName, setTeamName] = createSignal("");
  const [occupation, setOccupation] = createSignal("");
  const [educationInstitution, setEducationInstitution] = createSignal("");
  const [gender, setGender] = createSignal("");
  const [otherGender, setOtherGender] = createSignal("");
  const [notInIndia, setNotInIndia] = createSignal(false);
  const [city, setCity] = createSignal("");
  const [state, setState] = createSignal("");

  //UI signals
  const [error, setError] = createSignal();

  // Gender
  const handleGenderChange = e => {
    setGender(e.target.value);
    if (e.target.value !== "O") {
      setOtherGender("");
    }
  };

  // Not in India checkbox
  const handleNotInIndiaChange = () => {
    setNotInIndia(!notInIndia());
    setState("");
  };

  const handleSubmit = e => {
    e.preventDefault();
    // Prepare the data to be submitted
    const formData = {
      first_name: firstName(),
      last_name: lastName(),
      date_of_birth: dateOfBirth(),
      gender: gender(),
      other_gender: otherGender(),
      city: city(),
      phone: phone(),
      state_ut: state(),
      not_in_india: notInIndia(),
      team_name: teamName(),
      occupation: occupation(),
      educational_institution: educationInstitution(),
      india_ultimate_profile: upaiProfile()
    };
    // Perform form submission logic or API request with formData
    console.log("Form submitted with data:", formData);

    submitFormData(formData);
  };

  const submitFormData = async formData => {
    // Send a post request to the api
    try {
      const response = await fetch("/api/registration", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken
        },
        body: JSON.stringify(formData)
      });

      if (response.ok) {
        // Handle success
        console.log("Player created successfully");
        navigate("/registration-success");
      } else {
        if (response.status == 400) {
          const error = await response.json();
          setError(error.message);
        } else {
          setError(
            `Server returned an error: ${response.statusText} (${
              response.status
            })`
          );
        }
      }
    } catch (error) {
      setError(`An error occurred: ${error}`);
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
        <div class="grid gap-6 mb-6 md:grid-cols-2">
          <div>
            <label
              for="first_name"
              class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
            >
              First name
            </label>
            <input
              type="text"
              id="first_name"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              placeholder="John"
              value={firstName()}
              onInput={e => setFirstName(e.currentTarget.value)}
              required
            />
          </div>
          <div>
            <label
              for="last_name"
              class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
            >
              Last name
            </label>
            <input
              type="text"
              id="last_name"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              placeholder="Doe"
              value={lastName()}
              onInput={e => setLastName(e.currentTarget.value)}
              required
            />
          </div>
          <div>
            <label
              for="dateofbirth"
              class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
            >
              Date of Birth
            </label>
            <div class="relative max-w-sm">
              <input
                type="date"
                id="dateofbirth"
                class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full pl-10 p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                placeholder="Select date"
                value={dateOfBirth()}
                onInput={e => setDateOfBirth(e.currentTarget.value)}
                required
              />
            </div>
          </div>
          <div>
            <label
              for="phone"
              class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
            >
              Phone number
            </label>
            <input
              type="tel"
              id="phone"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              placeholder="9999999999"
              value={phone()}
              onInput={e => setPhone(e.currentTarget.value)}
            />
          </div>
          <div>
            <label
              for="upai-profile"
              class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
            >
              India Ultimate Profile URL
            </label>
            <input
              type="url"
              id="upai-profile"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              placeholder="https://indiaultimate.org/en-in/u/player-name"
              value={upaiProfile()}
              onInput={e => setUpaiProfile(e.currentTarget.value)}
            />
          </div>
          <div>
            <label
              for="team-name"
              class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
            >
              Team Name
            </label>
            <input
              type="text"
              id="team-name"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              placeholder=""
              value={teamName()}
              onInput={e => setTeamName(e.currentTarget.value)}
            />
          </div>
          <div>
            <label
              for="occupation"
              class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
            >
              Occupation
            </label>
            <input
              type="text"
              id="occupation"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              placeholder=""
              value={occupation()}
              onInput={e => setOccupation(e.currentTarget.value)}
            />
          </div>
          <div>
            <label
              for="education-institution"
              class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
            >
              Education Institution
            </label>
            <input
              type="text"
              id="education-institution"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              placeholder=""
              value={educationInstitution()}
              onInput={e => setEducationInstitution(e.currentTarget.value)}
            />
          </div>
          <div>
            <label
              for="gender"
              class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
            >
              Gender
              <select
                id="gender"
                class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                value={gender()}
                onInput={handleGenderChange}
                required
              >
                <option value="">Select Gender</option>
                {genderChoices.map(choice => (
                  <option value={choice.value}>{choice.label}</option>
                ))}
              </select>
            </label>
          </div>
          <div>
            {gender() === "O" && (
              <label
                for="other-gender"
                class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
              >
                Other Gender:
                <input
                  id="other-gender"
                  type="text"
                  class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                  value={otherGender()}
                  onInput={e => setOtherGender(e.target.value)}
                  required
                />
              </label>
            )}
          </div>
          <div>
            <div class="flex items-center pl-4 border border-gray-200 rounded dark:border-gray-700">
              <input
                id="not-in-india"
                type="checkbox"
                checked={notInIndia()}
                onChange={handleNotInIndiaChange}
                value={notInIndia()}
                name="bordered-checkbox"
                class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"
              />
              <label
                for="not-in-india"
                class="w-full py-4 ml-2 text-sm font-medium text-gray-900 dark:text-gray-300"
              >
                I'm not in India
              </label>
            </div>
          </div>
          <div />
          <div>
            <label
              for="city-name"
              class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
            >
              City
            </label>
            <input
              type="text"
              id="city-name"
              class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
              value={city()}
              onInput={e => setCity(e.target.value)}
              placeholder=""
            />
          </div>
          <div>
            {/* State dropdown */}
            {!notInIndia() && (
              <label
                for="state"
                class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
              >
                State
                <select
                  id="state"
                  class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                  value={state()}
                  onInput={e => setState(e.target.value)}
                  required
                >
                  <option value="">Select State/UT</option>
                  {stateChoices.map(choice => (
                    <option value={choice.value}>{choice.label}</option>
                  ))}
                </select>
              </label>
            )}
          </div>
        </div>
        {error() && (
          <p class="my-2 text-sm text-red-600 dark:text-red-500">
            <span class="font-medium">Oops!</span> {error()}
          </p>
        )}
        <button
          type="submit"
          class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
        >
          Submit
        </button>
      </form>
    </div>
  );
};

export default RegistrationForm;
