import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { trophy } from "solid-heroicons/solid";
import { Show } from "solid-js";

import { fetchTournamentBySlug } from "../queries";
import Breadcrumbs from "./Breadcrumbs";
import StyledMarkdown from "./StyledMarkdown";

const TournamentRules = () => {
  const params = useParams();

  const tournamentQuery = createQuery(
    () => ["tournament", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );

  return (
    <Show
      when={!tournamentQuery.data?.message}
      fallback={
        <div>
          Tournament could not be fetched. Error -{" "}
          {tournamentQuery.data.message}
          <A href={"/tournaments"} class="text-blue-600 dark:text-blue-500">
            <br />
            Back to Tournaments Page
          </A>
        </div>
      }
    >
      <Breadcrumbs
        icon={trophy}
        pageList={[
          { url: "/tournaments", name: "All Tournaments" },
          {
            url: `/tournament/${params.slug}`,
            name: tournamentQuery.data?.event?.ultimate_central_slug
              ?.split("-")
              .splice(-2)
              .map(word => word[0].toUpperCase() + word.slice(1))
              .join(" ")
          }
        ]}
      />
      <Show
        when={tournamentQuery.data.rules}
        fallback={<p>Rules does not exist for this tournament</p>}
      >
        <StyledMarkdown markdown={tournamentQuery.data.rules} />
      </Show>
    </Show>
  );
};

export default TournamentRules;
