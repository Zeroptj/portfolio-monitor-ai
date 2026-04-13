import { NextRequest, NextResponse } from "next/server";
import { callPython } from "@/lib/python";

export async function POST(req: NextRequest) {
  const body     = await req.json();
  const question = body.question || "";
  const data     = await callPython("recommend", { question });
  return NextResponse.json(data);
}
