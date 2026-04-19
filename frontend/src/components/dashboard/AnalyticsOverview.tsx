import { useState, useEffect } from "react";
import Badge from "../ui/Badge";
import Button from "../ui/Button";

interface AnalyticsData {
  totalSamples: number;
  totalLabels: number;
  todaySamples: number;
  activeJobs: number;
  weeklyGrowth: number;
  topLabels: Array<{ label: string; count: number }>;
  recentActivity: Array<{ action: string; time: string; user: string }>;
}

export default function AnalyticsOverview() {
  const [analytics, setAnalytics] = useState<AnalyticsData>({
    totalSamples: 0,
    totalLabels: 0,
    todaySamples: 0,
    activeJobs: 0,
    weeklyGrowth: 0,
    topLabels: [],
    recentActivity: []
  });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // Simulate API call
    setTimeout(() => {
      setAnalytics({
        totalSamples: 1247,
        totalLabels: 15,
        todaySamples: 23,
        activeJobs: 2,
        weeklyGrowth: 12.5,
        topLabels: [
          { label: "walking", count: 342 },
          { label: "sitting", count: 289 },
          { label: "running", count: 198 },
          { label: "jumping", count: 156 }
        ],
        recentActivity: [
          { action: "Created 5 samples", time: "2 min ago", user: "user1" },
          { action: "Added label 'dancing'", time: "15 min ago", user: "admin" },
          { action: "Uploaded video batch", time: "1 hour ago", user: "user2" }
        ]
      });
      setLoading(false);
    }, 1000);
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="card animate-pulse">
            <div className="h-20 bg-gray-200 rounded"></div>
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Key Metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card text-center">
          <div className="text-3xl font-bold text-blue-600 mb-1">
            {analytics.totalSamples.toLocaleString()}
          </div>
          <div className="text-gray-600 text-sm">Total Samples</div>
          <div className="flex items-center justify-center mt-2">
            <Badge variant="success" size="sm">
              +{analytics.weeklyGrowth}% this week
            </Badge>
          </div>
        </div>

        <div className="card text-center">
          <div className="text-3xl font-bold text-green-600 mb-1">
            {analytics.totalLabels}
          </div>
          <div className="text-gray-600 text-sm">Active Labels</div>
          <div className="flex items-center justify-center mt-2">
            <Badge variant="info" size="sm">
              Ready for training
            </Badge>
          </div>
        </div>

        <div className="card text-center">
          <div className="text-3xl font-bold text-purple-600 mb-1">
            {analytics.todaySamples}
          </div>
          <div className="text-gray-600 text-sm">Today's Samples</div>
          <div className="flex items-center justify-center mt-2">
            <Badge variant="warning" size="sm">
              🔥 Keep going!
            </Badge>
          </div>
        </div>

        <div className="card text-center">
          <div className="text-3xl font-bold text-orange-600 mb-1">
            {analytics.activeJobs}
          </div>
          <div className="text-gray-600 text-sm">Active Jobs</div>
          <div className="flex items-center justify-center mt-2">
            <Badge variant={analytics.activeJobs > 0 ? "info" : "default"} size="sm">
              {analytics.activeJobs > 0 ? "Processing..." : "Idle"}
            </Badge>
          </div>
        </div>
      </div>

      {/* Charts and Details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Top Labels */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">📊 Top Labels</h3>
            <Button variant="ghost" size="sm">View All</Button>
          </div>
          
          <div className="space-y-3">
            {analytics.topLabels.map((item, index) => (
              <div key={item.label} className="flex items-center justify-between">
                <div className="flex items-center">
                  <div className="w-6 h-6 bg-blue-100 rounded-full flex items-center justify-center text-xs font-medium text-blue-600 mr-3">
                    {index + 1}
                  </div>
                  <span className="font-medium">{item.label}</span>
                </div>
                <div className="flex items-center">
                  <div className="w-24 h-2 bg-gray-200 rounded-full mr-3">
                    <div 
                      className="h-2 bg-blue-500 rounded-full"
                      style={{ width: `${(item.count / analytics.topLabels[0].count) * 100}%` }}
                    />
                  </div>
                  <span className="text-sm text-gray-600 w-8 text-right">{item.count}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Activity */}
        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">⚡ Recent Activity</h3>
            <Button variant="ghost" size="sm">View All</Button>
          </div>
          
          <div className="space-y-3">
            {analytics.recentActivity.map((activity, index) => (
              <div key={index} className="flex items-start gap-3">
                <div className="w-8 h-8 bg-green-100 rounded-full flex items-center justify-center text-green-600 text-sm font-medium">
                  {activity.user.charAt(0).toUpperCase()}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-gray-900">
                    {activity.action}
                  </div>
                  <div className="text-xs text-gray-500 flex items-center gap-2">
                    <span>{activity.user}</span>
                    <span>•</span>
                    <span>{activity.time}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">🚀 Quick Actions</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Button className="justify-start" variant="secondary">
            <span className="mr-2">📷</span>
            Start New Capture Session
          </Button>
          <Button className="justify-start" variant="secondary">
            <span className="mr-2">📊</span>
            Export Dataset
          </Button>
          <Button className="justify-start" variant="secondary">
            <span className="mr-2">🤖</span>
            Train Model
          </Button>
        </div>
      </div>
    </div>
  );
}