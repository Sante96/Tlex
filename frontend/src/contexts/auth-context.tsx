"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import type { ReactNode } from "react";
import Cookies from "js-cookie";
import {
  login as apiLogin,
  logout as apiLogout,
  getCurrentUser,
  saveTokens,
  clearTokens,
  type UserResponse,
} from "@/lib/api";

interface LoginCredentials {
  email: string;
  password: string;
}

interface AuthContextValue {
  user: UserResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  loginWithToken: (accessToken: string, refreshToken?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    const token = Cookies.get("token");
    if (!token) {
      setIsLoading(false);
      return;
    }

    try {
      // An expired access token is renewed by the client's 401 handler first
      const userData = await getCurrentUser();
      setUser(userData);
    } catch {
      clearTokens();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = async (credentials: LoginCredentials) => {
    const response = await apiLogin(credentials.email, credentials.password);
    saveTokens(response.access_token, response.refresh_token);
    await fetchUser();
  };

  const loginWithToken = useCallback(async (accessToken: string, refreshToken?: string) => {
    saveTokens(accessToken, refreshToken);
    await fetchUser();
  }, [fetchUser]);

  const logout = () => {
    void apiLogout();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        loginWithToken,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
