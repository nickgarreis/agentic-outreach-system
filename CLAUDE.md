# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# IMPORTANT
- Always prioritize writing clean, simple, and modular code.
- Use simple & easy-to-understand language. Write in short sentences.
- DO NOT BE LAZY! Always read files IN

# COMMENTS
- Write lots of comments in your code. explain exactly what you are doing in your comments.
- but be strategic, do not explain obvious syntax - instead explain your thought process at the time of writing the
- NEVER delete explanatory comments from the code you're editing (unless they are wrong/obsolete)
- focus on explaining the non-obvious stuff in the comments, the nuances / details
- DO NOT delete comments
currently in our code. If the
comment is obsolete, or wrong, then update it - but NEVER mindlessly remove comments without

# HEADER COMMENTS
- EVERY file HAS TO start with 4 lines of comments!
1. exact file location in codebase
2. clear description of what this file does
3. clear description of WHY this file exists
4. RELEVANT FILES: comma-separated list of 2-4 most relevant files
- NEVER delete these "header comments" from the files you're

# ACTIVE CONTRIBUTORS
- **User (Human)**: Works in Cursor IDE, directs the project, makes high-level decisions, has the best taste & judgement.
- **Cursor Agent**: AI copilot activated by User, lives in the Cursor IDE, medium level of autonomy, can edit multiple files at once, can run terminal commands, can access the whole codebase; the User uses it to vibe-code the app.
- **Claude Code**: Terminal-based AI agent with high autonomy, can edit multiple files simultaneously, understands entire codebase automatically, runs tests/Git operations, handles large-scale refactoring and complex debugging independently

## Architecture Overview

This is an agentic-outreach system built with Python FastAPI backend and and supabase as database:

### Perspectives System
Each perspective represents a major feature:
- **AutopilotAgent**: AI Agent that executes jobs
- **SupabaseTables**: Store all information about clients, campaigns, metrics and so on 
- **SupabaseTrigger**: Activate AutopilotAgent based on database events. Often include edge functions to provide context to the AutopilotAgent
- **Tools**: Tools the AutopilotAgent can use to execute jobs
- **RenderWorker**: Where the AutopilotAgent lives. Has a job_scheduler functionality

### Access to MCPs
- Supabase MCP: READ-ONLY access to Supabase tables, triggers and edge functions. NEVER use MCP for database modifications.
- Exa Search MCP: Search the internet, github and other developer orientated sources to get the latest information about coding/developement practices

## Technology Stack

### Backend
- **FastAPI** with Python 3.12
- **Supabase** (PostgreSQL) for database
- **OpenRouter** for AI model access (Claude, GPT, DeepSeek, Grok)
- **Render** for background jobs

## Development Guidelines

### Anti-Complexity Philosophy
- BE VERY SUSPICIOUS OF EVERY COMPLICATION - simple = good, complex = bad
- Do exactly what's asked, nothing more
- Execute precisely what the user asks for, without additional features
- Constantly verify you're not adding anything beyond explicit instructions

### Communication Style
- Use simple & easy-to-understand language. write in short sentences
- Be CLEAR and STRAIGHT TO THE POINT
- EXPLAIN EVERYTHING CLEARLY & COMPLETELY
- Address ALL of user's points and questions clearly and completely.

## Key Implementation Notes

- **Branch Strategy**: `main` = production, `dev` = staging
- **AI Models**: All accessed via OpenRouter API
- **Background Jobs**: Render

## Testing & Quality

- Backend testing files in `/src/testing/`
- No formal test framework - manual testing approach

# IMPORTANT
- never EVER push to github unless the User explicitly tells you to.

## Supabase Development

### Branch Configuration
- **Dev Branch Project ID**: `tqjyyedrazaimtujdjrw` 
- **Main Branch Project ID**: `dmfniygxoaijrnjornaq` (DO NOT USE)
- ALWAYS use the dev branch project ID for all Supabase operations

### Database Management

#### Reading Database:
- Use Supabase MCP (READ-ONLY) to inspect current database state

#### Making Database Changes:
1. **Inspect current state** using Supabase MCP read operations
2. **Create migration file** in `/supabase/migrations/` with timestamp prefix (e.g., `20250128_add_user_profiles.sql`)
3. **Write SQL changes** in the migration file
4. **Apply migration** will be applied when pushing all changes to the remote dev branch in github
5. **Test thoroughly** before committing

#### Migration Guidelines:
- All database changes MUST go through migration files
- NEVER modify database directly without creating a migration
- Migration files should be:
  - Idempotent (safe to run multiple times)
  - Include both schema changes and data migrations if needed
  - Well-commented explaining the changes

IMPORTANT: The Supabase MCP is READ-ONLY for safety. All modifications must go through proper migration files.

## PostgreSQL Enum Migration Best Practices

### Converting Text Columns to Enum - The Complete Reset Approach
After extensive testing, the most reliable way to convert text columns to enum is the complete reset approach:

#### Working Migration Template (Tested and Proven)
```sql
-- Step 1: Clean up any partial migration state
DO $$
DECLARE
    constraint_name text;
BEGIN
    -- Drop all dependent objects
    DROP VIEW IF EXISTS dependent_view_name CASCADE;
    DROP TRIGGER IF EXISTS related_trigger ON table_name;
    DROP FUNCTION IF EXISTS related_function() CASCADE;
    
    -- Check if column is already enum and convert back to text
    IF EXISTS (
        SELECT 1 FROM pg_attribute a
        JOIN pg_class c ON a.attrelid = c.oid
        JOIN pg_type t ON a.atttypid = t.oid
        WHERE c.relname = 'my_table'
        AND a.attname = 'my_column'
        AND t.typname = 'my_enum'
    ) THEN
        ALTER TABLE my_table ALTER COLUMN my_column DROP DEFAULT;
        ALTER TABLE my_table ALTER COLUMN my_column TYPE text USING my_column::text;
    END IF;
    
    -- Drop CHECK constraints on the column
    FOR constraint_name IN 
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = ANY(con.conkey)
        WHERE rel.relname = 'my_table' AND att.attname = 'my_column' AND con.contype = 'c'
    LOOP
        EXECUTE format('ALTER TABLE my_table DROP CONSTRAINT IF EXISTS %I', constraint_name);
    END LOOP;
    
    -- Drop enum type and casts
    DROP CAST IF EXISTS (varchar AS my_enum);
    DROP CAST IF EXISTS (text AS my_enum);
    DROP TYPE IF EXISTS my_enum CASCADE;
END$$;

-- Step 2: Update invalid values BEFORE creating enum (CRITICAL ORDER!)
UPDATE my_table 
SET my_column = 'default_value' 
WHERE my_column NOT IN ('value1', 'value2', 'value3');

-- Step 3: Create the enum type
CREATE TYPE my_enum AS ENUM ('value1', 'value2', 'value3');

-- Step 4: Drop indexes on the column (prevents conversion issues)
DO $$
DECLARE
    idx_name text;
BEGIN
    FOR idx_name IN 
        SELECT indexname FROM pg_indexes 
        WHERE tablename = 'my_table' AND indexdef LIKE '%my_column%'
    LOOP
        EXECUTE format('DROP INDEX IF EXISTS %I', idx_name);
    END LOOP;
END$$;

-- Step 5: Convert the column
ALTER TABLE my_table 
    ALTER COLUMN my_column DROP DEFAULT,
    ALTER COLUMN my_column TYPE my_enum USING my_column::text::my_enum,
    ALTER COLUMN my_column SET DEFAULT 'default_value'::my_enum;

-- Step 6: Recreate indexes, views, etc.
CREATE INDEX IF NOT EXISTS idx_my_table_my_column ON my_table(my_column);
-- Recreate any dropped views here
```

### Critical Lessons Learned

#### 1. Order Matters - Update BEFORE Creating Enum
**NEVER** create the enum type before updating invalid values. This causes:
```
ERROR: operator does not exist: enum_type = text
```
Always update values while the column is still text type.

#### 2. Complete Reset is More Reliable Than Partial Fixes
Trying to handle partial states with complex logic often fails. Instead:
- Drop everything related to the enum
- Start fresh with a clean state
- This approach works in all scenarios

#### 3. Double Casting is Essential
Always use `::text::enum_type` not just `::enum_type`:
```sql
-- WRONG - can cause errors
USING my_column::my_enum

-- CORRECT - always works
USING my_column::text::my_enum
```

#### 4. Avoid Complex CASE Statements in USING Clause
CASE statements in the USING clause can cause comparison errors:
```sql
-- WRONG - causes "operator does not exist" errors
USING CASE 
    WHEN status = 'draft' THEN 'draft'::my_enum
    ...
END;

-- CORRECT - simple double cast
USING status::text::my_enum
```

#### 5. Handle All Dependencies
Before altering a column:
- Drop views that use the column
- Drop triggers on the table
- Drop CHECK constraints on the column
- Drop indexes on the column
- Drop functions that reference the column

### Common Error Solutions
- **"operator does not exist: enum_type = text"**: 
  - Happens when enum exists but column is text
  - Update values BEFORE creating enum
  - Use complete reset approach
  
- **"default for column cannot be cast automatically"**: 
  - Always drop default before type conversion
  - Re-add default after conversion
  
- **"cannot alter type of a column used by a view"**: 
  - Drop all dependent views first
  - Query pg_depend to find dependencies
  
- **"invalid input value for enum"**: 
  - Update invalid values before conversion
  - Use a safe default value

### Testing Your Migration
Always test by running the migration:
1. On a fresh database
2. On a database with partial migration state
3. Multiple times in a row (idempotency test)

### Handling View Dependencies
When altering a column that's used by a view, PostgreSQL will error with "cannot alter type of a column used by a view or rule". You must:

1. **Drop the view first**: `DROP VIEW IF EXISTS view_name;`
2. **Make your column changes**
3. **Recreate the view** with the same definition
4. **Re-grant permissions** if needed

Example:
```sql
-- Drop dependent views
DROP VIEW IF EXISTS my_view;

-- Alter the column
ALTER TABLE my_table ALTER COLUMN my_column TYPE new_type;

-- Recreate the view
CREATE OR REPLACE VIEW my_view AS
  SELECT * FROM my_table;
  
-- Re-grant permissions
GRANT SELECT ON my_view TO authenticated;
```

To check for view dependencies before altering columns:
```sql
SELECT distinct dependee.relname, dependee.relkind 
FROM pg_depend 
JOIN pg_rewrite ON pg_depend.objid = pg_rewrite.oid 
JOIN pg_class as dependee ON pg_rewrite.ev_class = dependee.oid 
JOIN pg_class as dependent ON pg_depend.refobjid = dependent.oid 
JOIN pg_attribute ON pg_depend.refobjid = pg_attribute.attrelid 
    AND pg_depend.refobjsubid = pg_attribute.attnum 
WHERE dependent.relname = 'your_table_name' 
AND pg_attribute.attname = 'your_column_name';
```