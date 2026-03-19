import { NavLink, Outlet } from "react-router-dom";
import { BarChart3, Globe, Layers, FileText, Activity, MessageSquare } from "lucide-react";
import { cn } from "../lib/utils";

const NAV = [
  { to: "/",             icon: Activity,       label: "Overview"      },
  { to: "/insights",     icon: BarChart3,      label: "Insights"      },
  { to: "/impact-delta", icon: Layers,         label: "Impact Delta"  },
  { to: "/sources",      icon: Globe,          label: "Sources"       },
  { to: "/reports",      icon: FileText,       label: "Report Builder"},
  { to: "/chat",         icon: MessageSquare,  label: "AI Assistant"  },
];

export default function Layout() {
  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col">
        {/* Logo */}
        <div className="px-6 py-5 border-b border-slate-800">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center text-white font-bold text-sm">
              D
            </div>
            <div>
              <p className="font-semibold text-sm text-white">Social Analyzer</p>
              <p className="text-xs text-slate-400">Danone ESG Intelligence</p>
            </div>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                  isActive
                    ? "bg-blue-600 text-white"
                    : "text-slate-400 hover:text-white hover:bg-slate-800"
                )
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-800">
          <p className="text-xs text-slate-500">Powered by Databricks</p>
          <p className="text-xs text-slate-600">danonedemo_catalog.marketing</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto bg-slate-950">
        <Outlet />
      </main>
    </div>
  );
}
