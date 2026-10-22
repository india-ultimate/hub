import { useParams } from "@solidjs/router";
import { Icon } from "solid-heroicons";
import { arrowUpTray, checkCircle } from "solid-heroicons/outline";
import {
  createResource,
  createSignal,
  For,
  Match,
  Show,
  Switch
} from "solid-js";

import { Spinner } from "../../icons";
import { getCookie } from "../../utils";
import Error from "../alerts/Error";

// The one-time link an AI agent hands out. The same address takes the
// files, from here or from curl.
const linkUrl = token => `/mcp/upload/${encodeURIComponent(token)}`;

const loadLink = async token => {
  try {
    const response = await fetch(linkUrl(token), {
      headers: { Accept: "application/json" },
      credentials: "same-origin"
    });
    const body = await response.json();
    return body.ok ? { link: body } : { problem: body.message };
  } catch {
    return { problem: "We couldn't load this link. Please try again." };
  }
};

const size = bytes =>
  bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${Number((bytes / 1024 / 1024).toFixed(1))} MB`;

const card =
  "mt-5 rounded-lg border border-gray-200 bg-white p-5 shadow-sm dark:border-gray-700 dark:bg-gray-800";

// The real input covers the box, so clicking and dropping both work.
const DropZone = props => {
  const [over, setOver] = createSignal(false);
  return (
    <div class="mb-4">
      <span
        id={`${props.field.name}-label`}
        class="mb-1.5 block font-medium text-gray-900 dark:text-white"
      >
        {props.field.label}
      </span>
      <div
        class="relative flex flex-col items-center gap-1 rounded-lg border-2 px-4 py-5 text-center transition-colors focus-within:ring-4 focus-within:ring-blue-300 dark:focus-within:ring-blue-800"
        classList={{
          "border-dashed border-gray-300 bg-gray-50 hover:border-blue-400 hover:bg-blue-50 dark:border-gray-600 dark:bg-gray-700 dark:hover:bg-gray-600":
            !props.file && !over(),
          "border-blue-500 bg-blue-50 dark:bg-gray-700": props.file || over()
        }}
      >
        <input
          type="file"
          name={props.field.name}
          accept={props.field.accept}
          required
          aria-labelledby={`${props.field.name}-label`}
          aria-describedby={`${props.field.name}-hint`}
          class="absolute inset-0 h-full w-full cursor-pointer opacity-0"
          onChange={e => props.onPick(e.currentTarget.files[0])}
          onDragEnter={() => setOver(true)}
          onDragLeave={() => setOver(false)}
          onDrop={() => setOver(false)}
        />
        <Icon
          path={props.file ? checkCircle : arrowUpTray}
          class="h-7 w-7 text-blue-700 dark:text-blue-400"
          aria-hidden="true"
        />
        <Show
          when={props.file}
          fallback={
            <span class="text-gray-900 dark:text-white">
              <span class="font-semibold text-blue-700 dark:text-blue-400">
                Choose a file
              </span>{" "}
              or drag it here
            </span>
          }
        >
          <span class="break-all font-semibold text-gray-900 dark:text-white">
            {props.file.name} · {size(props.file.size)}
          </span>
        </Show>
        <span
          id={`${props.field.name}-hint`}
          class="text-sm text-gray-500 dark:text-gray-400"
        >
          {props.field.hint}, up to {size(props.maxBytes)}
        </span>
      </div>
    </div>
  );
};

const UploadPage = () => {
  const params = useParams();
  const [loaded] = createResource(() => params.token, loadLink);
  const [files, setFiles] = createSignal({});
  const [sending, setSending] = createSignal(false);
  const [error, setError] = createSignal("");
  const [done, setDone] = createSignal("");

  // Back to this page through the login, as the link's owner.
  const [switchError, setSwitchError] = createSignal("");
  const switchAccount = async () => {
    setSwitchError("");
    const response = await fetch("/api/logout", {
      method: "POST",
      headers: { "X-CSRFToken": getCookie("csrftoken") },
      credentials: "same-origin"
    }).catch(() => null);
    if (!response?.ok) {
      setSwitchError("We couldn't sign you out. Please try again.");
      return;
    }
    window.location = `/login?redirect=${encodeURIComponent(
      `/upload/${params.token}`
    )}`;
  };

  const pick = (name, file) => {
    setError("");
    setFiles({ ...files(), [name]: file });
  };

  const send = async (event, link) => {
    event.preventDefault();
    const big = Object.values(files()).find(f => f && f.size > link.max_bytes);
    if (big) {
      setError(
        `${big.name} is over ${size(link.max_bytes)}. Pick a smaller file.`
      );
      return;
    }
    setError("");
    setSending(true);
    try {
      const response = await fetch(linkUrl(params.token), {
        method: "POST",
        body: new FormData(event.currentTarget),
        credentials: "same-origin"
      });
      const body = await response
        .json()
        .catch(() => ({ message: "Something went wrong. Try again." }));
      if (body.ok) setDone(body.message);
      else setError(body.message);
    } catch {
      setError("We couldn't reach Hub. Check your connection and try again.");
    }
    setSending(false);
  };

  return (
    <div class="mx-auto max-w-md py-6 sm:py-10">
      <Switch>
        <Match when={loaded.loading}>
          <Spinner />
        </Match>
        <Match when={loaded()?.problem}>
          <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
            Can't upload
          </h1>
          <div class="mt-5">
            <Error text={loaded().problem} />
          </div>
        </Match>
        <Match when={done()}>
          <div role="status" class={`${card} text-center`}>
            <Icon
              path={checkCircle}
              class="mx-auto h-12 w-12 text-green-600 dark:text-green-400"
              aria-hidden="true"
            />
            <p class="mt-3 text-lg font-semibold text-gray-900 dark:text-white">
              {done()}
            </p>
            <p class="mt-1 text-sm text-gray-600 dark:text-gray-300">
              You can close this tab and go back to your chat.
            </p>
          </div>
        </Match>
        <Match when={loaded()?.link && !loaded().link.mine}>
          <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
            This link is for someone else
          </h1>
          <p class="mt-2 text-gray-600 dark:text-gray-300">
            It belongs to <strong>{loaded().link.sign_in_as}</strong>. Sign in
            as them to upload.
          </p>
          <button
            type="button"
            onClick={switchAccount}
            class="mt-5 flex min-h-[44px] w-full items-center justify-center rounded-lg bg-blue-700 px-5 py-3 text-base font-semibold text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700"
          >
            Sign out and switch account
          </button>
          <Show when={switchError()}>
            <div class="mt-4">
              <Error text={switchError()} />
            </div>
          </Show>
        </Match>
        <Match when={loaded()?.link}>
          {link => (
            <>
              <h1 class="text-2xl font-bold text-gray-900 dark:text-white">
                Upload your {link().what}
              </h1>
              <p class="mt-1 text-sm text-gray-500 dark:text-gray-400">
                This link works once and only for the next 15 minutes.
              </p>
              <form class={card} onSubmit={e => send(e, link())}>
                <For each={link().fields}>
                  {field => (
                    <DropZone
                      field={field}
                      file={files()[field.name]}
                      maxBytes={link().max_bytes}
                      onPick={file => pick(field.name, file)}
                    />
                  )}
                </For>
                <button
                  type="submit"
                  disabled={sending()}
                  aria-busy={sending()}
                  class="flex min-h-[44px] w-full items-center justify-center gap-2 rounded-lg bg-blue-700 px-5 py-3 text-base font-semibold text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 disabled:cursor-progress disabled:bg-blue-400 dark:bg-blue-600 dark:hover:bg-blue-700"
                >
                  <Show when={sending()} fallback="Upload">
                    <Spinner height={20} width={20} noMargin />
                    Uploading…
                  </Show>
                </button>
                <Show when={error()}>
                  <div class="mt-4">
                    <Error text={error()} />
                  </div>
                </Show>
              </form>
            </>
          )}
        </Match>
      </Switch>
    </div>
  );
};

export default UploadPage;
