import { createMutation, useQueryClient } from "@tanstack/solid-query";
import clsx from "clsx";
import { createEffect, createSignal, Show } from "solid-js";

import { acceptSeriesInvitation, declineSeriesInvitation } from "../../queries";
import ErrorPopover from "../popover/ErrorPopover";
import SuccessPopover from "../popover/SuccessPopover";

const InvitationCard = props => {
  let successPopoverRef, errorPopoverRef;
  const queryClient = useQueryClient();

  const acceptInvitationMutation = createMutation({
    mutationFn: acceptSeriesInvitation,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["my-series-invitations", props.seriesSlug]
      });

      queryClient.invalidateQueries({
        queryKey: [
          "series-invitations-sent",
          props.seriesSlug,
          props.invitation?.team?.slug
        ]
      });
    }
  });

  const declineInvitationMutation = createMutation({
    mutationFn: declineSeriesInvitation,
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: ["my-series-invitations", props.seriesSlug]
      });

      queryClient.invalidateQueries({
        queryKey: [
          "series-invitations-sent",
          props.seriesSlug,
          props.invitation?.team?.slug
        ]
      });
    }
  });

  const [editStatus, setEditStatus] = createSignal("");

  createEffect(function onAcceptInvitationComplete() {
    if (acceptInvitationMutation.isSuccess) {
      setEditStatus("Accepted invitation");
      successPopoverRef.showPopover();
    }
    if (acceptInvitationMutation.isError) {
      setEditStatus(acceptInvitationMutation.error.message);
      errorPopoverRef.showPopover();
    }
  });

  createEffect(function onDeclineInvitationComplete() {
    if (declineInvitationMutation.isSuccess) {
      setEditStatus("Declined invitation");
      successPopoverRef.showPopover();
    }
    if (declineInvitationMutation.isError) {
      setEditStatus(declineInvitationMutation.error.message);
      errorPopoverRef.showPopover();
    }
  });

  return (
    <div class="rounded-lg border border-gray-300 bg-gray-100 p-4">
      <div class="space-x-2">
        <span>From:</span>
        <span class="font-semibold text-gray-600">
          {props.invitation?.team?.name}
        </span>
      </div>

      <div class="space-x-2">
        <span>Sent by:</span>
        <span class="font-semibold text-gray-600">
          {props.invitation?.from_user?.full_name}
        </span>
      </div>

      <div class="mt-4 flex w-full space-x-2">
        <button
          type="button"
          class={clsx(
            "mb-2 w-full rounded-lg bg-green-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-green-800 focus:outline-none focus:ring-4 focus:ring-green-300 disabled:bg-gray-300 dark:bg-green-600 dark:hover:bg-green-700 dark:focus:ring-green-800"
          )}
          disabled={acceptInvitationMutation.isLoading}
          onClick={() => {
            acceptInvitationMutation.mutate({
              invitation_id: props.invitation?.id
            });
          }}
        >
          <Show when={acceptInvitationMutation.isLoading} fallback={"Accept"}>
            Accepting...
          </Show>
        </button>
        <button
          type="button"
          class="mb-2 w-full rounded-lg bg-red-500 px-5 py-2.5 text-sm font-medium text-white hover:bg-red-700 focus:outline-none focus:ring-4 focus:ring-red-300 disabled:bg-gray-300 dark:bg-red-600 dark:hover:bg-red-700 dark:focus:ring-red-900"
          disabled={declineInvitationMutation.isLoading}
          onClick={() => {
            declineInvitationMutation.mutate({
              invitation_id: props.invitation?.id
            });
          }}
        >
          <Show when={declineInvitationMutation.isLoading} fallback={"Decline"}>
            Declining...
          </Show>
        </button>
      </div>

      <SuccessPopover ref={successPopoverRef}>
        <span class="font-medium">{editStatus()}</span>
      </SuccessPopover>

      <ErrorPopover ref={errorPopoverRef}>
        <span class="font-medium">{editStatus()}</span>
      </ErrorPopover>
    </div>
  );
};

export default InvitationCard;
