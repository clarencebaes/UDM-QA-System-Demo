import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import Navbar from "./components/Navbar";
import SiteFooter from "./components/SiteFooter";
import DashboardLayout from "./components/DashboardLayout";
import ConsentPage from "./pages/ConsentPage";
import EvaluationPage from "./pages/EvaluationPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import ThankYouPage from "./pages/ThankYouPage";
import Dashboard from "./pages/qa/Dashboard";
import FeedbackLogPage from "./pages/qa/FeedbackLogPage";
import AnalyticsPage from "./pages/qa/AnalyticsPage";
import AlertsPage from "./pages/qa/AlertsPage";
import SettingsPage from "./pages/qa/SettingsPage";
import HistoryPage from "./pages/qa/HistoryPage";
import ProfilePage from "./pages/qa/ProfilePage";

import InformationPage from "./pages/InformationPage";
import ConcernPage from "./pages/ConcernPage";
import RoleHome from "./pages/qa/RoleHome";
import RecordsPage from "./pages/qa/RecordsPage";
import ReportsPage from "./pages/qa/ReportsPage";
import BackupPage from "./pages/qa/BackupPage";
import NotificationCenter from "./components/NotificationCenter";
import { useLayoutEffect } from "react";

function AppShell() {
  const { pathname, key } = useLocation();
  useLayoutEffect(() => { window.scrollTo(0,0); }, [key]);
  const isQaArea = pathname.startsWith("/qa");
  const isEvaluation = pathname === "/evaluate";

  return (
    <div className="app-shell">
      <NotificationCenter />
      {!isQaArea && !isEvaluation && <Navbar />}
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/about" element={<InformationPage />} />
        <Route path="/faqs" element={<InformationPage />} />
        <Route path="/concern" element={<ConcernPage />} />
        <Route path="/consent" element={<ConsentPage />} />
        <Route path="/evaluate" element={<EvaluationPage />} />
        <Route path="/feedback" element={<Navigate to="/" replace />} />
        <Route path="/thanks" element={<ThankYouPage />} />
        <Route path="/qa/login" element={<LoginPage />} />
        <Route path="/qa" element={<DashboardLayout />}>
          <Route index element={<RoleHome />} />
          <Route path="dashboard" element={<Dashboard />} />
          <Route path="users" element={<RecordsPage key="users" kind="users" />} />
          <Route path="concerns" element={<RecordsPage key="concerns" kind="concerns" />} />
          <Route path="audit" element={<RecordsPage key="audit" kind="audit" />} />
          <Route path="reports" element={<ReportsPage />} />
          <Route path="backup" element={<BackupPage />} />
          <Route path="faqs" element={<InformationPage />} />
          <Route path="about" element={<InformationPage />} />
          <Route path="feedback-log" element={<FeedbackLogPage />} />
          <Route path="analytics" element={<AnalyticsPage />} />
          <Route path="alerts" element={<AlertsPage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="profile" element={<ProfilePage />} />
          <Route path="settings" element={<SettingsPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {(!isQaArea || pathname === "/qa/login") && <SiteFooter />}
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppShell />
    </BrowserRouter>
  );
}
