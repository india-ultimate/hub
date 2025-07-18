import { supported } from "@github/webauthn-json/browser-ponyfill";
import { A } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { initFlowbite } from "flowbite";
import { Icon } from "solid-heroicons";
import { camera, star } from "solid-heroicons/solid";
import { createEffect, createSignal, For, Show } from "solid-js";

import { AccordionDownIcon } from "../icons";
import { fetchUserRegistrations, uploadProfilePicture } from "../queries";
import { useStore } from "../store";
import { registerPasskey, showPlayerStatus } from "../utils";
import { getCookie } from "../utils";
import Player from "./Player";
import TransactionList from "./TransactionList";

// Profile Picture Component
const ProfilePicture = props => {
  const [isUploading, setIsUploading] = createSignal(false);
  const [uploadError, setUploadError] = createSignal("");
  const [uploadSuccess, setUploadSuccess] = createSignal("");

  const handleFileChange = async event => {
    const file = event.target.files[0];
    if (!file) return;

    // Validate file type
    const allowedTypes = [
      "image/jpeg",
      "image/png",
      "image/gif",
      "image/webp",
      "image/bmp",
      "image/tiff"
    ];
    if (!allowedTypes.includes(file.type)) {
      setUploadError(
        "Only image files are allowed (JPEG, PNG, GIF, WebP, BMP, TIFF)"
      );
      return;
    }

    // Validate file size (10MB max)
    if (file.size > 10 * 1024 * 1024) {
      setUploadError("File size must be less than 10MB");
      return;
    }

    setIsUploading(true);
    setUploadError("");
    setUploadSuccess("");

    try {
      const data = await uploadProfilePicture(file);
      setUploadSuccess("Profile picture updated successfully!");
      // Update the store with new player data
      if (props.onUpdate) {
        props.onUpdate(data);
      }
      // Clear success message after 3 seconds
      setTimeout(() => setUploadSuccess(""), 3000);
    } catch (error) {
      setUploadError(error.message || "Failed to upload profile picture");
      // Clear error message after 5 seconds
      setTimeout(() => setUploadError(""), 5000);
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div class="mb-6 flex items-center space-x-4">
      <div class="relative">
        <Show
          when={props.player?.profile_pic_url}
          fallback={
            <div class="flex h-20 w-20 items-center justify-center rounded-full bg-gray-200">
              <span class="text-2xl text-gray-500">
                {props.player?.full_name?.charAt(0)?.toUpperCase() || "?"}
              </span>
            </div>
          }
        >
          <img
            src={props.player.profile_pic_url}
            alt="Profile"
            class="h-20 w-20 rounded-full border-2 border-gray-200 object-cover"
          />
        </Show>

        <label class="absolute -bottom-1 -right-1 cursor-pointer rounded-full bg-blue-600 p-2 text-white hover:bg-blue-700">
          <Icon path={camera} class="h-4 w-4" />
          <input
            type="file"
            accept="image/*"
            onChange={handleFileChange}
            class="hidden"
            disabled={isUploading()}
          />
        </label>
      </div>

      <div class="flex-1">
        <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
          {props.player?.full_name}
        </h3>
        <p class="text-sm text-gray-500 dark:text-gray-400">
          {props.player?.user?.email}
        </p>

        <Show when={isUploading()}>
          <p class="text-sm text-blue-600 dark:text-blue-400">Uploading...</p>
        </Show>

        <Show when={uploadError()}>
          <p class="text-sm text-red-600 dark:text-red-400">{uploadError()}</p>
        </Show>

        <Show when={uploadSuccess()}>
          <p class="text-sm text-green-600 dark:text-green-400">
            {uploadSuccess()}
          </p>
        </Show>
      </div>
    </div>
  );
};

const Actions = props => {
  const onCreatePasskeyClick = async () => {
    props.setSuccess(false);
    props.setError(false);

    const response = await registerPasskey();

    if (response.success) {
      props.setSuccess(response.success);
    }
    if (response.error) {
      props.setError(response.error);
    }

    initFlowbite();
  };

  return (
    <div class="w-90 rounded-lg border border-gray-200 bg-white text-sm font-medium text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white">
      <Show when={!props.player}>
        <A
          href="/registration/me"
          class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
        >
          Register yourself as a player
        </A>
      </Show>
      <A
        href="/registration/ward"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Fill the membership form for a minor player as Guardian
      </A>
      <A
        href="/registration/others"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Fill the membership form for another player
      </A>
      <A
        href="/help#import-players-from-a-spreadsheet"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Import players information from a Spreadsheet
      </A>
      <A
        href={`/membership/${props.player?.id}`}
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Pay the membership fee for yourself or a group
      </A>
      <A
        href="/validate-rosters"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Validate your Team Roster for an event
      </A>
      <A
        href="/tickets"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Support Tickets
      </A>
      <button
        disabled={!supported()}
        onClick={onCreatePasskeyClick}
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 text-left hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 disabled:text-gray-600 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500 disabled:dark:text-gray-400"
      >
        <Show
          when={supported()}
          fallback={"One-Tab Login is not available for this browser or device"}
        >
          Enable One-Tap Login for this device
        </Show>
      </button>
    </div>
  );
};

const StaffActions = () => {
  return (
    <div class="w-90 rounded-lg border border-gray-200 bg-white text-sm font-medium text-gray-900 dark:border-gray-600 dark:bg-gray-700 dark:text-white">
      <A
        href="/players"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        View Registered players
      </A>
      <A
        href="/validate-rosters"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Validate Event Roster
      </A>
      <A
        href="/validate-transactions"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Validate Transactions
      </A>
      <A
        href="/check-memberships"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Check Membership Status
      </A>
      <A
        href="/tournament-manager"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        Create / Manage Tournament
      </A>
      <A
        href="/tickets"
        class="block w-full cursor-pointer border-b border-gray-200 px-4 py-2 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
      >
        View All Support Tickets
      </A>
    </div>
  );
};

const Dashboard = () => {
  const [store, { userFetchFailure, setPlayerById }] = useStore();
  const [success, setSuccess] = createSignal();
  const [error, setError] = createSignal();
  const [performancePoints, setPerformancePoints] = createSignal(0);

  const userRegistrationsQuery = createQuery(
    () => ["me-registrations"],
    fetchUserRegistrations
  );

  createEffect(() => {
    const validRegs = userRegistrationsQuery.data?.filter(reg => reg.points);
    if (!validRegs) return;

    const length = validRegs.length;
    if (length === 0) return;

    const sum = validRegs.reduce((sum, reg) => sum + reg.points, 0);
    const avg = sum / length;
    setPerformancePoints(parseFloat(avg.toFixed(1)));
  });

  createEffect(() => {
    console.log(success(), error());
  });

  const logout = async () => {
    const response = await fetch("/api/logout", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": getCookie("csrftoken")
      },
      credentials: "same-origin"
    });
    if (response.status == 200) {
      userFetchFailure();
      // NOTE: we reload the page to ensure the store is empty. Doesn't seem to
      // happen with just setData, for some reason?!
      window.location = "/";
    }
  };

  return (
    <div>
      <h1 class="mb-4 text-2xl font-bold text-blue-600 md:text-4xl">
        Welcome <span>{store?.data?.full_name || store?.data?.username}</span>!
      </h1>
      <div
        id="accordion-flush"
        data-accordion="collapse"
        data-active-classes="bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
        data-inactive-classes="text-gray-500 dark:text-gray-400"
      >
        <Show when={store.data.player}>
          <h2 id="accordion-heading-player">
            <button
              type="button"
              class="flex w-full items-center justify-between border-b border-gray-200 py-5 text-left font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400"
              data-accordion-target="#accordion-body-player"
              aria-expanded="true"
              aria-controls="accordion-body-player"
            >
              <span>Player Information: {store.data.player.full_name} </span>
              <span class="flex">
                {showPlayerStatus(store.data.player)}

                <AccordionDownIcon />
              </span>
            </button>
          </h2>
          <div
            id="accordion-body-player"
            class="hidden"
            aria-labelledby="accordion-heading-player"
          >
            <div class="border-b border-gray-200 py-5 dark:border-gray-700">
              <ProfilePicture
                player={store.data.player}
                onUpdate={updatedPlayer => {
                  setPlayerById(updatedPlayer);
                }}
              />
              <Player player={store.data.player} />
            </div>
          </div>
        </Show>
        <Show when={store.data.wards}>
          <For each={store.data.wards}>
            {ward => (
              <>
                <h2 id={`accordion-heading-ward-${ward.id}`}>
                  <button
                    type="button"
                    class="flex w-full items-center justify-between border-b border-gray-200 py-5 text-left font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400"
                    data-accordion-target={`#accordion-body-ward-${ward.id}`}
                    aria-expanded={store?.data?.player ? "false" : "true"}
                    aria-controls={`accordion-body-ward-${ward.id}`}
                  >
                    <span>Player Information: {ward.full_name} </span>
                    <span class="flex">
                      {showPlayerStatus(store.data.player)}
                      <AccordionDownIcon />
                    </span>
                  </button>
                </h2>
                <div
                  id={`accordion-body-ward-${ward.id}`}
                  class="hidden"
                  aria-labelledby={`accordion-heading-ward-${ward.id}`}
                >
                  <div class="border-b border-gray-200 py-5 dark:border-gray-700">
                    <Player player={ward} />
                  </div>
                </div>
              </>
            )}
          </For>
        </Show>
        <h2 id="accordion-heading-actions">
          <button
            type="button"
            class="flex w-full items-center justify-between border-b border-gray-200 py-5 text-left font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400"
            data-accordion-target="#accordion-body-actions"
            aria-expanded={
              store?.data?.player || store?.data?.wards?.length > 0
                ? "false"
                : "true"
            }
            aria-controls="accordion-body-actions"
          >
            <span>User Actions</span>
            <AccordionDownIcon />
          </button>
        </h2>
        <div
          id="accordion-body-actions"
          class="hidden"
          aria-labelledby="accordion-heading-actions"
        >
          <div class="border-b border-gray-200 py-5 dark:border-gray-700">
            <Actions
              player={store.data.player}
              setSuccess={setSuccess}
              setError={setError}
            />
          </div>
        </div>
        <h2 id="accordion-heading-registrations">
          <button
            type="button"
            class="flex w-full items-center justify-between border-b border-gray-200 py-5 text-left font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400"
            data-accordion-target="#accordion-body-registrations"
            aria-expanded="false"
            aria-controls="accordion-body-registrations"
          >
            <span>Performance Points</span>
            <span class="flex">
              <p class="mr-2 inline-flex items-center rounded bg-blue-600 p-1.5 text-sm font-semibold text-white dark:bg-blue-200 dark:text-blue-800">
                <Icon path={star} class="mr-1 h-4" />
                {performancePoints() || 0}
              </p>
              <AccordionDownIcon />
            </span>
          </button>
        </h2>
        <div
          id="accordion-body-registrations"
          class="hidden"
          aria-labelledby="accordion-heading-registrations"
        >
          <div class="border-b border-gray-200 py-5 dark:border-gray-700">
            <p class="mb-4 text-sm italic">
              The list of tournaments you've participated in and the points you
              earned based on your team's final rankings
            </p>

            <ul class="max-w-md divide-y divide-gray-200 dark:divide-gray-700">
              <For
                each={userRegistrationsQuery.data?.filter(reg => reg.points)}
                fallback={
                  <li class="py-3 sm:py-4">
                    <div class="w-full text-sm font-semibold">
                      No tournaments to show!
                    </div>
                  </li>
                }
              >
                {reg => (
                  <li class="py-3 sm:py-4">
                    <div class="flex items-center space-x-4 rtl:space-x-reverse">
                      <div class="flex-shrink-0">
                        <img
                          class="h-10 w-10 rounded-full"
                          src={reg.team.image ?? reg.team.image_url}
                          alt="logo"
                        />
                      </div>
                      <div class="min-w-0 flex-1">
                        <p class="truncate text-sm font-medium text-gray-900 dark:text-white">
                          {reg.team.name}
                        </p>
                        <p class="truncate text-sm text-gray-500 dark:text-gray-400">
                          {reg.event_name}
                        </p>
                        <Show when={reg.series_name}>
                          <p class="truncate text-xs text-gray-500 dark:text-gray-400">
                            {reg.series_name}
                          </p>
                        </Show>
                      </div>
                      <div class="inline-flex items-center rounded bg-blue-100 p-1.5 text-sm font-semibold text-blue-800">
                        <Icon path={star} class="mr-1 h-4" /> {reg.points}
                      </div>
                    </div>
                  </li>
                )}
              </For>
            </ul>

            <div
              class="my-2 rounded-lg bg-blue-50 p-4 text-sm text-blue-600"
              role="alert"
            >
              <details>
                <summary>How are the points calculated?</summary>
                <div class="mt-4 space-y-2">
                  <ol class="mt-2 list-decimal space-y-1 pl-5 text-sm">
                    <li>Points are calculated based on the team's finish.</li>
                    <li>
                      Base Points is 20. Which means the last finishing team
                      will get 20 points.
                    </li>
                    <li>
                      Every other team from the bottom will get the additional
                      points(upto 80 for max points of 100) in a linear format
                      based on the number of teams.
                    </li>
                    <li>
                      Example: With a tournament of 5 teams, the points for last
                      to first team would be 20, 40, 60, 80 and 100
                      respectively.
                    </li>
                  </ol>
                </div>
              </details>
            </div>
          </div>
        </div>
        <Show when={store.data.is_staff}>
          <h2 id="accordion-heading-staff">
            <button
              type="button"
              class="flex w-full items-center justify-between border-b border-gray-200 py-5 text-left font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400"
              data-accordion-target="#accordion-body-staff"
              aria-expanded="false"
              aria-controls="accordion-body-staff"
            >
              <span>Staff Actions</span>
              <AccordionDownIcon />
            </button>
          </h2>
          <div
            id="accordion-body-staff"
            class="hidden"
            aria-labelledby="accordion-heading-staff"
          >
            <div class="border-b border-gray-200 py-5 dark:border-gray-700">
              <StaffActions player={store.data.player} />
            </div>
          </div>
        </Show>
        <h2 id="accordion-heading-transactions">
          <button
            type="button"
            class="flex w-full items-center justify-between border-b border-gray-200 py-5 text-left font-medium text-gray-500 dark:border-gray-700 dark:text-gray-400"
            data-accordion-target="#accordion-body-transactions"
            aria-expanded="false"
            aria-controls="accordion-body-transactions"
          >
            <span>Transactions</span>
            <AccordionDownIcon />
          </button>
        </h2>
        <div
          id="accordion-body-transactions"
          class="hidden"
          aria-labelledby="accordion-heading-transactions"
        >
          <div class="border-b border-gray-200 py-5 dark:border-gray-700">
            <TransactionList />
          </div>
        </div>
      </div>

      <Show when={success()}>
        <div
          id="toast-success"
          class="fixed left-1/2 top-24 mb-4 flex w-full max-w-xs -translate-x-1/2 items-center rounded-lg bg-white p-4 text-gray-500 shadow dark:bg-gray-800 dark:text-gray-400"
          role="alert"
        >
          <div class="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-green-100 text-green-500 dark:bg-green-800 dark:text-green-200">
            <svg
              class="h-5 w-5"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5Zm3.707 8.207-4 4a1 1 0 0 1-1.414 0l-2-2a1 1 0 0 1 1.414-1.414L9 10.586l3.293-3.293a1 1 0 0 1 1.414 1.414Z" />
            </svg>
            <span class="sr-only">Check icon</span>
          </div>
          <div class="ms-3 text-sm font-normal">{success()}</div>
          <button
            type="button"
            class="-mx-1.5 -my-1.5 ms-auto inline-flex h-8 w-8 items-center justify-center rounded-lg bg-white p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-900 focus:ring-2 focus:ring-gray-300 dark:bg-gray-800 dark:text-gray-500 dark:hover:bg-gray-700 dark:hover:text-white"
            data-dismiss-target="#toast-success"
            aria-label="Close"
          >
            <span class="sr-only">Close</span>
            <svg
              class="h-3 w-3"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 14 14"
            >
              <path
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="m1 1 6 6m0 0 6 6M7 7l6-6M7 7l-6 6"
              />
            </svg>
          </button>
        </div>
      </Show>

      <Show when={error()}>
        <div
          id="toast-danger"
          class="fixed left-1/2 top-24 mb-4 flex w-full max-w-xs -translate-x-1/2 items-center rounded-lg bg-white p-4 text-gray-500 shadow dark:bg-gray-800 dark:text-gray-400"
          role="alert"
        >
          <div class="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-red-100 text-red-500 dark:bg-red-800 dark:text-red-200">
            <svg
              class="h-5 w-5"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path d="M10 .5a9.5 9.5 0 1 0 9.5 9.5A9.51 9.51 0 0 0 10 .5Zm3.707 11.793a1 1 0 1 1-1.414 1.414L10 11.414l-2.293 2.293a1 1 0 0 1-1.414-1.414L8.586 10 6.293 7.707a1 1 0 0 1 1.414-1.414L10 8.586l2.293-2.293a1 1 0 0 1 1.414 1.414L11.414 10l2.293 2.293Z" />
            </svg>
            <span class="sr-only">Error icon</span>
          </div>
          <div class="ms-3 text-sm font-normal">{error()}</div>
          <button
            type="button"
            class="-mx-1.5 -my-1.5 ms-auto inline-flex h-8 w-8 items-center justify-center rounded-lg bg-white p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-900 focus:ring-2 focus:ring-gray-300 dark:bg-gray-800 dark:text-gray-500 dark:hover:bg-gray-700 dark:hover:text-white"
            data-dismiss-target="#toast-danger"
            aria-label="Close"
          >
            <span class="sr-only">Close</span>
            <svg
              class="h-3 w-3"
              aria-hidden="true"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 14 14"
            >
              <path
                stroke="currentColor"
                stroke-linecap="round"
                stroke-linejoin="round"
                stroke-width="2"
                d="m1 1 6 6m0 0 6 6M7 7l6-6M7 7l-6 6"
              />
            </svg>
          </button>
        </div>
      </Show>

      <button
        onClick={logout}
        type="button"
        class="me-2 mt-4 rounded-lg border border-red-700 px-5 py-2.5 text-center text-sm font-medium text-red-700 hover:bg-red-800 hover:text-white focus:outline-none  dark:border-red-500 dark:text-red-500 dark:hover:bg-red-600 dark:hover:text-white "
      >
        Logout
      </button>
    </div>
  );
};

export default Dashboard;
