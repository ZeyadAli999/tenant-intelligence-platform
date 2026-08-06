import { FeatureEmptyPage } from "@/components/feature-empty-page";
export default function Page() {
  return (
    <FeatureEmptyPage
      title="Permissions"
      description="Review tenant-scoped table, column, row-filter, and masking controls."
      capabilities={[
        "Table and column access policies",
        "Backend-enforced row filters",
        "Sensitive-column masking policies",
      ]}
      securityNote="Permission enforcement occurs at the deterministic SQL boundary and cannot be overridden by generated model text."
      preview="settings"
    />
  );
}
