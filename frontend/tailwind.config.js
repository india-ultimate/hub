/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./src/**/*.{js,jsx,ts,tsx}", "./node_modules/flowbite/**/*.js"],
  theme: {
    extend: {}
  },
  plugins: [require("flowbite/plugin")],
  safelist: [
    "text-green-600",
    "dark:text-green-500",
    "bg-green-100",
    "bg-green-700",
    "after:border-green-100",
    "dark:after:border-green-700",
    "text-red-600",
    "dark:text-red-500",
    "bg-red-100",
    "bg-red-700",
    "after:border-red-100",
    "dark:after:border-red-700",
    "bg-gray-100",
    "bg-gray-700",
    "after:border-gray-100",
    "dark:after:border-gray-700"
  ],
  darkMode: 'class'
};
