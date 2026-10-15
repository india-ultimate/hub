import { A, useBeforeLeave, useNavigate, useParams } from "@solidjs/router";
import {
  createMutation,
  createQuery,
  useQueryClient
} from "@tanstack/solid-query";
import { createSignal, For, onCleanup, onMount, Show } from "solid-js";

import { errorField, hasUnsupportedFormatting } from "../../announcements";
import { announcementTypeLabels } from "../../colors";
import {
  card,
  createSaved,
  Field,
  focusRing,
  input,
  primaryButton,
  secondaryButton
} from "../../committees";
import {
  deleteAnnouncement,
  fetchAnnouncement,
  saveAnnouncement
} from "../../queries";
import { useStore } from "../../store";
import ConfirmDialog from "../ConfirmDialog";
import TiptapEditor from "../TiptapEditor";
import EditorToolbar from "./EditorToolbar";
import EmailPanel from "./EmailPanel";

const Checkbox = props => (
  <label class="flex min-h-[44px] items-center gap-2 text-sm text-gray-900 dark:text-white">
    <input
      type="checkbox"
      checked={props.checked}
      onChange={e => props.onChange(e.currentTarget.checked)}
      class="h-5 w-5 rounded border-gray-300 text-blue-700 focus:ring-blue-500"
    />
    {props.label}
  </label>
);

// Shown instead of the editor for a post it would quietly reformat.
const UnsupportedNotice = props => (
  <div
    role="alert"
    class="mb-6 rounded-lg border border-yellow-300 bg-yellow-50 p-4 text-sm text-yellow-900"
  >
    <p>
      This post has formatting the Hub editor can't keep (videos, custom
      styles). Edit it in the admin to keep it.
    </p>
    <div class="mt-3 flex flex-wrap gap-2">
      <Show when={props.adminHref}>
        <a href={props.adminHref} class={secondaryButton}>
          Edit in admin
        </a>
      </Show>
      <button type="button" class={secondaryButton} onClick={props.onContinue}>
        Continue here
      </button>
    </div>
  </div>
);

// The form, started from `announcement` (none for a new post).
const EditorForm = props => {
  const post = props.announcement ?? {};
  const [store] = useStore();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [saved, flash] = createSaved();
  const [editor, setEditor] = createSignal();
  const [form, setForm] = createSignal({
    title: post.title ?? "",
    type: post.type ?? "competitions",
    is_members_only: post.is_members_only ?? false,
    allow_comments: post.allow_comments ?? true,
    action_text: post.action_text ?? "",
    action_url: post.action_url ?? ""
  });
  // The title as saved, for the dialogs that name the post.
  const [savedTitle, setSavedTitle] = createSignal(post.title);
  const [published, setPublished] = createSignal(post.is_published ?? false);
  const [dirty, setDirty] = createSignal(false);
  const [contentError, setContentError] = createSignal("");
  // What the dialog is asking: see ConfirmDialog.
  const [request, setRequest] = createSignal(null);

  const edit = key => value => {
    setForm({ ...form(), [key]: value });
    setDirty(true);
  };
  const text = key => e => edit(key)(e.currentTarget.value);

  const refreshLists = slug => {
    queryClient.invalidateQueries({ queryKey: ["announcements"] });
    queryClient.invalidateQueries({ queryKey: ["announcement", slug] });
  };

  const save = createMutation({
    mutationFn: saveAnnouncement,
    onSuccess: (saved, { is_published }) => {
      setDirty(false);
      setPublished(saved.is_published);
      setSavedTitle(saved.title);
      refreshLists(saved.slug);
      queryClient.setQueryData(["announcement", saved.slug], saved);
      if (is_published && !post.is_published) {
        navigate(`/announcement/${saved.slug}`);
      } else if (!post.slug) {
        navigate(`/announcement/${saved.slug}/edit`, { replace: true });
      } else {
        flash();
      }
    }
  });
  const remove = createMutation({
    mutationFn: deleteAnnouncement,
    onSuccess: () => {
      setDirty(false);
      refreshLists(post.slug);
      navigate("/announcements");
    }
  });

  const submit = is_published => {
    if (save.isLoading) return;
    if (editor().isEmpty) return setContentError("Write something first.");
    setContentError("");
    save.mutate({
      slug: post.slug,
      ...form(),
      content: editor().getHTML(),
      is_published
    });
  };
  const publish = () =>
    setRequest({
      title: "Publish announcement",
      message: "Everyone who can read it will see it right away.",
      confirm: "Publish",
      run: () => submit(true)
    });
  const askDelete = () =>
    setRequest({
      title: "Delete announcement",
      message: `Delete "${savedTitle()}"? Its comments and reactions go with it.`,
      confirm: "Delete announcement",
      danger: true,
      run: () => remove.mutate(post.slug)
    });

  useBeforeLeave(e => {
    if (!dirty() || e.defaultPrevented) return;
    e.preventDefault();
    setRequest({
      title: "Leave without saving?",
      message: "Your changes to this announcement haven't been saved.",
      confirm: "Leave",
      danger: true,
      run: () => e.retry(true)
    });
  });
  const warn = e => dirty() && e.preventDefault();
  onMount(() => window.addEventListener("beforeunload", warn));
  onCleanup(() => window.removeEventListener("beforeunload", warn));

  const serverError = () => save.error ?? remove.error;
  const errors = () => ({
    [errorField(serverError()?.message ?? "")]: serverError()?.message
  });

  return (
    <>
      <form
        class="space-y-6"
        onSubmit={e => {
          e.preventDefault();
          submit(published());
        }}
      >
        <Field id="announcement-title" label="Title" error={errors().title}>
          <input
            id="announcement-title"
            required
            maxlength="200"
            value={form().title}
            onInput={text("title")}
            class={input}
          />
        </Field>

        <div>
          <p
            id="content-label"
            class="mb-1 block text-sm font-medium text-gray-900 dark:text-white"
          >
            Content
          </p>
          <EditorToolbar editor={editor} />
          <TiptapEditor
            labelledBy="content-label"
            content={post.content ?? ""}
            onReady={setEditor}
            onChange={() => setDirty(true)}
          />
          <Show when={contentError() || errors().content}>
            <p role="alert" class="mt-1 text-sm text-red-700 dark:text-red-400">
              {contentError() || errors().content}
            </p>
          </Show>
        </div>

        <div class={`${card} grid gap-x-4 gap-y-2 sm:grid-cols-2`}>
          <Field id="announcement-type" label="Type" error={errors().type}>
            <select
              id="announcement-type"
              value={form().type}
              onChange={text("type")}
              class={input}
            >
              <For each={Object.entries(announcementTypeLabels)}>
                {([value, label]) => <option value={value}>{label}</option>}
              </For>
            </select>
          </Field>
          <div>
            <Checkbox
              label="Members only"
              checked={form().is_members_only}
              onChange={edit("is_members_only")}
            />
            <Checkbox
              label="Allow comments"
              checked={form().allow_comments}
              onChange={edit("allow_comments")}
            />
          </div>
          <Field
            id="action-text"
            label="Button label (optional)"
            error={errors().action_text}
          >
            <input
              id="action-text"
              maxlength="100"
              value={form().action_text}
              onInput={text("action_text")}
              class={input}
            />
          </Field>
          <Field
            id="action-url"
            label="Button link (optional)"
            error={errors().action_url}
          >
            <input
              id="action-url"
              type="url"
              placeholder="https://"
              value={form().action_url}
              onInput={text("action_url")}
              class={input}
            />
          </Field>
        </div>
      </form>

      <Show when={post.slug}>
        <EmailPanel
          slug={post.slug}
          title={savedTitle()}
          published={published()}
          isStaff={store.data?.is_staff}
        />
        <button
          type="button"
          onClick={askDelete}
          class={`min-h-[44px] rounded px-2 text-sm font-medium text-red-700 underline dark:text-red-400 ${focusRing}`}
        >
          Delete announcement
        </button>
      </Show>

      <div class="sticky bottom-0 z-20 -mx-4 flex flex-wrap items-center justify-end gap-2 border-t border-gray-200 bg-white py-3 pl-4 pr-24 dark:border-gray-700 dark:bg-gray-900">
        <p
          role="status"
          class="mr-auto text-sm font-medium text-green-700 dark:text-green-400"
        >
          <Show when={saved()}>Saved</Show>
        </p>
        <Show when={errors().form}>
          <p role="alert" class="text-sm text-red-700 dark:text-red-400">
            {errors().form}
          </p>
        </Show>
        <Show
          when={published()}
          fallback={
            <>
              <button
                type="button"
                class={secondaryButton}
                disabled={save.isLoading}
                onClick={() => submit(false)}
              >
                Save draft
              </button>
              <button
                type="button"
                class={primaryButton}
                disabled={save.isLoading}
                onClick={publish}
              >
                Publish
              </button>
            </>
          }
        >
          <button
            type="button"
            class={secondaryButton}
            disabled={save.isLoading}
            onClick={() => submit(false)}
          >
            Unpublish
          </button>
          <button
            type="button"
            class={primaryButton}
            disabled={save.isLoading}
            onClick={() => submit(true)}
          >
            Save changes
          </button>
        </Show>
      </div>

      <ConfirmDialog request={request} close={() => setRequest(null)} />
    </>
  );
};

// /announcements/new and /announcement/:slug/edit.
const AnnouncementEditor = () => {
  const params = useParams();
  const [store] = useStore();
  const [continued, setContinued] = createSignal(false);
  const query = createQuery(
    () => ["announcement", params.slug],
    () => fetchAnnouncement(params.slug),
    {
      get enabled() {
        return Boolean(params.slug);
      }
    }
  );

  const unsupported = () =>
    hasUnsupportedFormatting(query.data?.content ?? "") && !continued();

  return (
    <div class="mx-auto max-w-3xl space-y-6">
      <A
        href={params.slug ? `/announcement/${params.slug}` : "/announcements"}
        class="text-blue-600 hover:text-blue-700"
      >
        ← Back
      </A>
      <h1 class="text-4xl font-bold text-blue-700 dark:text-white">
        {params.slug ? "Edit announcement" : "New announcement"}
      </h1>
      <Show when={query.error}>
        <p role="alert" class="text-red-700 dark:text-red-400">
          {query.error.message}
        </p>
      </Show>
      <Show when={!params.slug || query.data}>
        <Show
          when={!params.slug || query.data.can_manage}
          fallback={<p>Sorry, you can't edit this announcement.</p>}
        >
          <Show
            when={!unsupported()}
            fallback={
              <UnsupportedNotice
                adminHref={
                  store.data?.is_staff &&
                  `/admin/server/announcement/${query.data.id}/change/`
                }
                onContinue={() => setContinued(true)}
              />
            }
          >
            <EditorForm announcement={query.data} />
          </Show>
        </Show>
      </Show>
    </div>
  );
};

export default AnnouncementEditor;
