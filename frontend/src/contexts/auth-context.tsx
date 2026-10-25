"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import type { ReactNode } from "react";
import { isAxiosError } from "axios";
import {
  login as apiLogin,
  logout as apiLogout,
  getCurrentUser,
  hasSession,
  sessionStarted,
  endSession,
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
  /** The TV's device login was confirmed: its poll answer set the session cookies */
  completeDeviceLogin: () => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const fetchUser = useCallback(async () => {
    if (!hasSession()) {
      setIsLoading(false);
      return;
    }

    // An expired access token is renewed by the client's 401 handler first. Anything but a
    // 401 (backend unreachable or starting: a 502) says nothing about the session: keep
    // it and the loader up, and ask again. Logging out there sent the TV back to device
    // login whenever the stack started.
    for (;;) {
      try {
        setUser(await getCurrentUser());
        break;
      } catch (e) {
        if (isAxiosError(e) && e.response?.status === 401) {
          endSession();
          setUser(null);
          break;
        }
        await new Promise((r) => setTimeout(r, 3000));
      }
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    fetchUser();
  }, [fetchUser]);

  const login = async (credentials: LoginCredentials) => {
    await apiLogin(credentials.email, credentials.password);
    sessionStarted();
    await fetchUser();
  };

  const completeDeviceLogin = useCallback(async () => {
    sessionStarted();
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
        completeDeviceLogin,
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
