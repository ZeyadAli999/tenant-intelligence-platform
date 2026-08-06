import { FeatureEmptyPage } from "@/components/feature-empty-page";
export default function Page() {
  return (
    <FeatureEmptyPage
      title="Settings"
      description="Configure workspace preferences and administrative settings."
      capabilities={[
        "Workspace identity preferences",
        "Tenant administration entry points",
        "Theme and interface preferences",
      ]}
      securityNote="Administrative operations continue to require the authenticated tenant-administrator context."
      preview="settings"
    />
  );
}
