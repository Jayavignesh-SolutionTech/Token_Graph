import type { Metadata } from "next";
import { Reshaper } from "@/components/Reshaper";

export const metadata: Metadata = {
  title: "Prompt reshaper · TokenGuard",
};

export default function ReshapePage() {
  return <Reshaper />;
}
