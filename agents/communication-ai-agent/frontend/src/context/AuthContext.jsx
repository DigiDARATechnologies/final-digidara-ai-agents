import { createContext, useContext, useEffect, useState } from "react";
import client from "../api/client";

const AuthContext = createContext(null);
const GUEST_USER = {
  name: "Guest Student",
  email: "guest@student.local",
  password: "guest-student-password",
};

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const enterAsGuest = async () => {
      try {
        const token = localStorage.getItem("cc_token");
        if (token) {
          try {
            const res = await client.get("/profile");
            setUser(res.data);
            if (res.data?.email === GUEST_USER.email) {
              localStorage.setItem("cc_auth_mode", "guest");
            }
            return;
          } catch {
            localStorage.removeItem("cc_token");
          }
        }

        const res = await enterGuestSession();
        const session = normalizeSession(res.data);
        localStorage.setItem("cc_token", session.token);
        if (session.user?.email === GUEST_USER.email) {
          localStorage.setItem("cc_auth_mode", "guest");
        }
        setUser(session.user);
      } finally {
        setLoading(false);
      }
    };

    enterAsGuest().catch(() => {
      localStorage.removeItem("cc_token");
      setLoading(false);
    });
  }, []);

  const refreshUser = async () => {
    const res = await client.get("/profile");
    setUser(res.data);
  };

  return (
    <AuthContext.Provider value={{ user, loading, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}

async function enterGuestSession() {
  try {
    return await client.post("/auth/guest");
  } catch (guestError) {
    if (guestError.response?.status && guestError.response.status !== 404) {
      throw guestError;
    }
  }

  try {
    return await client.post("/auth/login", {
      email: GUEST_USER.email,
      password: GUEST_USER.password,
    });
  } catch {
    return client.post("/auth/register", GUEST_USER);
  }
}

function normalizeSession(payload) {
  return {
    token: payload.token || payload.accessToken || payload.data?.token || payload.data?.accessToken,
    user: payload.user || payload.data?.user,
  };
}
