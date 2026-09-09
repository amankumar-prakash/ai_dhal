import { createFileRoute, redirect } from "@tanstack/react-router";

export const Route = createFileRoute("/_authenticated/patches")({
  beforeLoad: () => {
    throw redirect({ to: "/tasks" });
  },
});
