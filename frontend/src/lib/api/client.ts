import axios from "axios";
import Cookies from "js-cookie";

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Add auth token and locale to requests
api.interceptors.request.use((config) => {
  const token = Cookies.get("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  const locale = Cookies.get("TLEX_LOCALE") || "it";
  config.headers["Accept-Language"] = locale === "en" ? "en-US" : "it-IT";
  return config;
});
