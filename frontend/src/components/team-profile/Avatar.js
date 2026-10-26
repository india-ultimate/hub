import { Show } from "solid-js";

import Initials from "../player-profile/Initials";

const Avatar = props => (
  <Show
    when={props.src}
    fallback={
      <Initials
        name={props.name}
        class={`${props.size} rounded-full text-xs`}
      />
    }
  >
    <img
      src={props.src}
      alt=""
      width="40"
      height="40"
      loading="lazy"
      class={`${props.size} flex-none rounded-full object-cover`}
    />
  </Show>
);

export default Avatar;
