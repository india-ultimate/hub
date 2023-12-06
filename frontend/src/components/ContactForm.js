import { createForm, maxSize, required } from "@modular-forms/solid";
import { createSignal, Show } from "solid-js";

import { Spinner } from "../icons";
import { getCookie } from "../utils";
import FileInput from "./FileInput";
import TextAreaInput from "./TextAreaInput";
import TextInput from "./TextInput";

const ContactForm = props => {
  const initialValues = {};
  const [status, setStatus] = createSignal("");

  const [contactForm, { Form, Field }] = createForm({
    initialValues,
    validateOn: "touched",
    revalidateOn: "touched"
  });

  const handleSubmit = async values => {
    const { attachment, ...data } = values;
    const formData = new FormData();
    formData.append("contact_form", JSON.stringify(data));
    formData.append("attachment", attachment);

    setStatus("");

    try {
      const response = await fetch("/api/contact", {
        method: "POST",
        headers: {
          "X-CSRFToken": getCookie("csrftoken")
        },
        body: formData
      });
      if (response.ok) {
        setStatus("The form has been submitted! ✨");
      } else {
        const message = await response.json();
        const text = message?.message || JSON.stringify(message);
        setStatus(`${text}`);
      }
    } catch (error) {
      setStatus(`An error occurred: ${error}`);
    }
  };

  return (
    <Form
      class="text-sm dark:text-white"
      onSubmit={values => handleSubmit(values)}
    >
      <Field name="subject" validate={[required("Please enter a subject.")]}>
        {(field, props) => (
          <TextInput
            {...props}
            value={field.value}
            error={field.error}
            type="text"
            label="Subject"
            placeholder="Please help me with ..."
            required
          />
        )}
      </Field>
      <Field
        name="description"
        validate={[required("Please enter a description.")]}
      >
        {(field, props) => (
          <TextAreaInput
            {...props}
            value={field.value}
            error={field.error}
            label="Description"
            placeholder="I am unable to get this to work. Please help..."
            required
          />
        )}
      </Field>
      <Field
        name="attachment"
        type="File"
        validate={[
          maxSize(5 * 1024 * 1024, "Please upload a file smaller than 5MB.")
        ]}
      >
        {(field, props) => (
          <FileInput
            {...props}
            accept={"image/*,application/pdf,application/zip"}
            value={field.value}
            error={field.error}
            label="Upload attachment"
          />
        )}
      </Field>
      <button
        type="submit"
        class="rounded-lg bg-blue-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700 dark:focus:ring-blue-800 sm:w-auto"
        disabled={contactForm.submitting}
      >
        Submit
      </button>
      <a
        class="mx-2.5 rounded-lg bg-gray-700 px-5 py-2.5 text-center text-sm font-medium text-white hover:bg-gray-800 focus:outline-none focus:ring-4 focus:ring-gray-300 dark:bg-gray-600 dark:hover:bg-gray-700 dark:focus:ring-gray-800 sm:w-auto"
        disabled={contactForm.submitting}
        href="#"
        onClick={props.close}
      >
        Close
      </a>
      <Show when={contactForm.submitting}>
        <Spinner />
      </Show>
      <p>{status()}</p>
    </Form>
  );
};

export default ContactForm;
