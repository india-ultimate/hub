import { createEffect, Show } from "solid-js";

import {
  dangerButton,
  focusRing,
  primaryButton,
  secondaryButton
} from "../committees";
import Modal from "./Modal";

// Asks before something that can't be taken back. `request` is null, or
// { title, message, confirm, danger?, disabled?, error?, retry?, run }; `close` clears it.
const ConfirmDialog = props => {
  let dialog;

  createEffect(() => {
    if (props.request() && !dialog.open) dialog.showModal();
    if (!props.request() && dialog.open) dialog.close();
  });

  return (
    <Modal
      ref={el => {
        dialog = el;
        el.addEventListener("close", props.close);
      }}
      title={
        <span class="font-semibold text-gray-900 dark:text-white">
          {props.request()?.title}
        </span>
      }
      close={props.close}
    >
      <Show when={props.request()}>
        {request => (
          <div class="space-y-4">
            <p class="text-sm">{request().message}</p>
            <Show when={request().error}>
              <p role="alert" class="text-sm text-red-700 dark:text-red-400">
                {request().error}{" "}
                <button
                  type="button"
                  class={`underline ${focusRing}`}
                  onClick={request().retry}
                >
                  Try again
                </button>
              </p>
            </Show>
            <div class="flex flex-wrap justify-end gap-2">
              <button
                type="button"
                class={secondaryButton}
                onClick={props.close}
              >
                Cancel
              </button>
              <button
                type="button"
                class={request().danger ? dangerButton : primaryButton}
                disabled={request().disabled}
                onClick={() => {
                  request().run();
                  props.close();
                }}
              >
                {request().confirm}
              </button>
            </div>
          </div>
        )}
      </Show>
    </Modal>
  );
};

export default ConfirmDialog;
