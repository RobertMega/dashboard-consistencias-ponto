CREATE INDEX "DailyRecord_reportRunId_severity_idx" ON "DailyRecord"("reportRunId", "severity");
CREATE INDEX "DailyRecord_reportRunId_status_idx" ON "DailyRecord"("reportRunId", "status");
CREATE INDEX "DailyRecord_reportRunId_collaborator_date_idx" ON "DailyRecord"("reportRunId", "collaborator", "date");
