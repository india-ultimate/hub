import {
  Bar,
  Loading,
  PageHeaderSkeleton,
  TableRowsSkeleton
} from "./primitives";

const TabsSkeleton = () => (
  <div class="my-6 flex h-11 justify-center space-x-2">
    <Bar class="h-11 w-24 !rounded-full" />
    <Bar class="h-11 w-20 !rounded-full" />
    <Bar class="h-11 w-20 !rounded-full" />
  </div>
);

const DetailsSkeleton = () => (
  <>
    <div class="mt-2 flex h-5 justify-center">
      <Bar class="h-4 w-40" />
    </div>
    <div class="mt-2 flex h-5 justify-center">
      <Bar class="h-4 w-52" />
    </div>
    <div class="mt-3 flex h-11 justify-center">
      <Bar class="h-11 w-40 !rounded-full" />
    </div>
    <div class="mt-5 flex h-6 justify-center">
      <Bar class="h-6 w-20" />
    </div>
    <Bar class="mt-5 h-[90px] w-full !rounded-lg" />
    <Bar class="mt-5 h-[90px] w-full !rounded-lg" />
    <Bar class="mt-5 h-[90px] w-full !rounded-lg" />
  </>
);

export const TournamentPageSkeleton = props => (
  <Loading label="Loading tournament">
    <PageHeaderSkeleton breadcrumbs />
    {props.details && <DetailsSkeleton />}
    {props.details && props.tabs && (
      <div class="mt-5 flex h-7 justify-center">
        <Bar class="h-6 w-48" />
      </div>
    )}
    {props.tabs && <TabsSkeleton />}
    {props.tabs && <TableRowsSkeleton rows={6} cols={3} />}
  </Loading>
);

export { TabsSkeleton };
