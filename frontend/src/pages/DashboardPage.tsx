import { useAuth } from "../hooks/useAuth";
import { Suspense } from "react";
import HeroSection from "../components/dashboard/HeroSection";
import CommunityStatsSection from "../components/dashboard/CommunityStatsSection";
import MyContributionSection from "../components/dashboard/MyContributionSection";
import QuickActionsSection from "../components/dashboard/QuickActionsSection";
import LandingHowItWorksSection from "../components/dashboard/LandingHowItWorksSection";

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
      {/* 1. Hero - Lời chào & động lực */}
      <HeroSection username={user?.username ?? null} />

      {/* 2. Quick Actions - Hành động nhanh */}
      <QuickActionsSection />

      {/* 3. My Contribution - Đóng góp cá nhân hoặc CTA tham gia */}
      <Suspense fallback={<div className="h-48 bg-slate-100 rounded-2xl animate-pulse" />}>
        <MyContributionSection username={user?.username ?? null} />
      </Suspense>

      {/* 4. Community Stats - Thống kê cộng đồng */}
      <Suspense fallback={<div className="h-40 bg-slate-100 rounded-2xl animate-pulse" />}>
        <CommunityStatsSection />
      </Suspense>

      {/* 5. How It Works - Giải thích quy trình */}
      <LandingHowItWorksSection />
    </div>
  );
}
