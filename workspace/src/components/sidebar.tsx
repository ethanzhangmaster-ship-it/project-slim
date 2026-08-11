"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Network,
  Gamepad2,
  ListTodo,
  Activity,
  Brain,
  Lightbulb,
} from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/organization", label: "Organization", icon: Network },
  { href: "/games", label: "Games", icon: Gamepad2 },
  { href: "/tasks", label: "Tasks", icon: ListTodo },
  { href: "/activity", label: "Activity", icon: Activity },
  { href: "/decisions", label: "Decisions", icon: Lightbulb },
  { href: "/memory", label: "Memory", icon: Brain },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 h-screen w-64 border-r border-[#e5e5e5] bg-[#ffffff] flex flex-col z-50">
      {/* Logo */}
      <div className="p-6 border-b border-[#e5e5e5]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center">
            <span className="text-gray-900 font-bold text-sm">AI</span>
          </div>
          <div>
            <h1 className="text-sm font-semibold text-gray-900">Game Studio OS</h1>
            <p className="text-xs text-gray-500">Control Center</p>
          </div>
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 p-4 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-indigo-500/10 text-indigo-400"
                  : "text-gray-400 hover:text-gray-900 hover:bg-black/5"
              }`}
            >
              <Icon className="w-4 h-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-[#e5e5e5]">
        <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[#ffffff]">
          <div className="w-2 h-2 rounded-full bg-green-500 pulse-dot" />
          <span className="text-xs text-gray-400">System Online</span>
        </div>
      </div>
    </aside>
  );
}
