"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type OrganizationNode } from "@/lib/api";
import { Network, ChevronRight } from "lucide-react";

const statusColors: Record<string, string> = {
  running: "bg-green-500",
  idle: "bg-gray-400",
  offline: "bg-red-500",
  degraded: "bg-yellow-500",
};

export default function OrganizationPage() {
  const [org, setOrg] = useState<OrganizationNode | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getOrganization().then(setOrg).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-gray-500">Loading organization...</div>
      </div>
    );
  }

  if (!org) return null;

  return (
    <div className="p-8 max-w-5xl">
      <div className="mb-8">
        <div className="flex items-center gap-2 mb-1">
          <Network className="w-5 h-5 text-indigo-400" />
          <h1 className="text-2xl font-bold text-gray-900">Organization</h1>
        </div>
        <p className="text-sm text-gray-500">AI 公司组织架构</p>
      </div>

      <div className="bg-[#ffffff] border border-[#e5e5e5] rounded-xl p-6">
        <OrgTree node={org} depth={0} />
      </div>
    </div>
  );
}

function OrgTree({ node, depth }: { node: OrganizationNode; depth: number }) {
  const isAgent = node.type === "agent";
  const isDepartment = node.type === "department";

  return (
    <div style={{ marginLeft: depth > 0 ? 24 : 0 }}>
      <div className={`flex items-center gap-3 py-2 ${isAgent ? "hover:bg-black/5 rounded-lg px-2 -mx-2 transition-colors" : ""}`}>
        {depth > 0 && <div className="w-4 h-px bg-[#e5e5e5]" />}

        {isAgent && node.status && (
          <div className={`w-2 h-2 rounded-full ${statusColors[node.status] || "bg-gray-400"}`} />
        )}

        {isDepartment && <ChevronRight className="w-3 h-3 text-gray-600 rotate-90" />}

        {isAgent ? (
          <Link href={`/agent/${node.agent_id}`} className="flex-1 flex items-center gap-2">
            <span className="text-sm text-gray-700 hover:text-gray-900">{node.name}</span>
          </Link>
        ) : (
          <span className={`text-sm ${node.type === "company" ? "font-bold text-gray-900" : "font-medium text-gray-400"}`}>
            {node.name}
          </span>
        )}

        {isAgent && node.status && (
          <span className="text-xs text-gray-600 capitalize">{node.status}</span>
        )}
      </div>

      {node.children.length > 0 && (
        <div className="border-l border-[#e5e5e5] ml-1">
          {node.children.map((child) => (
            <OrgTree key={child.id} node={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}
