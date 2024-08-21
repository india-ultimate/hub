import { A } from "@solidjs/router";

import { WALink } from "../constants";

export default function Footer() {
  const _email = "operations+hub@indiaultimate.org";
  return (
    <div>
      <footer class="m-4 rounded-lg bg-white shadow dark:bg-gray-800">
        <div class="mx-auto w-full max-w-screen-xl p-4 md:flex md:items-center md:justify-between">
          <span class="text-sm text-gray-500 dark:text-gray-400 sm:text-center">
            ©{" "}
            <A href="/" class="hover:underline">
              UPAI & FDSF(I)
            </A>
          </span>
          <ul class="mt-3 flex flex-wrap items-center text-sm font-medium text-gray-500 dark:text-gray-400 sm:mt-0">
            <li>
              <A href="/about" class="mr-4 hover:underline md:mr-6 ">
                About
              </A>
            </li>
            <li>
              <A
                href="/terms-and-conditions"
                class="mr-4 hover:underline md:mr-6 "
              >
                Terms & Conditions
              </A>
            </li>
            <li>
              <A href="/privacy-policy" class="mr-4 hover:underline md:mr-6 ">
                Privacy Policy
              </A>
            </li>
            <li>
              <A href="/legal" class="mr-4 hover:underline md:mr-6">
                Refund Policy
              </A>
            </li>
            <li>
              <A href="/contact-us" class="mr-4 hover:underline md:mr-6">
                Contact Us
              </A>
            </li>
            {/* <li>
              <a
                class="mr-4 hover:underline md:mr-6"
                title={email}
                href={`mailto:${email}`}
              >
                Email Us
              </a>
            </li> */}
            <li>
              <a href={WALink} class="mr-4 hover:underline md:mr-6">
                WhatsApp Us
              </a>
            </li>
          </ul>
        </div>
      </footer>
    </div>
  );
}
