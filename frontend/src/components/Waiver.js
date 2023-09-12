import { useStore } from "../store";
import { useParams } from "@solidjs/router";
import {
  createSignal,
  createEffect,
  onMount,
  Show,
  Switch,
  Match,
  mergeProps
} from "solid-js";
import { A } from "@solidjs/router";
import { getCookie, fetchUserData, displayDate, getPlayer } from "../utils";
import StatusStepper from "./StatusStepper";
import Breadcrumbs from "./Breadcrumbs";
import { inboxStack } from "solid-heroicons/solid";

const Legal = props => (
  <div class="my-10">
    <label class="flex select-none space-x-4 font-medium">
      <input
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
          UPAI events between {displayDate(props.startDate)} and{" "}
          {displayDate(props.endDate)}, I acknowledge and agree to the
          following:
        </p>
        <ol class="pl-5 mt-2 space-y-1 list-decimal list-inside my-4">
          <li>
            I am aware of the existence of the risk on my son/daughter/ward's
            physical appearance to the venues and his/ her participation in the
            activities of the Organization that may cause injury or illness such
            as, but not limited to Influenza, MRSA, or COVID-19 that may lead to
            paralysis or death.
          </li>
          <li>
            My son/daughter/ward has not experienced symptoms that of fever,
            fatigue, difficulty in breathing, or dry cough or exhibiting any
            other symptoms relating to COVID-19 or any communicable disease
            within the last 10 days. In the event that he or she experiences the
            above stated symptoms on any day prior to 10 days from the start of
            the tournament, he or she shall refrain from playing the tournament.
          </li>
          <li>
            My son/daughter/ward has not / will not have, nor any member(s) of
            my household, travelled by sea or by air, internationally on any day
            prior to 10 days from the start of the tournament. In the event that
            my son/daughter/ward or any member(s) of his/her household have
            either travelled by sea or air, internationally, my
            son/daughter/ward shall communicate the same to the UPAI Operations
            Team and he/she shall obtain a Negative RTPCR report any time prior
            to 48 hours of the start of the event and share the same with the
            UPAI Operations via email to operations@indiaultimate.org without
            which my son/daughter/ward shall not be allowed to participate in
            the event.
          </li>
          <li>
            My son/daughter/ward has not, nor any member(s) of my household,
            diagnosed to be infected of COVID-19 virus within the last 15 days
            prior to a UPAI event. In the event that he/she or any member of our
            family has been diagnosed with COVID 19 on any day prior to 15 days
            from the start of the event, he or she shall refrain from
            participating in that event.
          </li>
          <li>
            My son/daughter/ward's original fully vaccinated certificate as
            shared by the Government of India/ any other authorized agent
            without tampering with the same has been uploaded.
          </li>
        </ol>
        <label class="flex select-none space-x-4 font-medium">
          <input
            class="mt-1 h-4 w-4 cursor-pointer lg:mt-1 lg:h-5 lg:w-5"
            type="checkbox"
            onChange={e => props.onChange(e.target.checked)}
            checked={props.signed}
            disabled={props.signed}
          />
          <span>I acknowledge and agree to the above.</span>
        </label>
      </Match>
      <Match when={!props.minor}>
        <p>
          In consideration of my participation in UPAI's events that require me
          to be fully vaccinated against Covid-19, from{" "}
          {displayDate(props.startDate)} to {displayDate(props.endDate)}, I, the
          undersigned, acknowledge and agree to the following:
        </p>
        <ol class="pl-5 mt-2 space-y-1 list-decimal list-inside my-4">
          <li>
            I am aware of the existence of the risk on my physical appearance to
            the venues and my participation in the activities of the
            Organization that may cause injury or illness such as, but not
            limited to Influenza, MRSA, or COVID-19 that may lead to paralysis
            or death.
          </li>
          <li>
            If I have experienced symptoms that of fever, fatigue, difficulty in
            breathing, or dry cough or exhibiting any other symptoms relating to
            COVID-19 or any communicable disease within the last 14 days prior
            to an event, I will not participate in or appear at that event.
          </li>
          <li>
            If I, or any member(s) of my household, have been diagnosed to be
            infected of COVID-19 virus within the last 30 days prior to an
            event, I will not participate in or appear at that event.
          </li>
          <li>
            I have received two shots of Vaccination and that I am including my
            final vaccination certificate below.
          </li>
        </ol>
        <label class="flex select-none space-x-4 font-medium">
          <input
            class="mt-1 h-4 w-4 cursor-pointer lg:mt-1 lg:h-5 lg:w-5"
            type="checkbox"
            onChange={e => props.onChange(e.target.checked)}
            checked={props.signed}
            disabled={props.signed}
          />
          <span>I acknowledge and agree to the above.</span>
        </label>
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
        <ol class="pl-5 mt-2 space-y-1 list-decimal list-inside my-4">
          <li>
            I am fully and personally responsible for my son/daughter/ward's own
            safety and actions while and during his/her participation and
            recognize that my son/daughter/ward may be at risk of contracting
            COVID-19.
          </li>
          <li>
            With full knowledge of the risks involved, I hereby release, waive,
            discharge the Organization, its board, officers, independent
            contractors, affiliates, employees, representatives, successors,
            volunteers, and assigns from any and all liabilities, claims,
            demands, actions, and causes of action whatsoever, directly or
            indirectly arising out of or related to any loss, damage, injury, or
            death, that may be sustained by my son/daughter/ward related to
            COVID-19 while participating in any activity while in, on, or around
            the premises or while using the facilities that may lead to
            unintentional exposure or harm due to COVID-19.
          </li>
          <li>
            I agree to indemnify, defend, and hold harmless the Organization
            from and against any and all costs, expenses, damages, lawsuits,
            and/or liabilities or claims arising whether directly or indirectly
            from or related to any and all claims made by or against any of the
            released party due to injury, loss, or death from or related to
            COVID-19 sustained or suffered by my son/daughter/ward.
          </li>
          <li>
            By checking the box below I acknowledge that I have read the
            foregoing Liability Release Waiver concerning my son/daughter/ward
            and understand its contents; that I am the Parent or Legal Guardian
            and that I am fully competent to give my consent on behalf of my
            son/daughter/ward; That I have been sufficiently informed of the
            risks involved and give my voluntary consent in signing it as my own
            free act and deed on behalf of my son/daughter/ward; that I give my
            voluntary consent in accepting this Liability Release Waiver by
            checking the box below as my own free act and deed with full
            intention to be bound by the same on behalf of my son/daughter/ward,
            and free from any inducement or representation.
          </li>
        </ol>
        <label class="flex select-none space-x-4 font-medium">
          <input
            class="mt-1 h-4 w-4 cursor-pointer lg:mt-1 lg:h-5 lg:w-5"
            type="checkbox"
            onChange={e => props.onChange(e.target.checked)}
            checked={props.signed}
            disabled={props.signed}
          />
          <span>
            I acknowledge that I have read the foregoing Liability Release
            Waiver and understand its contents; That I have been sufficiently
            informed of the risks involved and give my voluntary consent in
            signing it as my own free act and deed; that I give my voluntary
            consent in signing this Liability Release Waiver as my own free act
            and deed with full intention to be bound by the same, and free from
            any inducement or representation.
          </span>
        </label>
      </Match>
      <Match when={!props.minor}>
        <p>
          Following the pronouncements above I hereby declare the following:
        </p>
        <ol class="pl-5 mt-2 space-y-1 list-decimal list-inside my-4">
          <li>
            I am fully and personally responsible for my own safety and actions
            while and during my participation and I recognize that I may be at
            risk of contracting COVID-19.
          </li>
          <li>
            With full knowledge of the risks involved, I hereby release, waive,
            discharge the Organization, its board, officers, independent
            contractors, affiliates, employees, representatives, successors,
            volunteers, and assigns from any and all liabilities, claims,
            demands, actions, and causes of action whatsoever, directly or
            indirectly arising out of or related to any loss, damage, injury, or
            death, that may be sustained by me related to COVID-19 while
            participating in any activity while in, on, or around the premises
            or while using the facilities that may lead to unintentional
            exposure or harm due to COVID-19.
          </li>
          <li>
            I agree to indemnify, defend, and hold harmless the Organization
            from and against any and all costs, expenses, damages, lawsuits,
            and/or liabilities or claims arising whether directly or indirectly
            from or related to any and all claims made by or against any of the
            released party due to injury, loss, or death from or related to
            COVID-19.
          </li>
          <li>
            By signing below I acknowledge that I have read the foregoing
            Liability Release Waiver and understand its contents;  That I have
            been sufficiently informed of the risks involved and give my
            voluntary consent in signing it as my own free act and deed; that I
            give my voluntary consent in signing this Liability Release Waiver
            as my own free act and deed with full intention to be bound by the
            same, and free from any inducement or representation.
          </li>
        </ol>
        <label class="flex select-none space-x-4 font-medium">
          <input
            class="mt-1 h-4 w-4 cursor-pointer lg:mt-1 lg:h-5 lg:w-5"
            type="checkbox"
            onChange={e => props.onChange(e.target.checked)}
            checked={props.signed}
            disabled={props.signed}
          />
          <span>
            I acknowledge that I have read the foregoing Liability Release
            Waiver and understand its contents; That I have been sufficiently
            informed of the risks involved and give my voluntary consent in
            signing it as my own free act and deed; that I give my voluntary
            consent in signing this Liability Release Waiver as my own free act
            and deed with full intention to be bound by the same, and free from
            any inducement or representation.
          </span>
        </label>
      </Match>
    </Switch>
  </div>
);

const MediaConsent = props => (
  <div class="my-10">
    <h3 class="text-xl font-bold text-blue-500">Media Consent</h3>
    <p class="my-4">
      <Switch>
        <Match when={props.minor}>
          I, the parent/legal guardian of the above mentioned minor, hereby give
          consent to Ultimate Players Association of India to take photographs,
          videos and live stream of my son/ daughter or ward playing,
          participating or attending any UPAI event(s) and to use the same
          material on media platforms (both print and online) including but not
          limited to the UPAI website, Instagram, Facebook, YouTube etc. I
          further acknowledge that participation of my son/ daughter or ward is
          voluntary and neither I nor my son/ daughter or ward will receive
          financial compensation of any type associated with the taking or
          publication of the photos/videos/ livestream. I acknowledge and agree
          that publication of the aforesaid material confers no right of
          ownership or royalties whatsoever.
        </Match>
        <Match when={!props.minor}>
          I, hereby give consent to Ultimate Players Association of India to
          take photographs, videos and live stream myself playing, participating
          in or attending any UPAI event(s) to use on media platforms (both
          print and online) including but not limited to the UPAI website,
          Instagram, Facebook, YouTube etc. I further acknowledge that my
          participation is voluntary and I will not receive financial
          compensation of any type associated with the taking or publication of
          the photos/videos/ livestream. I acknowledge and agree that
          publication of the aforesaid material confers no right of ownership or
          royalties whatsoever.
        </Match>
      </Switch>
    </p>
    <label class="flex select-none space-x-4 font-medium">
      <input
        class="mt-1 h-4 w-4 cursor-pointer lg:mt-1 lg:h-5 lg:w-5"
        type="checkbox"
        onChange={e => props.onChange(e.target.checked)}
        checked={props.signed}
        disabled={props.signed}
      />
      <span>
        I have read and understood whatever is stated above and hereby do give
        my consent
      </span>
    </label>
  </div>
);

const Disclaimer = _props => {
  const props = mergeProps({ date: new Date() }, _props);
  return (
    <div class="mt-6 inline-block font-medium">
      <h3 class="text-xl font-bold text-red-500">Disclaimer</h3>
      <p class="my-4">
        The Ultimate Players Association of India ('UPAI') hereby makes clear
        that all further play (including tournaments, team or other practice,
        pick-up, throwing, workouts, and any other activities connected to disc
        sport, other than those done individually; and including travel,
        hosting, meetings, meals and other affiliated acts in connection with
        such play, undertaken by state bodies, clubs, organizations (including
        those engaged in development using disc sport, school related bodies or
        of any other kind), teams, individuals (including parents, wards or
        guardians of minors), or any affiliated persons (each an 'Actor'),
        whether or not affiliated to the UPAI, in any capacity, in or outside
        India, whether in a formal or informal setting (each such act
        individually, or taken together, by any Actor, hereafter referred to as
        'Play'), as of {displayDate(props.date)} until stated otherwise, is
        undertaken in personal capacity. Importantly, it is also hereby made
        clear, that neither the UPAI, nor any of its employees, agents or
        representatives shall be responsible, and no action may be brought
        against them, for any COVID-19 (or related infection/illnesses) or other
        personal injury, illness, permanent disability, death and/or other
        damage, loss, claim, liability or expense of any kind occurring prior
        to, during or after participation in Play by an Actor or any other third
        party. All Actors engaged in any such, or other, Play are assumed to
        know and acknowledge the contagious nature of Covid-19 (or related
        infections/illnesses), and voluntarily assume all risk of and
        responsibility themselves, for exposure to such infections, whether
        caused by actions, omission, negligence or otherwise of themselves or
        other participants or connected persons, and any resulting personal
        injury, illness, permanent disability, death and/or other damage, loss,
        claim, liability or expense of any kind.
      </p>
      <p>
        Please note: Any previously issued state or UPAI return-to-play
        guidelines for tournaments or otherwise, have been prepared for
        informational purposes alone and are not a substitute for legal or
        medical advice, which it is recommended to obtain prior to acting on or
        relying on these guidelines. The guidelines are not comprehensive or
        exhaustive with respect to the measures/protocols that may be undertaken
        or are required under law and may require modifications or additions as
        the current outbreak evolves, and new information becomes available.
        Actors are advised to closely follow the guidelines issued by the
        Ministry of Health and Family Welfare, Government of India, Ministry of
        Home Affairs, Government of India and from relevant state and local
        municipal authorities.
      </p>
    </div>
  );
};
const WaiverForm = props => {
  const [headline, setHeadline] = createSignal("");

  const [isLegal, setIsLegal] = createSignal(false);
  const [mediaConsent, setMediaConsent] = createSignal(false);
  const [partA, setPartA] = createSignal(false);
  const [partB, setPartB] = createSignal(false);
  const [enableSubmit, setEnableSubmit] = createSignal(false);
  const [detailed, setDetailed] = createSignal(!props.signed);

  createEffect(() => {
    setEnableSubmit(mediaConsent() && partA() && partB() && isLegal());
  });

  createEffect(() => {
    const headline = props.minor
      ? `Liability Waiver form and Guardian Consent for ${props.player.full_name}`
      : `Liability Waiver form for ${props.player.full_name}`;
    setHeadline(headline);
  });

  return (
    <div>
      <h1 class="text-4xl font-bold text-blue-500">{headline()}</h1>
      <Show
        fallback={
          <p>
            There is no active membership for the {props.player.full_name}. Get
            a membership{" "}
            <A
              href={`/membership/${props.player.id}`}
              class="w-full border-b border-gray-200 cursor-pointer hover:bg-gray-100 hover:text-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-700 focus:text-blue-700 dark:border-gray-600 dark:hover:bg-gray-600 dark:hover:text-white dark:focus:ring-gray-500 dark:focus:text-white"
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
            class="p-4 my-4 text-sm text-green-800 rounded-lg bg-green-50 dark:bg-gray-800 dark:text-green-400"
            role="alert"
          >
            Liability Waiver form for {props.player?.full_name} has been signed
            for {displayDate(props.player?.membership?.start_date)} to{" "}
            {displayDate(props.player?.membership?.end_date)} by{" "}
            {props.player?.membership?.waiver_signed_by} on{" "}
            {displayDate(props.player?.membership?.waiver_signed_at)}.
          </div>
          <button
            class="my-4 text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
            onClick={() => setDetailed(!detailed())}
          >
            Show full text
          </button>
          <StatusStepper player={props.player} />
        </Show>
        <Show when={detailed()}>
          <PartA
            signed={props.signed}
            minor={props.minor}
            onChange={setPartA}
            startDate={props?.player?.membership?.start_date}
            endDate={props?.player?.membership?.end_date}
          />
          <PartB
            signed={props.signed}
            minor={props.minor}
            onChange={setPartB}
          />
          <MediaConsent
            signed={props.signed}
            minor={props.minor}
            onChange={setMediaConsent}
          />
          <Disclaimer date={props?.player?.membership?.waiver_signed_at} />
          <Legal signed={props.signed} onChange={setIsLegal} />
        </Show>
        <Show when={!props.signed}>
          <button
            class={`my-4 text-white bg-blue-700 hover:bg-blue-800 focus:ring-4 focus:outline-none focus:ring-blue-300 font-medium rounded-lg text-sm w-full sm:w-auto px-5 py-2.5 text-center dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 ${
              !enableSubmit() ? "cursor-not-allowed" : ""
            } `}
            onClick={props.handleSubmit} // eslint-disable-line solid/reactivity
            disabled={!enableSubmit()}
          >
            I Agree
          </button>
        </Show>
      </Show>
    </div>
  );
};

const Waiver = () => {
  const csrftoken = getCookie("csrftoken");

  const [store, { userFetchSuccess, userFetchFailure, setPlayerById }] =
    useStore();

  const [player, setPlayer] = createSignal();
  const [status, setStatus] = createSignal("");
  const [error, setError] = createSignal("");

  const params = useParams();

  createEffect(() => {
    const player = getPlayer(store.data, Number(params.playerId));
    setPlayer(player);
  });

  onMount(() => {
    if (!store.loggedIn) {
      fetchUserData(userFetchSuccess, userFetchFailure);
    }
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
            guardian.
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
