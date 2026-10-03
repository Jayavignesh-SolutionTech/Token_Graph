import { Suspense } from "react";
import { UsageDashboard } from "@/components/UsageDashboard";

export default function Home() {
  // UsageDashboard reads ?sample=1, so it renders on the client inside a Suspense boundary.
  return (
    <Suspense>
      <UsageDashboard />
    </Suspense>
  );
}
