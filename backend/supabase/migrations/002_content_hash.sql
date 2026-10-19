-- Deduplicación por contenido: hash SHA-256 (hex) del archivo subido.
alter table documents add column if not exists content_hash text;

-- Un usuario no puede tener dos documentos vigentes con el mismo contenido.
-- Los documentos en error quedan fuera para poder reintentar la subida.
create unique index if not exists documents_owner_hash_uidx
    on documents(user_id, content_hash)
    where user_id is not null and content_hash is not null and status <> 'error';
