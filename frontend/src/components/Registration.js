import { getCookie } from "../utils.js";
import { createSignal } from "solid-js";
import { genderChoices, stateChoices } from "../constants.js";
import { useNavigate } from "@solidjs/router";

const RegistrationForm = () => {
  const csrftoken = getCookie("csrftoken");
  const [firstname, setFirstName] = createSignal("");
  const [lastname, setLastName] = createSignal("");
  const [dateofbirth, setDateOfBirth] = createSignal("");
  const [phone, setPhone] = createSignal("");
  const [upaiprofile, setUpaiProfile] = createSignal("");
  const [teamname, setTeamName] = createSignal("");
  const [occupation, setOccupation] = createSignal("");
  const [educationinstitution, setEducationInstitution] = createSignal("");
  const [gender, setGender] = createSignal("");
  const [othergender, setOtherGender] = createSignal("");
  const [notinindia, setNotInIndia] = createSignal(false);
  const [city, setCity] = createSignal("");
  const [state, setState] = createSignal("");
  const navigate = useNavigate();

  // Gender
  const handleGenderChange = (e) => {
    setGender(e.target.value);
    if (e.target.value !== "O") {
      setOtherGender("");
    }
  };

  // Not in India checkbox
  const handleNotInIndiaChange = () => {
    setNotInIndia(!notinindia());
    setState("");
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    // Prepare the data to be submitted
    const formData = {
      first_name: firstname(),
      last_name: lastname(),
      date_of_birth: dateofbirth(),
      gender: gender(),
      other_gender: othergender(),
      city: city(),
      // phone: phone(), // FIXME: Uncomment when multiple ModelSchema is implemented
      state_ut: state(),
      not_in_india: notinindia(),
      team_name: teamname(),
      occupation: occupation(),
      educational_institution: educationinstitution(),
      india_ultimate_profile: upaiprofile(),
    };
    // Perform form submission logic or API request with formData
    console.log("Form submitted with data:", formData);

    submitFormData(formData);
  };

  const submitFormData = async (formData) => {
    formData.not_in_india = formData.not_in_india.toString();
    // Send a post request to the api
    try {
      const response = await fetch("/api/registration", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken },
        body: JSON.stringify(formData),
      });

      if (response.ok) {
        // Handle success
        console.log("Player created successfully");
        // Reroute to success page
        navigate("/registration-success", { replace: true });
      } else {
        if (response.status == 400) {
        // Handle error
          navigate("/registration-player-exists", { replace: true });
        } else {
          console.log("An error occured, response status:", response.status)
          navigate("/registration-error", { replace: true });
        }
      }
    } catch (error) {
      // Handle network or other errors
      console.log("An error occured, message:", error)
      navigate("/registration-error");
    }
  };

  return (
    <div>
      <form onSubmit={handleSubmit}>
          <div class="grid gap-6 mb-6 md:grid-cols-2">
              <div>
                  <label for="first_name" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">First name</label>
                  <input
                    type="text"
                    id="first_name"
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    placeholder="John"
                    value={firstname()}
                    onInput={e => setFirstName(e.currentTarget.value)}
                    required/>
              </div>
              <div>
                  <label for="last_name" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Last name</label>
                  <input
                    type="text"
                    id="last_name"
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    placeholder="Doe"
                    value={lastname()}
                    onInput={e => setLastName(e.currentTarget.value)}
                    required/>
              </div>
              <div>
                <label for="dateofbirth" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Date of Birth</label>
                <div class="relative max-w-sm">
                  <input
                    type="date"
                    id="dateofbirth"
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full pl-10 p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    placeholder="Select date"
                    value={dateofbirth()}
                    onInput={e => setDateOfBirth(e.currentTarget.value)}
                    required/>
                </div>
              </div>
              <div>
                  <label for="phone" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Phone number</label>
                  <input
                    type="tel"
                    id="phone"
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    placeholder="9999999999"
                    value={phone()}
                    onInput={e => setPhone(e.currentTarget.value)}/>
              </div>
              <div>
                  <label for="upai-profile" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">India Ultimate Profile URL</label>
                  <input
                    type="url"
                    id="upai-profile"
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    placeholder="https://indiaultimate.org/en-in/u/player-name"
                    value={upaiprofile()}
                    onInput={e => setUpaiProfile(e.currentTarget.value)}/>
              </div>
              <div>
                  <label for="team-name" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Team Name</label>
                  <input
                    type="text"
                    id="team-name"
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    placeholder=""
                    value={teamname()}
                    onInput={e => setTeamName(e.currentTarget.value)}/>
              </div>
              <div>
                  <label for="occupation" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Occupation</label>
                  <input
                    type="text"
                    id="occupation"
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    placeholder=""
                    value={occupation()}
                    onInput={e => setOccupation(e.currentTarget.value)}/>
              </div>
              <div>
                  <label for="education-institution" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Education Institution</label>
                  <input
                    type="text"
                    id="education-institution"
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    placeholder=""
                    value={educationinstitution()}
                    onInput={e => setEducationInstitution(e.currentTarget.value)}/>
              </div>
              <div>
                <label for="gender" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Gender
                <select
                  id="gender"
                  class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                  value={gender()}
                  onInput={handleGenderChange}
                  required>
                  <option value="">Select Gender</option>
                  {genderChoices.map((choice) =>
                    (<option value={choice.value}>{choice.label}</option>
                    ))}
                </select>
                </label>
              </div>
              <div>
                {gender() === "O" && (
                <label for="other-gender" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">
                  Other Gender:
                  <input
                    id="other-gender"
                    type="text"
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    value={othergender()}
                    onInput={(e) => setOtherGender(e.target.value)}
                    required/>
                </label>
                )}
              </div>
              <div>
                <div class="flex items-center pl-4 border border-gray-200 rounded dark:border-gray-700">
                    <input
                      id="not-in-india"
                      type="checkbox"
                      checked={notinindia()}
                      onChange={handleNotInIndiaChange}
                      value={notinindia()}
                      name="bordered-checkbox"
                      class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"/>
                    <label for="not-in-india" class="w-full py-4 ml-2 text-sm font-medium text-gray-900 dark:text-gray-300">I'm not in India</label>
                </div>
              </div>
              <div>
              </div>
               <div>
                <label for="city-name" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">City</label>
                <input
                  type="text"
                  id="city-name"
                  class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                  value={city()}
                  onInput={(e) => setCity(e.target.value)}
                  placeholder=""/>
              </div>
              <div>
                {/* State dropdown */}
                {notinindia() !== true && (
                  <label for="state" class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">State
                  <select
                    id="state"
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    value={state()}
                    onInput={(e) => setState(e.target.value)}
                    required>
                    <option value="">Select State/UT</option>
                    {stateChoices.map((choice) =>
                      (<option value={choice.value}>{choice.label}</option>
                      ))}
                  </select>
                  </label>
                )}
              </div>
          </div>
          <button type="submit" class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800">Submit</button>
      </form>
    </div>
  );
};

export default RegistrationForm;
