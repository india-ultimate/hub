import { getCookie } from "../utils.js";

const Home = () => {
  return (
    <div>
      <h1 class="text-4xl font-bold mb-4 text-red-500">Welcome to the Home Page!</h1>
      <p>Welcome!</p>
      <a
        class="text-4xl text-blue-600"
        href="https://github.com/solidjs/solid"
        target="_blank"
        rel="noopener noreferrer"
      >
        Learn Solid, Tailwind CSS and Flowbite
      </a>
    </div>
  );
};

export default Home;
