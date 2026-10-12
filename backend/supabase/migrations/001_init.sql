create extension if not exists vector;

create table if not exists documents (
    id uuid primary key default gen_random_uuid(),
    user_id uuid,                      -- null = corpus compartido (solo lectura)
    name text not null,
    type text not null,
    status text not null default 'processing'
        check (status in ('processing', 'ready', 'error')),
    error text,
    created_at timestamptz not null default now()
);

create table if not exists chunks (
    id bigserial primary key,
    document_id uuid not null references documents(id) on delete cascade,
    content text not null,
    metadata jsonb not null default '{}'::jsonb,
    embedding vector(768) not null
);
create index if not exists chunks_embedding_idx
    on chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_document_idx on chunks(document_id);

create table if not exists conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    title text not null,
    created_at timestamptz not null default now()
);

create table if not exists messages (
    id bigserial primary key,
    conversation_id uuid not null references conversations(id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    sources jsonb,
    refused boolean not null default false,
    created_at timestamptz not null default now()
);
create index if not exists messages_conv_idx on messages(conversation_id, id);

-- RLS: el backend usa una conexión directa (rol postgres, que la omite) y filtra
-- por user_id en SQL; RLS protege el acceso directo con la clave anon.
alter table documents enable row level security;
alter table chunks enable row level security;
alter table conversations enable row level security;
alter table messages enable row level security;

create policy documents_read on documents for select
    using (user_id is null or user_id = auth.uid());
create policy documents_write on documents for all
    using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy chunks_read on chunks for select using (
    exists (select 1 from documents d where d.id = document_id
            and (d.user_id is null or d.user_id = auth.uid())));

create policy conversations_own on conversations for all
    using (user_id = auth.uid()) with check (user_id = auth.uid());

create policy messages_own on messages for all using (
    exists (select 1 from conversations c where c.id = conversation_id
            and c.user_id = auth.uid()));
