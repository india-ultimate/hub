// The server's limits, checked before uploading: 10 MB a file, and a photo
// Cloudinary will take, which is 25 MP unless the server can shrink it.
export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
export const MAX_CLOUDINARY_PIXELS = 25_000_000;

// What the server shrinks. It can't shrink WEBP, HEIC or animated GIFs, and
// transparent images only to ~28 MP; a PNG may be transparent.
const SHRINKABLE_PIXELS = {
  "image/png": 28_000_000,
  "image/webp": MAX_CLOUDINARY_PIXELS,
  "image/heic": MAX_CLOUDINARY_PIXELS,
  "image/heif": MAX_CLOUDINARY_PIXELS,
  "image/gif": MAX_CLOUDINARY_PIXELS
};
const shrinkablePixels = type => SHRINKABLE_PIXELS[type] ?? 50_000_000;

// Read from the header as the browser loads it; 0 if it can't (e.g. HEIC on
// Chrome), leaving the server to decide.
const imagePixels = file => {
  const url = URL.createObjectURL(file);
  return new Promise(resolve => {
    const image = new Image();
    image.onload = () => resolve(image.naturalWidth * image.naturalHeight);
    image.onerror = () => resolve(0);
    image.src = url;
  }).finally(() => URL.revokeObjectURL(url));
};

// What's wrong with a file, or "" if it can go. maxPixels for uploads that go
// to Cloudinary as they are.
export const uploadError = async (file, maxPixels) => {
  if (!(file instanceof File)) return ""; // e.g. a saved logo's URL
  if (file.size > MAX_UPLOAD_BYTES) return "Files must be 10 MB or smaller.";
  const limit = maxPixels ?? shrinkablePixels(file.type);
  if (file.type.startsWith("image/") && (await imagePixels(file)) > limit) {
    return `This photo is too large; please use one under ${
      limit / 1_000_000
    } megapixels.`;
  }
  return "";
};

// For a form Field: the first problem with any of its files.
export const withinUploadLimits = async value => {
  for (const file of Array.isArray(value) ? value : [value]) {
    const error = await uploadError(file);
    if (error) return error;
  }
  return "";
};
