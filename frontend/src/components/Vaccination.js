import Player from "./Player";
import { useStore } from "../store";
import { useParams } from "@solidjs/router";
import { createSignal, createEffect, onMount, Show } from "solid-js";
import { vaccinationChoices } from "../constants";
import { getCookie, fetchUserData, displayDate } from "../utils";

const getPlayer = (data, id) => {
  if (data.player?.id === id) {
    return data.player;
  } else {
    return data.players?.filter(p => p.id === id)?.[0];
  }
};

const Vaccination = () => {
  const csrftoken = getCookie("csrftoken");

  const [store, { setLoggedIn, setData, setPlayerById }] = useStore();
  const [player, setPlayer] = createSignal();
  const [vaccination, setVaccination] = createSignal();

  const [vaccinationStatus, setVaccinationStatus] = createSignal();

  const [isVaccinated, setIsVaccinated] = createSignal(false);
  const [vaccinationName, setVaccinationName] = createSignal("");
  const [vaccinationCertficate, setVaccinationCertificate] = createSignal(null);
  const [notVaccinatedExplanation, setNotVaccinatedExplanation] = createSignal("");

  const [error, setError] = createSignal("");

  const params = useParams();
  createEffect(() => {
    const player = getPlayer(store.data, Number(params.playerId));
    setPlayer(player);
    setVaccination(player?.vaccination);
  });

  onMount(() => {
    if (!store.loggedIn) {
      fetchUserData(setLoggedIn, setData);
    }
  });

  // Is vaccinated checkbox
  const handleIsVaccinatedChange = e => {
    setIsVaccinated(!isVaccinated());
  };

  const handleFileChange = (e) => {
    const file = e.target.files[0];
    setVaccinationCertificate(file);
  }

  const submitVaccinationData = async vaccinationData => {
    try {
      const vaccinationFormData = new FormData();
      vaccinationFormData.append("player", vaccinationData.player);
      vaccinationFormData.append("is_vaccinated", vaccinationData.is_vaccinated);
      vaccinationFormData.append("vaccination_name", vaccinationData.vaccination_name);
      vaccinationFormData.append("vaccination_certificate", vaccinationData.vaccination_certificate);
      vaccinationFormData.append("explain_not_vaccinated", vaccinationData.explain_not_vaccinated);

      const response = await fetch("/api/vaccination", {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: vaccinationFormData
      });

      if (response.ok) {
        console.log("Vaccination data submitted successfully");
      } else {
        console.error("Error submitting vaccination data");
      }
    } catch (error) {
      console.error("An error occured while submitting vaccination data:", error);
    }
  };

  // handleSubmit function to handle form submission
  const handleSubmit = async e => {
    e.preventDefault();
    const vaccinationData = {
      player: player(),
      is_vaccinated: isVaccinated(),
      vaccination_name: vaccinationName(),
      vaccination_certificate: vaccinationCertficate(),
      explain_not_vaccinated: notVaccinatedExplanation(),
    };
    console.log("Vaccination data:", vaccinationData);

    try {
      await submitVaccinationData(vaccinationData);
      console.log("Vaccination data submitted successfully");
    } catch (error) {
      console.error("An error occurred while submitting vaccination data:", error);
    }
  };

  return (
    <div>
      <h1 class="text-2xl font-bold text-blue-500">Vaccination</h1>
      <h3>Vaccination details for {player()?.full_name}</h3>
      <Show
        when={player()}
      >
        <form onSubmit={handleSubmit}>
          <div class="grid gap-6 mb-6 md:grid-cols-2">
            <div>
              <div class="flex items-center pl-4 border border-gray-200 rounded dark:border-gray-700">
                <input
                  id="is-vaccinated"
                  type="checkbox"
                  checked={isVaccinated()}
                  onChange={handleIsVaccinatedChange}
                  value={isVaccinated()}
                  name="bordered-checkbox"
                  class="w-4 h-4 text-blue-600 bg-gray-100 border-gray-300 rounded focus:ring-blue-500 dark:focus:ring-blue-600 dark:ring-offset-gray-800 focus:ring-2 dark:bg-gray-700 dark:border-gray-600"
                />
                <label
                  for="is-vaccinated"
                  class="w-full py-4 ml-2 text-sm font-medium text-gray-900 dark:text-gray-300"
                >
                  Vaccinated
                </label>
              </div>
            </div>
            <div />
            {/* Vaccination dropdown */}
            <div>
              <Show when={isVaccinated()}>
                <div>
                  <label
                    for="vaccination-name"
                    class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Vaccination Name
                  </label>
                  <select
                    id="vaccination-name"
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    value={vaccinationName()}
                    onInput={e => setVaccinationName(e.target.value)}
                    required
                  >
                    <option value="" disabled>
                      Select Vaccination Name
                    </option>
                    <For each={vaccinationChoices}>
                      {choice => (
                        <option value={choice.value}>{choice.label}</option>
                      )}
                    </For>
                  </select>
                </div>
              </Show>
            </div>
            <div>
              <Show when={isVaccinated()}>
                <div>
                  <label
                    for="vaccination-certificate"
                    class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                    >Vaccination Certificate
                  </label>
                  <input
                    id="vaccination-certificate"
                    class="block w-full text-sm text-gray-900 border border-gray-300 rounded-lg cursor-pointer bg-gray-50 dark:text-gray-400 focus:outline-none dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400"
                    onInput={handleFileChange}
                    type="file"
                    aria-describedby="file_input_help"
                    required
                  />
                  <p
                    class="mt-1 text-sm text-gray-500 dark:text-gray-300"
                    id="file_input_help">PNG, JPG or PDF.</p>
                </div>
              </Show>
            </div>
            <div>
              <Show when={!isVaccinated()}>
                <label
                  for="not-vaccinated-explanation"
                  class="block mb-2 text-sm font-medium text-gray-900 dark:text-white">Explain not being vaccinated</label>
                <textarea
                  id="not-vaccinated-explanation"
                  value={notVaccinatedExplanation()}
                  onInput={e => setNotVaccinatedExplanation(e.target.value)}
                  rows="4"
                  class="block p-2.5 w-full text-sm text-gray-900 bg-gray-50 rounded-lg border border-gray-300 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500" placeholder="Write your explanation on why you are not vaccinated..."
                  required
                >
                </textarea>
              </Show>
            </div>
          </div>
          <Show when={error()}>
            <p class="my-2 text-sm text-red-600 dark:text-red-500">
              <span class="font-medium">Oops!</span> {error()}
            </p>
          </Show>
          <button
            type="submit"
            class="text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
          >
            Submit
          </button>
        </form>

      </Show>
    </div>
  );
};

export default Vaccination;
