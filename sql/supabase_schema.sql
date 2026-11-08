create extension if not exists vector with schema extensions;
set search_path to public, extensions;

create table if not exists public.compliance_chunks (
    id text primary key,
    tenant_id text not null,
    document_id text not null,
    source text not null,
    content text not null,
    metadata jsonb not null,
    embedding vector(768) not null,
    updated_at timestamptz not null default now()
);

create index if not exists compliance_chunks_tenant_idx
    on public.compliance_chunks (tenant_id);

alter table public.compliance_chunks enable row level security;

-- The application connects using the Supabase database connection string.
-- Keep the service/database credentials server-side; never put them in Streamlit secrets.
