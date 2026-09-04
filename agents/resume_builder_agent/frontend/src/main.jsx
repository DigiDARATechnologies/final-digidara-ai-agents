import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";
import HomePage from "./pages/HomePage.jsx";
import ResumeBuilderPage from "./pages/ResumeBuilderPage.jsx";
import { RouterProvider, useLocation } from "./router.jsx";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <RouterProvider>
      <AppRouter />
    </RouterProvider>
  </React.StrictMode>,
);

function AppRouter() {
  const { pathname } = useLocation();
  let page = <HomePage />;
  if (pathname === "/resumes" || pathname === "/resumes/") {
    page = <DashboardPage />;
  } else if (/^\/resume\/[^/]+\/?$/.test(pathname)) {
    page = <ResumeBuilderPage />;
  }
  return <App>{page}</App>;
}
