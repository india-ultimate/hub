import { A, useParams } from "@solidjs/router";
import { createSignal } from "solid-js";

const ReceiptPage = () => {
  const params = useParams();
  const [height, setHeight] = createSignal(1200);
  const fit = event => {
    const doc = event.currentTarget.contentDocument;
    // body, not documentElement: the latter is clamped to the iframe's
    // current height, so it only ever grows and leaves grey space below.
    if (doc) setHeight(doc.body.scrollHeight + 8);
  };
  return (
    <div class="mx-auto max-w-4xl">
      <div class="mb-4 flex flex-wrap items-center justify-between gap-3">
        <A
          href="/dashboard"
          class="inline-flex min-h-[44px] items-center text-sm font-medium text-blue-700 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-600 dark:text-blue-400"
        >
          ← Back to dashboard
        </A>
        <a
          href={`/api/receipts/${params.id}/pdf`}
          class="inline-flex min-h-[44px] items-center rounded-lg bg-blue-700 px-5 text-sm font-medium text-white hover:bg-blue-800 focus:outline-none focus:ring-4 focus:ring-blue-300 dark:bg-blue-600 dark:hover:bg-blue-700"
        >
          Download PDF
        </a>
      </div>
      <iframe
        title="Receipt"
        src={`/api/receipts/${params.id}/page`}
        onLoad={fit}
        class="w-full border-0"
        style={{ height: `${height()}px` }}
      />
    </div>
  );
};

export default ReceiptPage;
