import { api, endSession, sessionStarted } from "./client";

/** The tokens themselves come back as httpOnly cookies. */
export interface LoginResponse {
  expires_at: number;
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

export async function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<void> {
  // The backend ends every other session and sets fresh cookies for this one
  await api.put<LoginResponse>("/api/v1/auth/change-password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
  sessionStarted();
}

/** Revoke this device's refresh token; the backend also clears the httpOnly cookies,
 * which this code can't. Best effort. */
export async function logout(): Promise<void> {
  endSession();
  await api.post("/api/v1/auth/logout").catch(() => {});
}

export async function getRegistrationStatus(): Promise<{ enabled: boolean }> {
  const response = await api.get<{ enabled: boolean }>(
    "/api/v1/auth/registration-status",
  );
  return response.data;
}

export async function setRegistrationStatus(
  enabled: boolean,
): Promise<{ enabled: boolean }> {
  const response = await api.put<{ enabled: boolean }>(
    "/api/v1/auth/registration-status",
    { enabled },
  );
  return response.data;
}

export interface UserInfo {
  id: number;
  email: string;
  is_admin: boolean;
  profiles_count: number;
  profiles: { id: number; name: string }[];
}

export async function listUsers(): Promise<UserInfo[]> {
  const response = await api.get<UserInfo[]>("/api/v1/auth/users");
  return response.data;
}

export async function toggleUserAdmin(
  userId: number,
  isAdmin: boolean,
): Promise<void> {
  await api.patch(`/api/v1/auth/users/${userId}/admin`, { is_admin: isAdmin });
}

export async function deleteUser(userId: number): Promise<void> {
  await api.delete(`/api/v1/auth/users/${userId}`);
}

export interface DeviceCodeResponse {
  user_code: string;
  device_code: string;
  expires_in: number;
  interval: number;
}

/** "confirmed" comes with the session cookies. */
export interface DevicePollResponse {
  status: "pending" | "confirmed" | "expired";
}

export async function requestDeviceCode(): Promise<DeviceCodeResponse> {
  const response = await api.post<DeviceCodeResponse>("/api/v1/auth/device/request");
  return response.data;
}

export async function confirmDeviceCode(
  userCode: string,
  email: string,
  password: string,
): Promise<void> {
  await api.post("/api/v1/auth/device/confirm", {
    user_code: userCode,
    email,
    password,
  });
}

export async function pollDeviceCode(deviceCode: string): Promise<DevicePollResponse> {
  const response = await api.get<DevicePollResponse>("/api/v1/auth/device/poll", {
    params: { device_code: deviceCode },
  });
  return response.data;
}
