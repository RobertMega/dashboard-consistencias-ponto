import { PrismaClient } from "@prisma/client";
import bcrypt from "bcryptjs";

const email = (process.env.INITIAL_ADMIN_EMAIL || "").trim().toLowerCase();
const password = process.env.INITIAL_ADMIN_PASSWORD || "";
if (!email || !password || password.length < 12) throw new Error("Set INITIAL_ADMIN_EMAIL and INITIAL_ADMIN_PASSWORD (minimum 12 characters).");
const prisma = new PrismaClient();
try {
  const passwordHash = await bcrypt.hash(password, 12);
  await prisma.user.upsert({ where: { email }, update: { passwordHash, role: "ADMIN" }, create: { email, passwordHash, role: "ADMIN" } });
  console.log(`ADMIN ready: ${email}`);
} finally { await prisma.$disconnect(); }
