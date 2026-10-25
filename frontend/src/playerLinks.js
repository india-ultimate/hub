import { A } from "@solidjs/router";
import { useQueryClient } from "@tanstack/solid-query";
import { Show, splitProps } from "solid-js";

import { fetchPlayerProfile } from "./queries";

export const profileQueryKey = slug => ["player-profile", slug];

export const usePrefetchPlayer = () => {
  const queryClient = useQueryClient();
  return slug =>
    queryClient.prefetchQuery({
      queryKey: profileQueryKey(slug),
      queryFn: () => fetchPlayerProfile(slug),
      staleTime: 60_000
    });
};

const inert = cls =>
  cls
    ?.split(/\s+/)
    .filter(c => !/(^|:)(hover|focus-visible):|^transition/.test(c))
    .join(" ");

export const PlayerLink = props => {
  const [local, rest] = splitProps(props, ["slug", "from", "children"]);
  const prefetch = usePrefetchPlayer();
  const warm = () => prefetch(local.slug);

  return (
    <Show
      when={local.slug}
      fallback={<span class={inert(rest.class)}>{local.children}</span>}
    >
      <A
        {...rest}
        href={`/player/${local.slug}`}
        state={{ from: local.from }}
        onPointerEnter={warm}
        onFocus={warm}
        onTouchStart={warm}
      >
        {local.children}
      </A>
    </Show>
  );
};
