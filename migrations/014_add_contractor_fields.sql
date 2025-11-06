-- Migration: Add company_type and tax_number to contractors table
-- Purpose: Support contractor type classification and tax identification
-- Author: System
-- Date: 2025-11-06

-- Add company_type column to contractors table
ALTER TABLE IF EXISTS contractors
ADD COLUMN IF NOT EXISTS company_type VARCHAR(20) DEFAULT 'limited'
CHECK (company_type IN ('bireysel', 'limited'));

-- Add tax_number column to contractors table
ALTER TABLE IF EXISTS contractors
ADD COLUMN IF NOT EXISTS tax_number VARCHAR(20);

-- Create index on tax_number for faster lookups
CREATE INDEX IF NOT EXISTS idx_contractors_tax_number ON contractors(tax_number);

-- Create index on company_type for filtering
CREATE INDEX IF NOT EXISTS idx_contractors_company_type ON contractors(company_type);

-- Add comment to columns
COMMENT ON COLUMN contractors.company_type IS 'Company type: bireysel (individual) or limited (company)';
COMMENT ON COLUMN contractors.tax_number IS 'Tax identification number (10 digits for Turkish VKN)';
