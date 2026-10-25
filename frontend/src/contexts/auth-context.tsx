"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
} from "react";
import type { ReactNode } from "react";
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

    try {
      // An expired access token is renewed by the client's 401 handler first
      const userData = await getCurrentUser();
      setUser(userData);
    } catch {
      endSession();
      setUser(null);
    } finally {
      setIsLoading(false);
    }
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
