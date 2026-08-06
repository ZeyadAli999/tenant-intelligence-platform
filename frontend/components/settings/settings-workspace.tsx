"use client";

import { Building2, Info, Palette, ShieldCheck, User } from "lucide-react";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/ui/page";
import { LoadingState } from "@/components/ui/states";
import { fetchCurrentIdentity } from "@/lib/settings-api";
import type { CurrentUser } from "@/lib/contracts";
import { AccountSettingsSection } from "./account-settings-section";
import { AppearanceSettingsSection } from "./appearance-settings-section";
import { ProductInformationSection } from "./product-information-section";
import { SecuritySettingsSection } from "./security-settings-section";
import { TenantSettingsSection } from "./tenant-settings-section";

type TabId = "account" | "tenant" | "appearance" | "security" | "system";

const tabs: Array<{ id: TabId; label: string; icon: typeof User }> = [
  { id: "account", label: "Account Profile", icon: User },
  { id: "tenant", label: "Tenant Profile", icon: Building2 },
  { id: "appearance", label: "Appearance", icon: Palette },
  { id: "security", label: "Session & Security", icon: ShieldCheck },
  { id: "system", label: "System Info", icon: Info },
];

export function SettingsWorkspace({
  onLogout,
}: {
  onLogout?: () => Promise<void>;
} = {}) {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<TabId>("account");

  useEffect(() => {
    let mounted = true;
    fetchCurrentIdentity()
      .then((data) => {
        if (mounted) {
          setUser(data);
          setLoading(false);
        }
      })
      .catch(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return <LoadingState label="Loading settings workspace..." />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Settings"
        description="Manage interface preferences, account details, tenant profile, and system status."
      />

      <div className="border-b border-[var(--border)]">
        <nav
          role="tablist"
          aria-label="Settings categories"
          className="-mb-px flex space-x-2 overflow-x-auto pb-0.5 sm:space-x-4"
        >
          {tabs.map(({ id, label, icon: Icon }) => {
            const active = activeTab === id;
            return (
              <button
                key={id}
                role="tab"
                id={`tab-${id}`}
                aria-selected={active}
                aria-controls={`panel-${id}`}
                onClick={() => setActiveTab(id)}
                className={`flex shrink-0 items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-semibold transition-colors ${
                  active
                    ? "border-[var(--primary)] text-[var(--primary)]"
                    : "border-transparent text-[var(--text-secondary)] hover:border-[var(--border-strong)] hover:text-[var(--text)]"
                }`}
              >
                <Icon className="h-4 w-4" aria-hidden />
                {label}
              </button>
            );
          })}
        </nav>
      </div>

      <div className="mt-6">
        <div
          role="tabpanel"
          id={`panel-${activeTab}`}
          aria-labelledby={`tab-${activeTab}`}
          tabIndex={0}
          className="outline-none"
        >
          {activeTab === "account" && <AccountSettingsSection user={user} />}
          {activeTab === "tenant" && <TenantSettingsSection user={user} />}
          {activeTab === "appearance" && <AppearanceSettingsSection />}
          {activeTab === "security" && (
            <SecuritySettingsSection onLogout={onLogout} />
          )}
          {activeTab === "system" && <ProductInformationSection />}
        </div>
      </div>
    </div>
  );
}
