"use client";

import { useParams } from "next/navigation";
import { TicketDetailPage } from "@/features/workbench/pages/ticket-detail";

export default function ReviewDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  return <TicketDetailPage ticketId={taskId} backHref="/review" />;
}
