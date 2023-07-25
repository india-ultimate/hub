import Player from "./Player";

const RegistrationSuccess = props => (
  <div>
    <h2 class="text-4xl font-bold text-blue-500">Successful Registration!</h2>
    <div class="my-8">
      <Player player={props.player} others={true} />
    </div>
  </div>
);

export default RegistrationSuccess;
