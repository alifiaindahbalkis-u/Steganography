alter table public.steganography_runs
    add column if not exists image_name text,
    add column if not exists source_image_path text,
    add column if not exists result_image_path text;

insert into storage.buckets (
    id,
    name,
    public,
    file_size_limit,
    allowed_mime_types
)
values (
    'stego-history',
    'stego-history',
    false,
    52428800,
    array['image/png']
)
on conflict (id) do update
set name = excluded.name,
    public = false,
    file_size_limit = excluded.file_size_limit,
    allowed_mime_types = excluded.allowed_mime_types;