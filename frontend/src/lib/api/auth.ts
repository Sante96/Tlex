import { api } from "./client";

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface UserResponse {
  id: number;
  email: string;
  is_admin: boolean;
}

export async function login(
  email: string,
  password: string,
): Promise<LoginResponse> {
  const formData = new URLSearchParams();
  formData.append("username", email);
  formData.append("password", password);

  const response = await api.post<LoginResponse>(
    "/api/v1/auth/login",
    formData,
    {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    },
  );
  return response.data;
}

export async function register(
  email: string,
  password: string,
): Promise<UserResponse> {
  const response = await api.post<UserResponse>("/api/v1/auth/register", {
    email,
    password,
  });
  return response.data;
}

export async function getCurrentUser(): Promise<UserResponse> {
  const response = await api.get<UserResponse>("/api/v1/auth/me");
  return response.data;
}
