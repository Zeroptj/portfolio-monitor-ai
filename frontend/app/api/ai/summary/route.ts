import { NextRequest, NextResponse } from "next/server";
import { callPython } from "@/lib/python";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const refresh = searchParams.get("refresh") === "true";
  const data    = await callPython("ai-summary", { refresh: refresh || undefined });
  return NextResponse.json(data);
}
