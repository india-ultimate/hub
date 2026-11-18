import { A, useParams } from "@solidjs/router";
import { createQuery } from "@tanstack/solid-query";
import { trophy } from "solid-heroicons/solid";
import { Show } from "solid-js";

import { fetchTournamentBySlug } from "../queries";
import { Bar, Loading, PageHeaderSkeleton } from "../skeletons/primitives";
import { getTournamentBreadcrumbName } from "../utils";
import Error from "./alerts/Error";
import Breadcrumbs from "./Breadcrumbs";
import StyledMarkdown from "./StyledMarkdown";

const TournamentRules = () => {
  const params = useParams();

  const tournamentQuery = createQuery(
    () => ["tournaments", params.slug],
    () => fetchTournamentBySlug(params.slug)
  );

  return (
    <Show
      when={!tournamentQuery.isLoading}
      fallback={
        <Loading label="Loading tournament">
          <PageHeaderSkeleton breadcrumbs title={false} />
          <Bar class="mt-6 h-7 w-1/2" />
          <Bar class="mt-4 h-4 w-full" />
          <Bar class="mt-3 h-4 w-full" />
          <Bar class="mt-3 h-4 w-5/6" />
          <Bar class="mt-6 h-7 w-1/3" />
          <Bar class="mt-4 h-4 w-full" />
          <Bar class="mt-3 h-4 w-4/5" />
        </Loading>
      }
    >
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
              name: getTournamentBreadcrumbName(
                tournamentQuery.data?.event?.slug || ""
              )
            }
          ]}
        />
        <Show when={tournamentQuery.isError}>
          <Error text="The tournament could not be loaded. Please try again." />
        </Show>
        <Show
          when={tournamentQuery.data?.rules}
          fallback={
            <Show when={tournamentQuery.isSuccess}>
              <p>Rules does not exist for this tournament</p>
            </Show>
          }
        >
          <StyledMarkdown markdown={tournamentQuery.data.rules} />
        </Show>
      </Show>
    </Show>
  );
};

export default TournamentRules;
