CREATE TYPE "Role" AS ENUM ('ADMIN', 'VIEWER');
CREATE TYPE "ReportStatus" AS ENUM ('SUCCESS', 'PROCESSING', 'FAILED');

CREATE TABLE "User" (
    "id" TEXT NOT NULL,
    "email" TEXT NOT NULL,
    "name" TEXT,
    "passwordHash" TEXT NOT NULL,
    "role" "Role" NOT NULL DEFAULT 'VIEWER',
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    CONSTRAINT "User_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "ReportRun" (
    "id" TEXT NOT NULL,
    "periodStart" TIMESTAMP(3),
    "periodEnd" TIMESTAMP(3),
    "sourceFilename" TEXT NOT NULL,
    "processedAt" TIMESTAMP(3),
    "status" "ReportStatus" NOT NULL,
    "totalRecords" INTEGER NOT NULL DEFAULT 0,
    "errorMessage" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "isCurrent" BOOLEAN NOT NULL DEFAULT false,
    "excelFilename" TEXT,
    "excelData" BYTEA,
    CONSTRAINT "ReportRun_pkey" PRIMARY KEY ("id")
);

CREATE TABLE "DailyRecord" (
    "id" TEXT NOT NULL,
    "reportRunId" TEXT NOT NULL,
    "collaborator" TEXT NOT NULL,
    "date" TIMESTAMP(3) NOT NULL,
    "plannedHours" INTEGER,
    "expectedMarkings" INTEGER,
    "markings" JSONB NOT NULL,
    "markingsCount" INTEGER NOT NULL,
    "totalHours" INTEGER,
    "balance" INTEGER,
    "reason" TEXT,
    "occurrenceType" TEXT NOT NULL,
    "severity" TEXT NOT NULL,
    "status" TEXT NOT NULL,
    "weekday" TEXT,
    "calculatedBalance" INTEGER,
    "originalBalance" INTEGER,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "DailyRecord_pkey" PRIMARY KEY ("id")
);

CREATE UNIQUE INDEX "User_email_key" ON "User"("email");
CREATE INDEX "ReportRun_status_isCurrent_idx" ON "ReportRun"("status", "isCurrent");
CREATE INDEX "ReportRun_periodStart_periodEnd_idx" ON "ReportRun"("periodStart", "periodEnd");
CREATE UNIQUE INDEX "DailyRecord_reportRunId_collaborator_date_key" ON "DailyRecord"("reportRunId", "collaborator", "date");
CREATE INDEX "DailyRecord_reportRunId_date_idx" ON "DailyRecord"("reportRunId", "date");
CREATE INDEX "DailyRecord_reportRunId_collaborator_idx" ON "DailyRecord"("reportRunId", "collaborator");
CREATE INDEX "DailyRecord_reportRunId_occurrenceType_idx" ON "DailyRecord"("reportRunId", "occurrenceType");

ALTER TABLE "DailyRecord" ADD CONSTRAINT "DailyRecord_reportRunId_fkey" FOREIGN KEY ("reportRunId") REFERENCES "ReportRun"("id") ON DELETE CASCADE ON UPDATE CASCADE;
