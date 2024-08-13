import { useParams } from "@solidjs/router";
import { A } from "@solidjs/router";
import { inboxStack } from "solid-heroicons/solid";
import { createEffect, createSignal, Match, Show, Switch } from "solid-js";

import { useStore } from "../store";
import { displayDate, getCookie, getPlayer } from "../utils";
import Breadcrumbs from "./Breadcrumbs";

const Legal = props => (
  <div class="my-10">
    <label class="flex select-none space-x-4 font-medium">
      <input
        id="legal"
        class="mt-1 h-4 w-4 cursor-pointer lg:mt-1 lg:h-5 lg:w-5"
        type="checkbox"
        onChange={e => props.onChange(e.target.checked)}
        checked={props.signed}
        disabled={props.signed}
      />
      <span>
        I understand that this is a legally binding document and that I have
        read and understood its contents fully.
      </span>
    </label>
  </div>
);

const PartA = props => (
  <div class="my-10">
    <h3 class="text-xl font-bold text-blue-500">Part A</h3>
    <Switch>
      <Match when={props.minor}>
        <p>
          In consideration of the participation of my son/daughter/ward in the
          events conducted by Ultimate Players Association of India and Flying
          Disc Sports Federation (India), collectively known as India Ultimate
          hereinafter, from {displayDate(props.startDate)} to{" "}
          {displayDate(props.endDate)}. I, the undersigned, understand,
          acknowledge and agree to the following:
        </p>
        <ol class="my-4 mt-2 list-inside list-decimal space-y-1 pl-5">
          <li>
            I am aware that my son/daughter/ward's participation involves
            certain risks and hazards, including, but not limited to, physical
            injury, property damage, and other potential dangers.
          </li>
          <li>
            I am aware of the existence of the risk of my son/daughter/ward's
            physical appearance to the venues and their participation in the
            activities of the Organization that may cause injury or illness such
            as, but not limited to Influenza, MRSA, or COVID-19 that may lead to
            paralysis or death.
          </li>
          <li>
            I am fully and personally responsible for my son/daughter/ward's
            safety and actions while and during their participation and I
            recognize that my son/daughter/ward may be at risk of contracting
            any communicable disease including but not limited to COVID-19.
          </li>
          <li>
            If my son/daughter/ward has experienced symptoms of fever, fatigue,
            difficulty in breathing, or dry cough or exhibiting any other
            symptoms relating to COVID-19 or any communicable disease within the
            last 14 days prior to an event, they will not participate in or
            appear at that event.
          </li>
          <li>
            If my son/daughter/ward, or any member(s) of my household, have been
            diagnosed to be infected of COVID-19 virus or any communicable
            disease within the last 30 days prior to an event, my
            son/daughter/ward will not participate in or appear at that event.
          </li>
          <li>
            I am aware that India Ultimate recommends two shots of Vaccination
            against the COVID-19 virus.
          </li>
        </ol>
      </Match>
      {/* Adults */}
      <Match when={!props.minor}>
        <p>
          In consideration of my participation in the events conducted by
          Ultimate Players Association of India and Flying Disc Sports
          Federation (India), collectively known as India Ultimate hereinafter,
          from {displayDate(props.startDate)} to {displayDate(props.endDate)}
          I, the undersigned, understand, acknowledge and agree to the
          following:
        </p>
        <ol class="my-4 mt-2 list-inside list-decimal space-y-1 pl-5">
          <li>
            I am aware that my participation involves certain risks and hazards,
            including, but not limited to, physical injury, property damage, and
            other potential dangers.
          </li>
          <li>
            I am aware of the existence of the risk of my physical appearance to
            the venues and my participation in the activities of the
            Organization that may cause injury or illness such as, but not
            limited to Influenza, MRSA, or COVID-19 that may lead to paralysis
            or death.
          </li>
          <li>
            I am fully and personally responsible for my own safety and actions
            while and during my participation and I recognize that I may be at
            risk of contracting any communicable disease including but not
            limited to COVID-19.
          </li>
          <li>
            If I have experienced symptoms of fever, fatigue, difficulty in
            breathing, or dry cough or exhibiting any other symptoms relating to
            COVID-19 or any communicable disease within the last 14 days prior
            to an event, I will not participate in or appear at that event.
          </li>
          <li>
            If I, or any member(s) of my household, have been diagnosed to be
            infected of COVID-19 virus or any communicable disease within the
            last 30 days prior to an event, I will not participate in or appear
            at that event.
          </li>
          <li>
            I am aware that India Ultimate recommends two shots of Vaccination
            against the COVID-19 virus.
          </li>
        </ol>
      </Match>
    </Switch>
  </div>
);

const PartB = props => (
  <div class="my-10">
    <h3 class="text-xl font-bold text-blue-500">Part B</h3>
    <Switch>
      <Match when={props.minor}>
        <p>
          Following the pronouncements above I hereby declare the following on
          behalf of my son/daughter/ward
        </p>
        <ol class="my-4 mt-2 list-inside list-decimal space-y-1 pl-5">
          <li>
            In consideration for my son/daughter/ward being permitted to
            participate in the Event(s), I hereby agree to release, discharge,
            and hold harmless the Organizer, its officers, directors, employees,
            agents, volunteers, sponsors, and all other persons or entities
            acting in any capacity on behalf of the Organizer (collectively, the
            "Released Parties"), from any and all claims, liabilities, demands,
            actions, rights of action, costs, and expenses (including attorney's
            fees) that may arise out of or be related to any loss, damage,
            injury, or harm, whether to my son/daughter/ward or property, that
            may occur as a result of their participation in the Event(s) while
            in, on, or around the premises or while using the facilities that
            may lead to unintentional exposure or harm due to COVID-19 or any
            communicable disease as well.
          </li>
          <li>
            I agree to indemnify, defend, and hold harmless the Organization
            from and against any and all costs, expenses, damages, lawsuits,
            and/or liabilities or claims arising whether directly or indirectly
            from or related to any and all claims made by or against any of the
            released party due to injury, loss, or death from my
            son/daughter/ward participating in the event(s).
          </li>
          <li>
            By clicking “I agree” below I acknowledge that I have read the
            foregoing Liability Release Waiver concerning my son/daughter/ward
            and understand its contents;  That I am the Parent or Legal Guardian
            and that I am fully competent to give my consent on behalf of my
            son/daughter/ward; That I have been sufficiently informed of the
            risks involved and give my voluntary consent in signing it as my own
            free act and deed on behalf of my son/daughter/ward; that I give my
            voluntary consent in signing this Liability Release Waiver as my own
            free act and deed with full intention to be bound by the same on
            behalf of my son/daughter/ward, and free from any inducement or
            representation.
          </li>
        </ol>
        <p class="mb-4">
          I hereby affirm that I am of legal age and competent to sign this
          Liability Waiver and Release Form. I am signing on behalf of a minor
          and I certify that I am the parent or legal guardian of the minor and
          have the authority to sign this form on their behalf.
        </p>
        <label class="flex select-none space-x-4 font-medium">
          <input
            id="waiver"
            class="mt-1 h-4 w-4 cursor-pointer lg:mt-1 lg:h-5 lg:w-5"
            type="checkbox"
            onChange={e => props.onChange(e.target.checked)}
            checked={props.signed}
            disabled={props.signed}
          />
          <span>
            I give my voluntary consent in signing this Liability Release Waiver
            on behalf of my son/daughter/ward
          </span>
        </label>
      </Match>
      <Match when={!props.minor}>
        <p>
          Following the pronouncements above I hereby declare the following:
        </p>
        <ol class="my-4 mt-2 list-inside list-decimal space-y-1 pl-5">
          <li>
            In consideration for being permitted to participate in the Event(s),
            I hereby agree to release, discharge, and hold harmless the
            Organizer, its officers, directors, employees, agents, volunteers,
            sponsors, and all other persons or entities acting in any capacity
            on behalf of the Organizer (collectively, the "Released Parties"),
            from any and all claims, liabilities, demands, actions, rights of
            action, costs, and expenses (including attorney's fees) that may
            arise out of or be related to any loss, damage, injury, or harm,
            whether to my person or property, that may occur as a result of my
            participation in the Event(s) while in, on, or around the premises
            or while using the facilities that may lead to unintentional
            exposure or harm due to COVID-19 or any communicable disease as
            well.
          </li>
          <li>
            I agree to indemnify, defend, and hold harmless the Organization
            from and against any and all costs, expenses, damages, lawsuits,
            and/or liabilities or claims arising whether directly or indirectly
            from or related to any and all claims made by or against any of the
            released party due to injury, loss, or death from participating in
            the event.
          </li>
          <li>
            By clicking “I agree” below I acknowledge that I have read the
            foregoing Liability Release Waiver and understand its contents; 
            That I have been sufficiently informed of the risks involved and
            give my voluntary consent in signing it as my own free act and deed;
            that I give my voluntary consent in signing this Liability Release
            Waiver as my own free act and deed with full intention to be bound
            by the same, and free from any inducement or representation.
          </li>
        </ol>
        <p class="mb-4">
          I hereby affirm that I am of legal age and competent to sign this
          Liability Waiver and Release Form.
        </p>
        <label class="flex select-none space-x-4 font-medium">
          <input
            id="waiver"
            class="mt-1 h-4 w-4 cursor-pointer lg:mt-1 lg:h-5 lg:w-5"
            type="checkbox"
            onChange={e => props.onChange(e.target.checked)}
            checked={props.signed}
            disabled={props.signed}
          />
          <span>
            I give my voluntary consent in signing this Liability Release
            Waiver.
          </span>
        </label>
      </Match>
    </Switch>
  </div>
);

const MediaConsent = props => (
  <div class="my-10">
    <h3 class="text-xl font-bold text-blue-500">Media Consent</h3>
    <Switch>
      <Match when={props.minor}>
        <p class="py-4">
          I, the parent/legal guardian of {props.player.full_name}, hereby give
          consent to India Ultimate, to take photographs, videos and live
          stream/broadcast of my son/daughter/ward playing, participating in or
          attending any India Ultimate event(s) to use on media platforms (both
          print and online) including but not limited to the India Ultimate
          website, Instagram, Facebook, YouTube etc. I further acknowledge that
          the participation of my son/daughter/ward is voluntary and neither I
          nor my son/daughter/ward will not receive financial compensation of
          any type associated with the taking or publication of the
          photos/videos/livestream. I acknowledge and agree that publication of
          the aforesaid material confers no right of ownership or royalties
          whatsoever.
        </p>
      </Match>
      <Match when={!props.minor}>
        <p class="py-4">
          I, hereby give consent to India Ultimate, to take photographs, videos
          and live stream/broadcast myself playing, participating in or
          attending any India Ultimate event(s) to use on media platforms (both
          print and online) including but not limited to the India Ultimate
          website, Instagram, Facebook, YouTube etc. I further acknowledge that
          my participation is voluntary and I will not receive financial
          compensation of any type associated with the taking or publication of
          the photos/videos/livestream. I acknowledge and agree that publication
          of the aforesaid material confers no right of ownership or royalties
          whatsoever.
        </p>
      </Match>
    </Switch>
    <p class="py-4">
      Furthermore, if at any point in the future, should I wish to withdraw my
      consent, I will write an official email to India Ultimate
      (operations@indiaultimate.org) requesting the same.
    </p>
  </div>
);

const Disclaimer = () => {
  return (
    <div class="mt-6 inline-block font-medium">
      <h3 class="text-xl font-bold text-red-500">Disclaimer</h3>
      <p class="my-4">
        <strong>Please note:</strong> Any previously issued State/India Ultimate
        return-to-play guidelines for tournaments or otherwise, have been
        prepared for informational purposes alone and are not a substitute for
        legal or medical advice, which it is recommended to obtain prior to
        acting on or relying on these guidelines. The guidelines are not
        comprehensive or exhaustive with respect to the measures/protocols that
        may be undertaken or are required under law and may require
        modifications or additions as the current outbreak evolves, and new
        information becomes available. Actors are advised to closely follow the
        guidelines issued by the Ministry of Health and Family Welfare,
        Government of India, Ministry of Home Affairs, Government of India and
        from relevant state and local municipal authorities.
      </p>
    </div>
  );
};
const WaiverForm = props => {
  const [headline, setHeadline] = createSignal("");

  const [isLegal, setIsLegal] = createSignal(false);
  const [waiverSign, setWaiverSign] = createSignal(false);
  const [enableSubmit, setEnableSubmit] = createSignal(false);
  const [detailed, setDetailed] = createSignal(!props.signed);

  createEffect(() => {
    setEnableSubmit(waiverSign() && isLegal());
  });

  createEffect(() => {
    const headline = props.minor
      ? `Liability Waiver form and Guardian Consent for ${props.player.full_name}`
      : `Liability Waiver form for ${props.player.full_name}`;
    setHeadline(headline);
  });

  return (
    <div>
      <h1 class="mb-4 text-2xl font-bold text-blue-500">{headline()}</h1>
      <Show
        fallback={
          <p>
            There is no active membership for the {props.player.full_name}. Get
            a membership{" "}
            <A
              href={`/membership/${props.player.id}`}
              class="w-full cursor-pointer border-b border-gray-200 hover:bg-gray-100 hover:text-blue-700 focus:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:text-white dark:focus:ring-gray-500"
            >
              here
            </A>
            .
          </p>
        }
        when={props.player?.membership?.is_active}
      >
        <Show when={props.signed}>
          <div
            class="my-4 rounded-lg bg-green-50 p-4 text-sm text-green-800 dark:bg-gray-800 dark:text-green-400"
            role="alert"
          >
            Liability Waiver form for {props.player?.full_name} has been signed
            for {displayDate(props.player?.membership?.start_date)} to{" "}
            {displayDate(props.player?.membership?.end_date)} by{" "}
            {props.player?.membership?.waiver_signed_by} on{" "}
            {displayDate(props.player?.membership?.waiver_signed_at)}.
          </div>
          <button
            class="my-4 w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
            onClick={() => setDetailed(!detailed())}
          >
            Show full text
          </button>
        </Show>
        <Show when={detailed()}>
          <span>
            Validity: {displayDate(props?.player?.membership?.start_date)} to{" "}
            {displayDate(props?.player?.membership?.end_date)}
          </span>
          <PartA
            signed={props.signed}
            minor={props.minor}
            startDate={props?.player?.membership?.start_date}
            endDate={props?.player?.membership?.end_date}
          />
          <PartB
            signed={props.signed}
            minor={props.minor}
            onChange={setWaiverSign}
          />
          <MediaConsent
            signed={props.signed}
            player={props.player}
            minor={props.minor}
          />
          <Legal signed={props.signed} onChange={setIsLegal} />
        </Show>
        <Show when={!props.signed}>
          <button
            class={`my-4 w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto ${
              !enableSubmit() ? "cursor-not-allowed" : ""
            } `}
            onClick={props.handleSubmit} // eslint-disable-line solid/reactivity
            disabled={!enableSubmit()}
          >
            I Agree
          </button>
        </Show>
        <Show when={detailed()}>
          <Disclaimer date={props?.player?.membership?.waiver_signed_at} />
        </Show>
      </Show>
    </div>
  );
};

const Waiver = () => {
  const csrftoken = getCookie("csrftoken");

  const [store, { setPlayerById }] = useStore();
  const [player, setPlayer] = createSignal();
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const params = useParams();

  createEffect(() => {
    const player = getPlayer(store.data, Number(params.playerId));
    setPlayer(player);
  });

  const submitConsent = async () => {
    try {
      const response = await fetch("/api/waiver", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": csrftoken
        },
        body: JSON.stringify({ player_id: player()?.id })
      });
      setError("");
      if (response.ok) {
        const data = await response.json();
        setPlayerById(data);
      } else {
        const message = await response.json();
        const text = message?.message || JSON.stringify(message);
        setStatus(`${text}`);
      }
    } catch (error) {
      setStatus("");
      setError(`An error occurred while submitting waiver data: ${error}`);
    }
  };

  return (
    <>
      <Breadcrumbs
        icon={inboxStack}
        pageList={[
          { url: "/dashboard", name: "Dashboard" },
          { name: "Waiver" }
        ]}
      />
      <Switch>
        <Match when={!player()}>
          <p>Waiver information for player {params.playerId} not accessible.</p>
        </Match>
        <Match when={player()?.membership?.waiver_valid}>
          <>
            <WaiverForm
              signed={true}
              minor={true}
              player={player()}
              handleSubmit={submitConsent}
            />
          </>
        </Match>
        <Match
          when={player()?.guardian && player()?.guardian !== store.data.id}
        >
          <p>
            Waiver forms for {player()?.full_name} can only be signed by the
            guardian. The guardian can login to Hub with their Email and OTP.
            They will then be able to find their wards in the Dashboard where
            they can sign the waiver.
          </p>
        </Match>
        {/* Minors waiver form */}
        <Match when={player()?.guardian === store.data.id}>
          <WaiverForm
            minor={true}
            player={player()}
            handleSubmit={submitConsent}
          />
        </Match>
        {/* Self waiver form for adults */}
        <Match when={player().user == store.data.id}>
          <WaiverForm player={player()} handleSubmit={submitConsent} />
        </Match>
      </Switch>
      <p>{error()}</p>
      <p>{status()}</p>
    </>
  );
};

export default Waiver;
