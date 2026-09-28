-- DESTRUCTIVE RESET for StegoLab. Run in the Supabase SQL Editor only when
-- you intend to erase all existing history and experiment rows. Existing
-- Storage objects are not deleted here; remove them through Storage API/UI.
-- Message text and stego keys are never stored. Images go to private Storage.

drop table if exists public.experiment_results cascade;
drop table if exists public.experiment_batches cascade;
drop table if exists public.bit_mode_results cascade;
drop table if exists public.steganography_runs cascade;

create table if not exists public.steganography_runs (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users (id) on delete set null,
    operation text not null
        check (operation in ('encode', 'decode', 'jpeg_test')),
    status text not null default 'success'
        check (status in ('success', 'failed', 'partial')),
    image_name text,
    source_image_path text,
    result_image_path text,
    image_width integer,
    image_height integer,
    selected_bits smallint
        check (selected_bits between 1 and 4),
    detected_bits smallint
        check (detected_bits between 1 and 4),
    message_length_bytes integer
        check (message_length_bytes >= 0),
    encrypted_payload_bytes integer
        check (encrypted_payload_bytes >= 0),
    capacity_bytes integer
        check (capacity_bytes >= 0),
    mse double precision
        check (mse >= 0),
    psnr_db double precision
        check (psnr_db >= 0),
    extraction_success boolean,
    jpeg_message_intact boolean,
    created_at timestamptz not null default now(),
    check (
        (image_width is null and image_height is null)
        or (image_width > 0 and image_height > 0)
    )
);

create index if not exists steganography_runs_user_created_idx
    on public.steganography_runs (user_id, created_at desc);

create table if not exists public.bit_mode_results (
    id uuid primary key default gen_random_uuid(),
    run_id uuid not null
        references public.steganography_runs (id) on delete cascade,
    bits_per_channel smallint not null
        check (bits_per_channel between 1 and 4),
    capacity_bytes integer not null
        check (capacity_bytes >= 0),
    plaintext_capacity_bytes integer not null
        check (plaintext_capacity_bytes >= 0),
    encrypted_payload_bytes integer not null
        check (encrypted_payload_bytes >= 0),
    mse double precision
        check (mse >= 0),
    psnr_db double precision
        check (psnr_db >= 0),
    status text not null
        check (status in ('pass', 'fail', 'insufficient_capacity')),
    created_at timestamptz not null default now(),
    unique (run_id, bits_per_channel)
);

create index if not exists bit_mode_results_run_idx
    on public.bit_mode_results (run_id);

-- One batch represents a run of either experiments/run_experiment.py or
-- Pengujian/run_experiments.py. Configuration can hold non-secret settings.
create table if not exists public.experiment_batches (
    id uuid primary key default gen_random_uuid(),
    user_id uuid references auth.users (id) on delete set null,
    source text not null,
    configuration jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);

create index if not exists experiment_batches_user_created_idx
    on public.experiment_batches (user_id, created_at desc);

create table if not exists public.experiment_results (
    id uuid primary key default gen_random_uuid(),
    batch_id uuid not null
        references public.experiment_batches (id) on delete cascade,
    image_name text not null,
    image_width integer
        check (image_width > 0),
    image_height integer
        check (image_height > 0),
    message_category text,
    message_length_chars integer
        check (message_length_chars >= 0),
    message_length_bytes integer
        check (message_length_bytes >= 0),
    encrypted_payload_bytes integer
        check (encrypted_payload_bytes >= 0),
    bits_per_channel smallint not null default 1
        check (bits_per_channel between 1 and 4),
    capacity_bytes integer
        check (capacity_bytes >= 0),
    mse double precision
        check (mse >= 0),
    psnr_db double precision
        check (psnr_db >= 0),
    encode_success boolean,
    decode_success boolean,
    message_matches boolean,
    status text not null,
    created_at timestamptz not null default now()
);

create index if not exists experiment_results_batch_idx
    on public.experiment_results (batch_id);

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

alter table public.steganography_runs enable row level security;
alter table public.bit_mode_results enable row level security;
alter table public.experiment_batches enable row level security;
alter table public.experiment_results enable row level security;

drop policy if exists "Users read own steganography runs"
    on public.steganography_runs;
create policy "Users read own steganography runs"
    on public.steganography_runs for select to authenticated
    using (user_id = (select auth.uid()));

drop policy if exists "Users insert own steganography runs"
    on public.steganography_runs;
create policy "Users insert own steganography runs"
    on public.steganography_runs for insert to authenticated
    with check (user_id = (select auth.uid()));

drop policy if exists "Users delete own steganography runs"
    on public.steganography_runs;
create policy "Users delete own steganography runs"
    on public.steganography_runs for delete to authenticated
    using (user_id = (select auth.uid()));

drop policy if exists "Users read own bit mode results"
    on public.bit_mode_results;
create policy "Users read own bit mode results"
    on public.bit_mode_results for select to authenticated
    using (
        exists (
            select 1 from public.steganography_runs as run
            where run.id = bit_mode_results.run_id
              and run.user_id = (select auth.uid())
        )
    );

drop policy if exists "Users insert own bit mode results"
    on public.bit_mode_results;
create policy "Users insert own bit mode results"
    on public.bit_mode_results for insert to authenticated
    with check (
        exists (
            select 1 from public.steganography_runs as run
            where run.id = bit_mode_results.run_id
              and run.user_id = (select auth.uid())
        )
    );

drop policy if exists "Users delete own bit mode results"
    on public.bit_mode_results;
create policy "Users delete own bit mode results"
    on public.bit_mode_results for delete to authenticated
    using (
        exists (
            select 1 from public.steganography_runs as run
            where run.id = bit_mode_results.run_id
              and run.user_id = (select auth.uid())
        )
    );

drop policy if exists "Users read own experiment batches"
    on public.experiment_batches;
create policy "Users read own experiment batches"
    on public.experiment_batches for select to authenticated
    using (user_id = (select auth.uid()));

drop policy if exists "Users insert own experiment batches"
    on public.experiment_batches;
create policy "Users insert own experiment batches"
    on public.experiment_batches for insert to authenticated
    with check (user_id = (select auth.uid()));

drop policy if exists "Users delete own experiment batches"
    on public.experiment_batches;
create policy "Users delete own experiment batches"
    on public.experiment_batches for delete to authenticated
    using (user_id = (select auth.uid()));

drop policy if exists "Users read own experiment results"
    on public.experiment_results;
create policy "Users read own experiment results"
    on public.experiment_results for select to authenticated
    using (
        exists (
            select 1 from public.experiment_batches as batch
            where batch.id = experiment_results.batch_id
              and batch.user_id = (select auth.uid())
        )
    );

drop policy if exists "Users insert own experiment results"
    on public.experiment_results;
create policy "Users insert own experiment results"
    on public.experiment_results for insert to authenticated
    with check (
        exists (
            select 1 from public.experiment_batches as batch
            where batch.id = experiment_results.batch_id
              and batch.user_id = (select auth.uid())
        )
    );

drop policy if exists "Users delete own experiment results"
    on public.experiment_results;
create policy "Users delete own experiment results"
    on public.experiment_results for delete to authenticated
    using (
        exists (
            select 1 from public.experiment_batches as batch
            where batch.id = experiment_results.batch_id
              and batch.user_id = (select auth.uid())
        )
    );

grant select, insert, delete on public.steganography_runs to authenticated;
grant select, insert, delete on public.bit_mode_results to authenticated;
grant select, insert, delete on public.experiment_batches to authenticated;
grant select, insert, delete on public.experiment_results to authenticated;