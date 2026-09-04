import { Navigate, Route, Routes } from "react-router-dom";
import AppLayout from "./components/AppLayout.jsx";
import { useAuth } from "./context/AuthContext.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import History from "./pages/History.jsx";
import Profile from "./pages/Profile.jsx";
import Pronunciation from "./pages/Pronunciation.jsx";
import Speaking from "./pages/Speaking.jsx";
import Writing from "./pages/Writing.jsx";

function AppShell() {
  const { loading } = useAuth();
  if (loading) return null;
  return <AppLayout />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<AppShell />}>
        <Route index element={<Dashboard />} />
        <Route path="speaking" element={<Speaking />} />
        <Route path="writing" element={<Writing />} />
        <Route path="pronunciation" element={<Pronunciation />} />
        <Route path="history" element={<History />} />
        <Route path="profile" element={<Profile />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
