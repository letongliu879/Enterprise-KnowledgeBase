"use client";

import { useParams } from "next/navigation";
import { TicketDetailPage } from "@/features/workbench/pages/ticket-detail";

export default function WorkbenchDetailPage() {
  const { ticketId } = useParams<{ ticketId: string }>();
  return <TicketDetailPage ticketId={ticketId} backHref="/review" />;
}
