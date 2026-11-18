import { ListSkeleton, Loading } from "./primitives";

const Roster = () => (
  <Loading label="Loading roster">
    <ListSkeleton rows={15} avatar />
  </Loading>
);

export default Roster;
