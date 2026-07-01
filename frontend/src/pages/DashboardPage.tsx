import { useAuth } from "../hooks/useAuth";
import { Suspense } from "react";
import HeroSection from "../components/dashboard/HeroSection";
import CommunityStatsSection from "../components/dashboard/CommunityStatsSection";
import MyContributionSection from "../components/dashboard/MyContributionSection";
import QuickActionsSection from "../components/dashboard/QuickActionsSection";

export default function DashboardPage() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="h-48 bg-gradient-to-r from-slate-200 to-slate-100 rounded-2xl animate-pulse" />
        <div className="h-64 bg-slate-100 rounded-2xl animate-pulse" />
        <div className="h-40 bg-slate-100 rounded-2xl animate-pulse" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Hero Section - Motivational */}
      <HeroSection username={user?.username ?? null} />

      {/* My Contribution - User's Personal Focus or Join CTA */}
      <Suspense fallback={<div className="h-48 bg-slate-100 rounded-2xl animate-pulse" />}>
        <MyContributionSection username={user?.username ?? null} />
      </Suspense>

      {/* Community Stats - Broader Context */}
      <Suspense fallback={<div className="h-40 bg-slate-100 rounded-2xl animate-pulse" />}>
        <CommunityStatsSection />
      </Suspense>

      {/* Quick Actions - Clear CTAs */}
      <QuickActionsSection />
    </div>
  );
}
