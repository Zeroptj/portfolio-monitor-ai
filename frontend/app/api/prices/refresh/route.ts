import { NextResponse } from "next/server"
import { callPython } from "@/lib/python"

export async function POST() {
  const data = await callPython("refresh")
  return NextResponse.json(data)
}
