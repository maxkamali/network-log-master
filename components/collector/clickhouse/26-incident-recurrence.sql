ALTER TABLE observability.incident_updates
    ADD COLUMN IF NOT EXISTS `recurrence_count` UInt32 DEFAULT 0
    AFTER `occurrence_count`;
