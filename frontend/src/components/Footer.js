export default function Footer() {
  return (
    <div>
      <footer class="bg-white rounded-lg shadow m-4 dark:bg-gray-800">
          <div class="w-full mx-auto max-w-screen-xl p-4 md:flex md:items-center md:justify-between">
            <span class="text-sm text-gray-500 sm:text-center dark:text-gray-400">© 2023 <a href="#/" class="hover:underline">UPAI</a>. Play Ultimate.
          </span>
          <ul class="flex flex-wrap items-center mt-3 text-sm font-medium text-gray-500 dark:text-gray-400 sm:mt-0">
              <li>
                  <a href="#/about" class="mr-4 hover:underline md:mr-6 ">About</a>
              </li>
              <li>
                  <a href="#" class="mr-4 hover:underline md:mr-6">Privacy Policy</a>
              </li>
              <li>
                <a href="mailto:operations+hub@indiaultimate.org" class="hover:underline">Contact</a>
              </li>
          </ul>
          </div>
      </footer>
    </div>
  );
};
