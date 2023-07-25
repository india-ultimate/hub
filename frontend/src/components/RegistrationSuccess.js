import Player from "./Player";

const RegistrationSuccess = props => (
  <div>
    <h2 class="text-4xl font-bold text-blue-500">Successful Registration!</h2>
    <div class="my-8">
      <Player player={props.player} others={props.others} ward={props.ward} />
    </div>
  </div>
);

export default RegistrationSuccess;
