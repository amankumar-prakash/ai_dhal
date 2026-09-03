import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/_authenticated/attack-chain")({
  beforeLoad: () => {
    throw redirect({ to: "/tasks" });
  },
});
