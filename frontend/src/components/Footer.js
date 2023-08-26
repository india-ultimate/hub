import { A } from "@solidjs/router";

export default function Footer() {
  const email = "operations+hub@indiaultimate.org";
  return (
    <div>
      <footer class="bg-white rounded-lg shadow m-4 dark:bg-gray-800">
        <div class="w-full mx-auto max-w-screen-xl p-4 md:flex md:items-center md:justify-between">
          <span class="text-sm text-gray-500 sm:text-center dark:text-gray-400">
            ©{" "}
            <A href="/" class="hover:underline">
              UPAI
            </A>
          </span>
          <ul class="flex flex-wrap items-center mt-3 text-sm font-medium text-gray-500 dark:text-gray-400 sm:mt-0">
            <li>
              <A href="/about" class="mr-4 hover:underline md:mr-6 ">
                About
              </A>
            </li>
            <li>
              <A href="#" class="mr-4 hover:underline md:mr-6">
                Privacy Policy
              </A>
            </li>
            <li>
              <a title={email} href={`mailto:${email}`} class="hover:underline">
                Contact
              </a>
            </li>
          </ul>
        </div>
      </footer>
    </div>
  );
}
