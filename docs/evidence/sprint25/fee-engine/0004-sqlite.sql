BEGIN;
--
-- Create model FeeScheduleVersion
--
CREATE TABLE "valuation_feescheduleversion" ("id" char(32) NOT NULL PRIMARY KEY, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "scope" varchar(30) NOT NULL, "marketplace" varchar(20) NOT NULL, "currency" varchar(3) NOT NULL, "number" integer unsigned NOT NULL CHECK ("number" >= 0), "label" varchar(120) NOT NULL, "source_url" varchar(200) NOT NULL, "source_note" text NOT NULL, "fingerprint" varchar(64) NOT NULL, "engine_version" varchar(30) NOT NULL, "entered_by_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "previous_id" char(32) NULL UNIQUE REFERENCES "valuation_feescheduleversion" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "fee_version_number" UNIQUE ("scope", "marketplace", "currency", "number"));
--
-- Create model FeePlanPeriod
--
CREATE TABLE "valuation_feeplanperiod" ("id" char(32) NOT NULL PRIMARY KEY, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "plan" varchar(24) NOT NULL, "effective_from" date NOT NULL, "effective_to" date NULL, "per_order_fee" decimal NOT NULL, "international_pct" decimal NOT NULL, "gst_treatment" varchar(24) NOT NULL, "source_note" text NOT NULL, "version_id" char(32) NOT NULL REFERENCES "valuation_feescheduleversion" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "fee_period_start" UNIQUE ("version_id", "effective_from"), CONSTRAINT "fee_period_valid_dates" CHECK (("effective_to" IS NULL OR "effective_to" > ("effective_from"))), CONSTRAINT "fee_period_nonnegative" CHECK (("per_order_fee" >= '0' AND "international_pct" >= '0')));
--
-- Create model FeeOrderSnapshot
--
CREATE TABLE "valuation_feeordersnapshot" ("id" char(32) NOT NULL PRIMARY KEY, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "channel" varchar(24) NOT NULL, "order_identity" varchar(180) NOT NULL, "sale_date" date NOT NULL, "inputs" text NOT NULL CHECK ((JSON_VALID("inputs") OR "inputs" IS NULL)), "result" text NOT NULL CHECK ((JSON_VALID("result") OR "result" IS NULL)), "fingerprint" varchar(64) NOT NULL, "rule_version" varchar(30) NOT NULL, "period_id" char(32) NULL REFERENCES "valuation_feeplanperiod" ("id") DEFERRABLE INITIALLY DEFERRED, "version_id" char(32) NULL REFERENCES "valuation_feescheduleversion" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "fee_order_once" UNIQUE ("channel", "order_identity"));
--
-- Create model FeeTierRate
--
CREATE TABLE "valuation_feetierrate" ("id" char(32) NOT NULL PRIMARY KEY, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "tier" varchar(20) NOT NULL, "fvf_pct" decimal NOT NULL, "threshold" decimal NOT NULL, "above_pct" decimal NOT NULL, "mapping" text NOT NULL CHECK ((JSON_VALID("mapping") OR "mapping" IS NULL)), "period_id" char(32) NOT NULL REFERENCES "valuation_feeplanperiod" ("id") DEFERRABLE INITIALLY DEFERRED, CONSTRAINT "fee_period_tier" UNIQUE ("period_id", "tier"), CONSTRAINT "fee_tier_valid_rates" CHECK (("fvf_pct" >= '0' AND "above_pct" >= '0' AND "threshold" > '0')));
--
-- Create model SaleFeeSnapshot
--
CREATE TABLE "valuation_salefeesnapshot" ("id" char(32) NOT NULL PRIMARY KEY, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "provenance" varchar(40) NOT NULL, "basis" varchar(40) NOT NULL, "label" varchar(160) NOT NULL, "inputs" text NOT NULL CHECK ((JSON_VALID("inputs") OR "inputs" IS NULL)), "components" text NOT NULL CHECK ((JSON_VALID("components") OR "components" IS NULL)), "result" text NOT NULL CHECK ((JSON_VALID("result") OR "result" IS NULL)), "order_id" char(32) NULL REFERENCES "valuation_feeordersnapshot" ("id") DEFERRABLE INITIALLY DEFERRED, "sale_id" char(32) NOT NULL UNIQUE REFERENCES "sales_salerecord" ("id") DEFERRABLE INITIALLY DEFERRED, "version_id" char(32) NULL REFERENCES "valuation_feescheduleversion" ("id") DEFERRABLE INITIALLY DEFERRED);
--
-- Create model FeeAdjustment
--
CREATE TABLE "valuation_feeadjustment" ("id" char(32) NOT NULL PRIMARY KEY, "created_at" datetime NOT NULL, "updated_at" datetime NOT NULL, "amount" decimal NOT NULL, "reason" text NOT NULL, "provenance" varchar(30) NOT NULL, "components" text NOT NULL CHECK ((JSON_VALID("components") OR "components" IS NULL)), "actor_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED, "snapshot_id" char(32) NOT NULL REFERENCES "valuation_salefeesnapshot" ("id") DEFERRABLE INITIALLY DEFERRED);
CREATE UNIQUE INDEX "fee_calendar_one_root" ON "valuation_feescheduleversion" ("scope", "marketplace", "currency") WHERE "previous_id" IS NULL;
CREATE INDEX "valuation_feescheduleversion_entered_by_id_25e27c5b" ON "valuation_feescheduleversion" ("entered_by_id");
CREATE INDEX "valuation_feeplanperiod_version_id_daa202bf" ON "valuation_feeplanperiod" ("version_id");
CREATE INDEX "valuation_feeordersnapshot_period_id_eb452b15" ON "valuation_feeordersnapshot" ("period_id");
CREATE INDEX "valuation_feeordersnapshot_version_id_a75776e8" ON "valuation_feeordersnapshot" ("version_id");
CREATE INDEX "valuation_feetierrate_period_id_fc5f77bd" ON "valuation_feetierrate" ("period_id");
CREATE INDEX "valuation_salefeesnapshot_order_id_e92c3ce0" ON "valuation_salefeesnapshot" ("order_id");
CREATE INDEX "valuation_salefeesnapshot_version_id_ee6ac4c9" ON "valuation_salefeesnapshot" ("version_id");
CREATE INDEX "valuation_feeadjustment_actor_id_58bc1279" ON "valuation_feeadjustment" ("actor_id");
CREATE INDEX "valuation_feeadjustment_snapshot_id_0ee45c7b" ON "valuation_feeadjustment" ("snapshot_id");
COMMIT;
