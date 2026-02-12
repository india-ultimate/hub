import { createForm, required, reset } from "@modular-forms/solid";
import { useNavigate } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { chatBubbleOvalLeftEllipsis } from "solid-heroicons/outline";
import { createSignal, Show } from "solid-js";

import { createTicket, fetchUser } from "../../queries";
import Breadcrumbs from "../Breadcrumbs";

const CreateTicket = () => {
  const [isSubmitting, setIsSubmitting] = createSignal(false);
  const [error, setError] = createSignal(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Breadcrumbs data
  const breadcrumbItems = [
    { name: "Help", url: "/tickets" },
    { name: "Create Ticket", url: "" }
  ];

  // Check if user is authenticated
  const userQuery = createQuery(() => ["me"], fetchUser);
  const initialValues = {
    title: "",
    description: "",
    priority: "MED",
    category: ""
  };

  const formId = "create-ticket";
  const [_form, { Form, Field }] = createForm({
    id: formId,
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const createTicketMutation = createMutation({
    mutationFn: createTicket,
    onSuccess: data => {
      setIsSubmitting(false);
      queryClient.invalidateQueries(["tickets"]);
      reset(_form);
      // Redirect to the created ticket's detail page
      navigate(`/tickets/${data.id}`);
    },
    onError: error => {
      setError(error.message || "An error occurred while creating the ticket");
      setIsSubmitting(false);
    }
  });

  const handleSubmit = async values => {
    setIsSubmitting(true);
    setError(null);
    createTicketMutation.mutate(values);
  };

  const handleLoginRedirect = () => {
    navigate("/login");
  };

  return (
    <div class="space-y-4">
      {/* Breadcrumb Navigation */}
      <Breadcrumbs
        icon={chatBubbleOvalLeftEllipsis}
        pageList={breadcrumbItems}
      />

      <div class="rounded-lg bg-white dark:bg-gray-800 md:p-6 md:shadow">
        <h2 class="mb-6 text-2xl font-bold text-blue-700 dark:text-white">
          Create Help Ticket
        </h2>

        <Show
          when={userQuery.data}
          fallback={
            <div class="rounded-lg bg-yellow-100 p-6 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-300">
              <div class="flex items-center">
                <svg
                  class="mr-2 h-5 w-5"
                  fill="currentColor"
                  viewBox="0 0 20 20"
                  xmlns="http://www.w3.org/2000/svg"
                >
                  <path
                    fill-rule="evenodd"
                    d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
                    clip-rule="evenodd"
                  />
                </svg>
                <h3 class="text-lg font-medium">Authentication Required</h3>
              </div>
              <div class="mt-2">
                <p>You need to be logged in to create support tickets.</p>
                <button
                  onClick={handleLoginRedirect}
                  class="mt-3 inline-flex items-center rounded-lg bg-blue-700 px-4 py-2 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
                >
                  Log In
                </button>
              </div>
            </div>
          }
        >
          <Show when={isSubmitting()}>
            <div class="flex justify-center p-4">
              <div class="h-12 w-12 animate-spin rounded-full border-b-2 border-t-2 border-blue-600" />
            </div>
          </Show>

          <Show when={!isSubmitting()}>
            {error() && (
              <div
                class="mb-4 rounded-lg bg-red-100 p-4 text-sm text-red-700"
                role="alert"
              >
                {error()}
              </div>
            )}

            <Form class="space-y-6" onSubmit={values => handleSubmit(values)}>
              <Field name="title" validate={required("Title is required")}>
                {(field, props) => (
                  <div>
                    <label
                      for={props.name}
                      class="mb-2 block text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Title
                    </label>
                    <input
                      {...props}
                      type="text"
                      id={props.name}
                      value={field.value}
                      class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400"
                      placeholder="Brief summary of your issue"
                    />
                    {field.error && (
                      <p class="mt-1 text-sm text-red-600">{field.error}</p>
                    )}
                  </div>
                )}
              </Field>

              <Field name="category">
                {(field, props) => (
                  <div>
                    <label
                      for={props.name}
                      class="mb-2 block text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Category
                    </label>
                    <select
                      {...props}
                      id={props.name}
                      value={field.value}
                      class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    >
                      <option value="">Select a category</option>
                      <option value="Account">Account</option>
                      <option value="Competitions">Competitions</option>
                      <option value="Membership">Membership</option>
                      <option value="Tournament">Tournament</option>
                      <option value="Payment">Payment</option>
                      <option value="Tech">Tech</option>
                      <option value="Other">Other</option>
                    </select>
                  </div>
                )}
              </Field>

              <Field
                name="priority"
                validate={required("Priority is required")}
              >
                {(field, props) => (
                  <div>
                    <label
                      for={props.name}
                      class="mb-2 block text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Priority
                    </label>
                    <select
                      {...props}
                      id={props.name}
                      value={field.value}
                      class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white"
                    >
                      <option value="LOW">Low</option>
                      <option value="MED">Medium</option>
                      <option value="HIG">High</option>
                      <option value="URG">Urgent</option>
                    </select>
                  </div>
                )}
              </Field>

              <Field
                name="description"
                validate={required("Description is required")}
              >
                {(field, props) => (
                  <div>
                    <label
                      for={props.name}
                      class="mb-2 block text-sm font-medium text-gray-900 dark:text-white"
                    >
                      Description
                    </label>
                    <textarea
                      {...props}
                      id={props.name}
                      value={field.value}
                      rows="4"
                      class="block w-full rounded-lg border border-gray-300 bg-gray-50 p-2.5 text-sm text-gray-900 focus:border-blue-500 focus:ring-blue-500 dark:border-gray-600 dark:bg-gray-700 dark:text-white dark:placeholder-gray-400"
                      placeholder="Please describe your issue in detail"
                    />
                    {field.error && (
                      <p class="mt-1 text-sm text-red-600">{field.error}</p>
                    )}
                  </div>
                )}
              </Field>

              <button
                type="submit"
                disabled={isSubmitting()}
                class="w-full rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:opacity-50 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800"
              >
                {isSubmitting() ? "Creating Ticket..." : "Create Ticket"}
              </button>
            </Form>
          </Show>
        </Show>
      </div>
    </div>
  );
};

export default CreateTicket;
