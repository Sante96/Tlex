import { api } from "./client";

/** An image from the PC; resolves to its "local:<name>" path. Rejects with the backend's
 * reason in error.response.data.detail (errorText shows it). */
export async function uploadImage(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  // The client's default JSON type would turn the form into JSON; this one lets the
  // browser write the multipart boundary
  const response = await api.post<{ path: string }>("/api/v1/images", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return response.data.path;
}

/** A pasted link: the backend downloads and keeps the picture */
export async function imageFromUrl(url: string): Promise<string> {
  const response = await api.post<{ path: string }>("/api/v1/images/from-url", { url });
  return response.data.path;
}
