-- PostgreSQL Authentication Fix for CVAT Django Issues
-- Resolves "relation auth_user does not exist" errors

-- Set proper schema search path
SET search_path TO public;

-- Check if auth_user table exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'auth_user') THEN
        RAISE NOTICE 'auth_user table does not exist - Django migrations required';
    ELSE
        RAISE NOTICE 'auth_user table exists - checking structure...';
    END IF;
END
$$;

-- Verify auth_user table structure
SELECT 
    column_name,
    data_type,
    is_nullable,
    column_default
FROM information_schema.columns 
WHERE table_name = 'auth_user' 
ORDER BY ordinal_position;

-- Check table ownership
SELECT 
    schemaname,
    tablename,
    tableowner,
    tablespace
FROM pg_tables 
WHERE tablename = 'auth_user';

-- Verify indexes on auth_user
SELECT 
    indexname,
    indexdef
FROM pg_indexes 
WHERE tablename = 'auth_user';

-- Check for any permission issues
SELECT 
    grantee,
    privilege_type
FROM information_schema.table_privileges 
WHERE table_name = 'auth_user';

-- Test basic query that was failing
SELECT COUNT(*) as user_count FROM auth_user;

-- Check if there's a default admin user
SELECT 
    id,
    username,
    email,
    is_active,
    is_superuser,
    date_joined
FROM auth_user 
WHERE is_superuser = true
LIMIT 5;

-- Check Django migrations table
SELECT 
    app,
    name,
    applied
FROM django_migrations 
WHERE app IN ('auth', 'admin', 'contenttypes')
ORDER BY applied DESC
LIMIT 10;

-- Final health check
SELECT 
    'Database Schema Health Check' as status,
    CASE 
        WHEN EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'auth_user') 
        THEN 'PASS' 
        ELSE 'FAIL' 
    END as auth_user_exists,
    CASE 
        WHEN (SELECT COUNT(*) FROM auth_user WHERE is_superuser = true) > 0 
        THEN 'PASS' 
        ELSE 'WARN' 
    END as superuser_exists,
    (SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public') as total_tables;