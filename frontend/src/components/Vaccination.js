import VaccinationInformation from "./VaccinationInformation";
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
  const [status, setStatus] = createSignal("");

  const [isVaccinated, setIsVaccinated] = createSignal(true);
  const [name, setName] = createSignal("");
  const [otherName, setOtherName] = createSignal("");
  const [certificate, setCertificate] = createSignal(null);
  const [explanation, setExplanation] = createSignal("");

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

   // Other vaccination name
  const handleVaccineNameOther = e => {
    setName(e.target.value);
    if (e.target.value !== "OTHER") {
      setOtherName("");
    }
  };

  const handleFileChange = e => {
    const file = e.target.files[0];
    setCertificate(file);
  };

  // handleSubmit function to handle form submission
  const handleSubmit = async e => {
    e.preventDefault();
    const vaccinationData = {
      is_vaccinated: isVaccinated(),
      name: name(),
      other_name: otherName(),
      explain_not_vaccinated: explanation(),
      player_id: player()?.id
    };

    const formData = new FormData();
    formData.append("vaccination", JSON.stringify(vaccinationData));
    formData.append("certificate", certificate());

    try {
      const response = await fetch("/api/vaccination", {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: formData
      });
      if (response.ok) {
        setStatus("Player vaccination information saved!");
      } else {
        const message = await response.json();
        const text = message?.message || JSON.stringify(message);
        setStatus(`${text}`);
      }
    } catch (error) {
      setError(`An error occurred while submitting vaccination data: ${error}`);
    }
  };

  return (
    <div>
      <h1 class="text-2xl font-bold text-blue-500">Vaccination</h1>
      <h3>Vaccination details for {player()?.full_name}</h3>
      <Show
        when={player() && !player()?.vaccination?.is_vaccinated}
        fallback={
          <table>
            <tbody>
              <VaccinationInformation vaccination={player()?.vaccination} />
            </tbody>
          </table>
        }
      >
        <form onSubmit={handleSubmit}>
          <div class="grid gap-6 mb-6 md:grid-cols-2">
            <div>
              <div class="flex items-center pl-4 border border-gray-200 rounded dark:border-gray-700">
                <input
                  id="is-vaccinated"
                  type="checkbox"
                  checked={isVaccinated()}
                  onChange={() => setIsVaccinated(!isVaccinated())}
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
                    value={name()}
                    onInput={handleVaccineNameOther}
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
              <Show when={name() === "OTHER"}>
                <div>
                  <label
                    for="vaccination-other-name"
                    class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Other Vaccination Name
                  </label>
                  <input
                    id="vaccination-other-name"
                    type="text"
                    class="bg-gray-50 border border-gray-300 text-gray-900 text-sm rounded-lg focus:ring-blue-500 focus:border-blue-500 block w-full p-2.5 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                    value={otherName()}
                    onInput={e => setOtherName(e.target.value)}
                    required
                  />
                </div>
              </Show>
            </div>
            <div>
              <Show when={isVaccinated()}>
                <div>
                  <label
                    for="vaccination-certificate"
                    class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                  >
                    Vaccination Certificate
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
                    id="file_input_help"
                  >
                    PNG, JPG or PDF.
                  </p>
                </div>
              </Show>
            </div>
            <div/>
            <div>
              <Show when={!isVaccinated()}>
                <label
                  for="not-vaccinated-explanation"
                  class="block mb-2 text-sm font-medium text-gray-900 dark:text-white"
                >
                  Explain not being vaccinated
                </label>
                <textarea
                  id="not-vaccinated-explanation"
                  value={explanation()}
                  onInput={e => setExplanation(e.target.value)}
                  rows="4"
                  class="block p-2.5 w-full text-sm text-gray-900 bg-gray-50 rounded-lg border border-gray-300 focus:ring-blue-500 focus:border-blue-500 dark:bg-gray-700 dark:border-gray-600 dark:placeholder-gray-400 dark:text-white dark:focus:ring-blue-500 dark:focus:border-blue-500"
                  placeholder="Write your explanation on why you are not vaccinated..."
                  required
                ></textarea>
              </Show>
            </div>
          </div>
          <Show when={error()}>
            <p class="my-2 text-sm text-red-600 dark:text-red-500">
              <span class="font-medium">Oops!</span> {error()}
            </p>
          </Show>
          <p>{status()}</p>
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
