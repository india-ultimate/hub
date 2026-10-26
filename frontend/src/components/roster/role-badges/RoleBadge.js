import CaptainBadge from "./Captain";
import CoachBadge from "./Coach";
import ManagerBadge from "./Manager";
import SpiritCaptainBadge from "./SpiritCaptain";

const ROLE_BADGES = {
  CAP: CaptainBadge,
  SCAP: SpiritCaptainBadge,
  COACH: CoachBadge,
  ACOACH: CoachBadge,
  MNGR: ManagerBadge
};

const RoleBadge = props => {
  const Badge = () => ROLE_BADGES[props.role];
  return <>{Badge() ? Badge()() : null}</>;
};

export default RoleBadge;
