import { type NextRequest } from "next/server";
import { proxyRequest } from "../../_lib/proxy";

export async function GET(req: NextRequest) {
  return proxyRequest(req, "workbench");
}

export async function POST(req: NextRequest) {
  return proxyRequest(req, "workbench");
}

export async function PUT(req: NextRequest) {
  return proxyRequest(req, "workbench");
}

export async function PATCH(req: NextRequest) {
  return proxyRequest(req, "workbench");
}

export async function DELETE(req: NextRequest) {
  return proxyRequest(req, "workbench");
}
