const IMAGE = /\.(jpe?g|png|gif|webp|bmp|tiff)$/i;
const PDF = /\.pdf$/i;

const path = url => {
  try {
    return new URL(url).pathname;
  } catch {
    return url;
  }
};

const HTTPS = /^https:/i;

export const isImage = url => HTTPS.test(url) && IMAGE.test(path(url));

export const isPdf = url => HTTPS.test(url) && PDF.test(path(url));

// Phones open PDFs in a new tab, where their own viewer does better than an iframe.
export const previewsInline = () =>
  window.matchMedia("(pointer: fine)").matches;

export const fileName = url => path(url).split("/").pop() || "attachment";

export const download = async url => {
  try {
    const response = await fetch(url);
    if (!response.ok) throw new Error("Failed to fetch file");
    const href = window.URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = href;
    link.download = fileName(url);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(href);
  } catch {
    window.open(url, "_blank", "noopener");
  }
};
