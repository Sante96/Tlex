import { api } from "./client";

export interface Profile {
  id: number;
  user_id: number;
  worker_id: number | null;
  name: string;
  avatar_url: string | null;
  is_kids: boolean;
  preferences: {
    default_audio?: string;
    default_subtitle?: string | null;
    auto_quality?: boolean;
  };
  has_worker: boolean;
}

export interface ProfileListResponse {
  profiles: Profile[];
  has_profiles: boolean;
}

export async function getProfiles(): Promise<ProfileListResponse> {
  const response = await api.get<ProfileListResponse>("/api/v1/profiles");
  return response.data;
}

export async function getProfile(profileId: number): Promise<Profile> {
  const response = await api.get<Profile>(`/api/v1/profiles/${profileId}`);
  return response.data;
}

export async function createProfile(data: {
  name: string;
  avatar_url?: string | null;
  is_kids?: boolean;
}): Promise<Profile> {
  const response = await api.post<Profile>("/api/v1/profiles", data);
  return response.data;
}

export async function updateProfile(
  profileId: number,
  data: {
    name?: string;
    avatar_url?: string | null;
    is_kids?: boolean;
    preferences?: Record<string, unknown>;
  },
): Promise<Profile> {
  const response = await api.put<Profile>(
    `/api/v1/profiles/${profileId}`,
    data,
  );
  return response.data;
}

export async function deleteProfile(profileId: number): Promise<void> {
  await api.delete(`/api/v1/profiles/${profileId}`);
}
