import React, { useEffect, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import SetupScreen from "./components/SetupScreen";
import InterviewScreen from "./components/InterviewScreen";
import ResultScreen from "./components/ResultScreen";
import Dashboard from "./components/Dashboard";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import History from "./components/History";
import Profile from "./components/Profile";
import Sidebar from "./components/ui/Sidebar";
import TopHeader from "./components/ui/TopHeader";
import { getActiveInterview, getProfile, startInterview } from "./api";
import { AVATAR_COLORS, getInitials } from "./utils/profile";
import { reportClientError, reportClientWarning } from "./utils/clientLogger";
import "./App.css";

// Demo student id -- wire this to your LMS auth/session once integrated.
const STUDENT_ID = 1;
const SIDEBAR_PREFERENCE_KEY = "mock-interview:sidebar-collapsed";
const SCREEN_ROUTES = {
  dashboard: "/dashboard",
  setup: "/new-interview",
  history: "/history",
  analytics: "/analytics",
  profile: "/profile",
  interview: "/interview",
  result: "/result",
};

function getInitialSidebarCollapsed() {
  try {
    return globalThis.localStorage?.getItem(SIDEBAR_PREFERENCE_KEY) === "true";
  } catch (error) {
    reportClientWarning("sidebar_preference_read_failed", error);
    return false;
  }
}

const PAGE_META = {
  dashboard: {
    title: "Dashboard",
    subtitle: "Track your interview practice, scores, and focus areas.",
  },
  setup: {
    title: "New Interview",
    subtitle: "Configure a voice-based mock interview that matches your goal.",
  },
  interview: {
    title: "Live Interview",
    subtitle: "Stay focused. The AI will guide the conversation.",
  },
  result: {
    title: "Interview Report",
    subtitle: "Review your score breakdown and feedback.",
  },
  history: {
    title: "Interview History",
    subtitle: "Revisit previous attempts and answer transcripts.",
  },
  analytics: {
    title: "AI Usage Analytics",
    subtitle: "Monitor provider-reported tokens and estimated API cost.",
  },
  profile: {
    title: "Profile",
    subtitle: "Manage your student details and interview summary.",
  },
};

function screenFromPath(pathname) {
  if (pathname === "/new-interview") return "setup";
  if (pathname.startsWith("/history")) return "history";
  if (pathname === "/analytics") return "analytics";
  if (pathname === "/profile") return "profile";
  if (pathname === "/interview") return "interview";
  if (pathname === "/result") return "result";
  return "dashboard";
}

/** Root shell with URL-backed routes plus transient live-interview state. */
export default function App() {
  const location = useLocation();
  const navigate = useNavigate();
  const screen = screenFromPath(location.pathname);
  const [interviewId, setInterviewId] = useState(null);
  const [firstQuestion, setFirstQuestion] = useState(null);
  const [interviewDifficulty, setInterviewDifficulty] = useState("intermediate");
  const [totalQuestions, setTotalQuestions] = useState(5);
  const [initialQuestionOrder, setInitialQuestionOrder] = useState(1);
  const [initialRealQuestionIndex, setInitialRealQuestionIndex] = useState(1);
  const [initialIsFrequentlyAsked, setInitialIsFrequentlyAsked] = useState(false);
  const [result, setResult] = useState(null);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(getInitialSidebarCollapsed);
  const [studentProfile, setStudentProfile] = useState(null);
  const [startupWarning, setStartupWarning] = useState(null);

  useEffect(() => {
    try {
      globalThis.localStorage?.setItem(
        SIDEBAR_PREFERENCE_KEY,
        String(isSidebarCollapsed)
      );
    } catch (error) {
      reportClientWarning("sidebar_preference_write_failed", error);
    }
  }, [isSidebarCollapsed]);

  useEffect(() => {
    let isMounted = true;

    getProfile(STUDENT_ID)
      .then((profile) => {
        if (isMounted) setStudentProfile(profile);
      })
      .catch((error) => {
        reportClientError("student_profile_bootstrap_failed", error, {
          student_id: STUDENT_ID,
        });
      });

    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    let isMounted = true;
    getActiveInterview(STUDENT_ID)
      .then((session) => {
        if (!isMounted) return;
        setStartupWarning(null);
        if (!session.active) return;
        setInterviewId(session.interview_id);
        setFirstQuestion(session.question);
        setInterviewDifficulty(session.difficulty || "intermediate");
        setTotalQuestions(session.total_questions || 5);
        setInitialQuestionOrder(session.question_order || 1);
        setInitialRealQuestionIndex(session.real_question_index || 1);
        setInitialIsFrequentlyAsked(Boolean(session.is_frequently_asked));
        navigate(SCREEN_ROUTES.interview, { replace: true });
      })
      .catch((error) => {
        reportClientError("active_interview_restore_failed", error, {
          student_id: STUDENT_ID,
        });
        if (isMounted) {
          setStartupWarning(
            "We could not check for an interview already in progress. You can retry by refreshing this page."
          );
        }
      });
    return () => {
      isMounted = false;
    };
  }, [navigate]);

  const isInterviewActive = screen === "interview";
  const pageMeta = PAGE_META[screen] || PAGE_META.dashboard;
  const personalizedStudentName = studentProfile?.name?.trim() || "";
  const studentName = personalizedStudentName || "Student";
  const studentInitials = getInitials(studentProfile?.name, studentProfile?.email);
  const studentAvatarColor = studentProfile?.avatar_color || AVATAR_COLORS[0];
  const studentAvatarUrl = studentProfile?.avatar_url || null;

  function handleNavigate(nextScreen) {
    if (isInterviewActive) return;
    navigate(SCREEN_ROUTES[nextScreen] || SCREEN_ROUTES.dashboard);
  }

  function handleSidebarToggle() {
    if (globalThis.matchMedia?.("(max-width: 900px)")?.matches) {
      setIsSidebarOpen(true);
      return;
    }
    setIsSidebarCollapsed((collapsed) => !collapsed);
  }

  function handleStarted(id, question, session = {}) {
    setInterviewId(id);
    setFirstQuestion(question);
    setInterviewDifficulty(session.difficulty || "intermediate");
    setTotalQuestions(session.totalQuestions || 5);
    setInitialQuestionOrder(session.questionOrder || 1);
    setInitialRealQuestionIndex(session.realQuestionIndex || 1);
    setInitialIsFrequentlyAsked(Boolean(session.isFrequentlyAsked));
    navigate(SCREEN_ROUTES.interview);
  }

  function handleFinished(finalResult) {
    setResult(finalResult);
    navigate(SCREEN_ROUTES.result, { replace: true });
  }

  function handleExited() {
    setInterviewId(null);
    setFirstQuestion(null);
    setInterviewDifficulty("intermediate");
    setTotalQuestions(5);
    setInitialQuestionOrder(1);
    setInitialRealQuestionIndex(1);
    setInitialIsFrequentlyAsked(false);
    navigate(SCREEN_ROUTES.dashboard, { replace: true });
  }

  function handleStartAgain() {
    setInterviewId(null);
    setFirstQuestion(null);
    setInterviewDifficulty("intermediate");
    setTotalQuestions(5);
    setInitialQuestionOrder(1);
    setInitialRealQuestionIndex(1);
    setInitialIsFrequentlyAsked(false);
    setResult(null);
    navigate(SCREEN_ROUTES.setup);
  }

  async function handlePracticeWeakTopics(weakSubjects) {
    if (!result?.role_name || !weakSubjects?.length) return;
    try {
      const session = await startInterview({
        student_id: STUDENT_ID,
        interview_mode: "weak_topic_practice",
        round_type: "technical",
        role_name: result.role_name,
        resolved_subjects: weakSubjects,
        subject: weakSubjects[0],
        difficulty: interviewDifficulty,
        num_questions: 5,
      });
      if (session.interview_id) {
        handleStarted(session.interview_id, session.question, {
          totalQuestions: session.total_questions,
          difficulty: session.difficulty || interviewDifficulty,
          questionOrder: session.question_order || 1,
          realQuestionIndex: session.real_question_index || 1,
          isFrequentlyAsked: Boolean(session.is_frequently_asked),
        });
      }
    } catch (error) {
      reportClientError("weak_topic_practice_start_failed", error, { student_id: STUDENT_ID });
    }
  }

  if (isInterviewActive && interviewId) {
    return (
      <main className="interview-only-shell">
        <InterviewScreen
          interviewId={interviewId}
          firstQuestion={firstQuestion}
          difficulty={interviewDifficulty}
          totalQuestions={totalQuestions}
          initialQuestionOrder={initialQuestionOrder}
          initialRealQuestionIndex={initialRealQuestionIndex}
          initialIsFrequentlyAsked={initialIsFrequentlyAsked}
          onFinished={handleFinished}
          onExited={handleExited}
        />
      </main>
    );
  }

  return (
    <div className={`app-shell ${isSidebarCollapsed ? "sidebar-is-collapsed" : ""}`}>
      <Sidebar
        screen={screen}
        isOpen={isSidebarOpen}
        isCollapsed={isSidebarCollapsed}
        isInterviewActive={isInterviewActive}
        onNavigate={handleNavigate}
        onClose={() => setIsSidebarOpen(false)}
        studentName={studentName}
        studentInitials={studentInitials}
        avatarColor={studentAvatarColor}
        avatarUrl={studentAvatarUrl}
      />

      <div className="app-content">
        <TopHeader
          title={pageMeta.title}
          subtitle={pageMeta.subtitle}
          onSidebarToggle={handleSidebarToggle}
          isSidebarCollapsed={isSidebarCollapsed}
          onNavigate={handleNavigate}
          isInterviewActive={isInterviewActive}
          studentName={studentName}
          studentInitials={studentInitials}
          avatarColor={studentAvatarColor}
          avatarUrl={studentAvatarUrl}
        />

        <main className="app-main">
          {startupWarning && (
            <p className="error-text app-startup-warning" role="alert">
              {startupWarning}
            </p>
          )}
          <Routes location={location}>
            <Route
              path="/dashboard"
              element={(
                <Dashboard
                  studentId={STUDENT_ID}
                  studentName={personalizedStudentName}
                  onStartInterview={() => navigate(SCREEN_ROUTES.setup)}
                  onViewInterview={(id) => navigate(`/history/${id}`)}
                />
              )}
            />
            <Route
              path="/new-interview"
              element={<SetupScreen studentId={STUDENT_ID} onStarted={handleStarted} />}
            />
            <Route path="/history" element={<History studentId={STUDENT_ID} />} />
            <Route path="/history/:interviewId" element={<History studentId={STUDENT_ID} />} />
            <Route path="/analytics" element={<AnalyticsDashboard studentId={STUDENT_ID} />} />
            <Route
              path="/profile"
              element={<Profile studentId={STUDENT_ID} onProfileUpdate={setStudentProfile} />}
            />
            <Route
              path="/result"
              element={result ? (
                <ResultScreen
                  result={result}
                  onDone={() => navigate(SCREEN_ROUTES.dashboard)}
                  onStartAgain={handleStartAgain}
                  onPracticeWeakTopics={handlePracticeWeakTopics}
                />
              ) : <Navigate to="/history" replace />}
            />
            <Route path="/interview" element={<Navigate to="/dashboard" replace />} />
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}
